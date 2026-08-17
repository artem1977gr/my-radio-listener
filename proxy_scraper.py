import requests
from time import sleep, time as get_current_time
import datetime
import os  # Для переименования файла под workflow
import random
import json
import re  # <--- Добавлено для регулярных выражений
from bs4 import BeautifulSoup


# ⚡️ НАИБОЛЕЕ ПОЛНЫЙ СПИСОК ИСТОЧНИКОВ БЕСПЛАТНЫХ HTTP-ПРОКСИ
sources = [
    # ✅ API-сервисы
    "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=10000",
    "https://www.proxy-list.download/api/v1/get?type=http",          # Анонимные + прозрачные
    "https://raw.githubusercontent.com/roosterkid/openproxylists/master/MIXED_ANON_HTTP.txt",
    "https://api.openproxylist.xyz/http.txt",
    
    # ✅ Веб-сайты для парсинга (будут собираться через наш модуль)
    "PARSE_FREE_PROXY_SOURCES"
]

# Настройки адаптивных таймаутов
PING_TIMEOUT_CONNECT = 5   # Быстрый пинг
PING_TIMEOUT_READ = 5      # Время на чтение первых данных стрима
STREAM_TIMEOUT_CONNECT = 5  # Тест полной скорости
STREAM_TIMEOUT_READ = 20

user_agents = [  # Ротация UA
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64; rv:88.0) Gecko/20100101 Firefox/88.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1'
]

working_proxies = []  # Сюда будут попадать только прошедшие проверку

# Регулярное выражение для проверки формата IPv4:Port
PROXY_PATTERN = re.compile(r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?):\d+$')

def load_proxies_from_source(raw_text):
    """Загружает прокси из сырого текста, фильтруя по формату."""
    lines = raw_text.splitlines()
    valid_proxies = []
    
    for line in lines:
        candidate = line.strip()
        # Проверяем, похожа ли строка на прокси, и нет ли в ней HTML-тегов или мусора
        if PROXY_PATTERN.match(candidate) and '<' not in candidate and '>' not in candidate:
            valid_proxies.append(candidate)
            
    return valid_proxies

###############################################################################
# МОДУЛЬ ДЛЯ СБОРА ПРОКСИ СО ВСЕХ ПОПУЛЯРНЫХ ВЕБ-САЙТОВ
###############################################################################
def scrape_free_proxy_sources():
    """
    Парсит десятки популярных сайтов с бесплатными прокси.
    Возвращает список валидных строк вида "http://ip:port".
    """
    urls = {
        "free-proxy-list": "https://free-proxy-list.net/",
        "us-proxies": "https://free-proxy-list.net/us-index.html",
        "uk-proxies": "https://free-proxy-list.net/uk-proxy.html",
        "anonymous-proxies": "https://free-proxy-list.net/anonymous-proxy.html",
        "ssl-proxies": "https://www.sslproxies.org/",
        
        # ProxyListDownload
        "proxy-list-download": ["HTTP", "SOCKS4", "SOCKS5"],
        
        # SpysOne
        "spys-one": ["all", "anon"],  # all / anon / transparent
        
        # Other sources
        "hidemy.name": "https://hide-my.ip/ru/proxy-list/?country=&type=shtt&anonymity=34&start=0#list",
        "cool-proxy": "https://www.cool-proxy.net/proxies/http_proxy_list/c country=a&port=&anonymity=&google=on&ping=under300&spam=on&sort=ping",
        "geonode": "https://proxylist.geonode.com/api/proxy-list?limit=500&page=1&sort_by=lastChecked&sort_type=desc&filter=type%3Dhttp"
    }

    proxies = set()  # Множество для удаления дублей

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept-Language": "en-US,en;q=0.9"
    }

    def parse_table(soup, selector="table"):
        table = soup.find(selector)
        rows = table.tbody.find_all("tr") if table else []

        for row in rows:
            cells = [td.text.strip() for td in row.find_all("td")]
            ip = cells[0].strip()
            port = cells[1].strip()
            protocol = cells[6].lower().strip() if len(cells) > 6 else ""

            # Проверка типа протокола
            if protocol == "yes":
                proxy_str = f"https://{ip}:{port}"
            elif protocol == "no":
                proxy_str = f"http://{ip}:{port}"
            else:
                continue

            proxies.add(proxy_str)

    print("[INFO] Scraping free proxy websites...")
    for source, url_or_config in urls.items():
        try:
            if source.startswith("proxy-list-download"):
                # Специальная обработка для proxy-list.download
                base_url = "https://www.proxy-list.download/"
                for proto in url_or_config:
                    response = requests.get(f"{base_url}/api/v1/get?type={proto}", timeout=10)
                    new_proxies = load_proxies_from_source(response.text)
                    proxies.update(new_proxies)
                continue

            if source == "spys-one":
                # Special handling for spys.one due to its complex structure
                for page_type in url_or_config:
                    url = f"https://spys.one/en/{page_type}proxy/"
                    response = requests.get(url, headers=headers, timeout=10)
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # На spys.one таблица скрыта в JavaScript, но есть текстовый блок
                    data_rows = soup.select_one("#xpproxytext").get_text(separator='\n').split('\n')
                    for row in data_rows:
                        parts = row.split(':')
                        if len(parts) >= 2:
                            ip_port = f"{parts[0]}:{parts[1]}"
                            proxies.add(ip_port)
                continue

            if isinstance(url_or_config, list):
                raise ValueError("Invalid URL configuration")

            # Обработка остальных сайтов как обычных страниц
            response = requests.get(url_or_config, headers=headers, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')

            # Разные сайты используют разные селекторы таблиц
            selectors = ["table.table-bordered", "#proxy-table", ".table"]
            for sel in selectors:
                parse_table(soup, sel)

        except Exception as e:
            print(f"[WARNING] Failed to parse {source}: {e}")
    
    # Геонод возвращает JSON
    geonode_response = requests.get(urls["geonode"], headers=headers).json()
    for entry in geonode_response.get("data", []):
        proxies.add(f"http://{entry['ip']}:{entry['port']}")

    return list(proxies)
