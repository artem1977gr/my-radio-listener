import requests
from time import sleep, time as get_current_time
import datetime
import os  # Для переименования файла под workflow
import random
import json
import re
from bs4 import BeautifulSoup


# ⚡️ НАИБОЛЕЕ ПОЛНЫЙ СПИСОК ИСТОЧНИКОВ БЕСПЛАТНЫХ HTTP-ПРОКСИ
sources = [
    "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http",
    "https://www.proxy-list.download/api/v1/get?type=http",          # Анонимные + прозрачные
    
    # ProxyListDownload (API)
    {"name": "proxy-list-download", "types": ["HTTP", "SOCKS4", "SOCKS5"]},
    
    # Веб-сайты для парсинга HTML
    {
        "free-proxy-list": [
            "https://free-proxy-list.net/",
            "https://free-proxy-list.net/us-index.html",
            "https://free-proxy-list.net/uk-proxy.html",
            "https://free-proxy-list.net/anonymous-proxy.html"
        ],
        "ssl-proxies": "https://www.sslproxies.org/",  # Похожий формат таблицы
        "hidemy.name": "https://hide-my.ip/ru/proxy-list/?country=&type=shtt&anonymity=34&start=0#list",
        "cool-proxy": "https://www.cool-proxy.net/proxies/http_proxy_list/c country=a&port=&anonymity=&google=on&ping=under300&spam=on&sort=ping",
        "geonode": "https://proxylist.geonode.com/api/proxy-list?limit=500&page=1&sort_by=lastChecked&sort_type=desc&filter=type%3Dhttp"
    },
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
# МОДУЛЬ ДЛЯ СБОРА ПРОКСИ СО ВСЕХ ПОПУЛЯРНЫХ ВЕБ-САЙТОВ И API
###############################################################################
def scrape_free_proxy_sources():
    """
    Парсит десятки популярных источников бесплатных HTTP(S)/SOCKS-прокси.
    Возвращает список валидных строк вида "protocol://ip:port".
    """
    proxies = set()  # Множество для удаления дублей

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept-Language": "en-US,en;q=0.9"
    }

    def parse_table(soup, selector="table.table-bordered"):
        table = soup.find(selector)
        rows = table.tbody.find_all("tr") if table else []

        for row in rows:
            cells = [td.text.strip() for td in row.find_all("td")]
            
            # Обработка разных форматов таблиц
            ip = cells[0].strip()
            port = cells[1].strip()
            protocol = cells[6].lower().strip() if len(cells) > 6 else ""

            # Проверка типа протокола
            if protocol == "yes":
                proxy_str = f"https://{ip}:{port}"
            elif protocol == "no":
                proxy_str = f"http://{ip}:{port}"
            else:
                # Для других сайтов протокол может быть в другом месте
                proto_cell = next((c for c in cells if 'http' in c.lower()), "")
                protocols = re.findall(r'(http|https|socks4|socks5)', proto_cell)
                
                # Добавляем все возможные варианты из одной строки
                for proto in protocols:
                    proxy_str = f"{proto}://{ip}:{port}"
                    proxies.add(proxy_str)
    
    print("[INFO] Scraping free proxy websites and APIs...")
    for source_config in sources:
        try:
            name = list(source_config.keys())[0] if isinstance(source_config, dict) else None
            url_or_config = source_config[name] if isinstance(source_config, dict) else source_config

            if isinstance(url_or_config, str):  # Простой URL
                response = requests.get(url_or_config, timeout=10)
                new_proxies = load_proxies_from_source(response.text)
                proxies.update(new_proxies)
                continue

            if isinstance(url_or_config, dict):  # Спец-обработка API
                config = url_or_config["types"]

                if name == "proxy-list-download":  
                    base_url = "https://www.proxy-list.download/"
                    for proto in config:
                        api_url = f"{base_url}/api/v1/get?type={proto}"
                        response = requests.get(api_url, timeout=10)
                        new_proxies = load_proxies_from_source(response.text)
                        proxies.update(new_proxies)
                    continue

                raise ValueError(f"Unknown special source type: {name}")

            elif isinstance(url_or_config, list):  # Список страниц
                for page_url in url_or_config:
                    response = requests.get(page_url, headers=headers, timeout=10)
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # Разные сайты используют разные селекторы таблиц
                    selectors = ["table.table-bordered", "#proxy-table", ".table"]
                    for sel in selectors:
                        parse_table(soup, sel)
            else:  # Обычная страница
                response = requests.get(url_or_config, headers=headers, timeout=10)
                soup = BeautifulSoup(response.text, 'html.parser')
                parse_table(soup)

        except Exception as e:
            print(f"[WARNING] Failed to parse {name or source_config}: {e}")
    
    # Геонод возвращает JSON
    geonode_response = requests.get(
        "https://proxylist.geonode.com/api/proxy-list?limit=500&page=1&sort_by=lastChecked&sort_type=desc&filter=type%3Dhttp",
        headers=headers,
        timeout=10
    ).json()
    for entry in geonode_response.get("data", []):
        proxies.add(f"http://{entry['ip']}:{entry['port']}")

    return list(proxies)

def check_proxy(proxy_str):
    """
    ✅ УЛУЧШЕННАЯ проверка одного IP:PORT или protocol://IP:PORT.
    Теперь корректно работает с любыми входными данными.
    """

    # 🔹 Шаг 1: Приводим строку к единому формату IP:PORT
    # Это решает проблему дублирования протоколов ("http://http://")
    if proxy_str.startswith("http://") or proxy_str.startswith("https://"):
        # Если уже есть протокол, просто вырезаем всё после двоеточия
        ip_port = proxy_str.split("//")[1].split(":")
    else:
        # Иначе предполагаем, что это голая пара IP:PORT
        ip_port = proxy_str.strip().split(":")

    # Базовая валидность
    if len(ip_port) != 2 or not PROXY_PATTERN.match(f"{ip_port[0]}:{ip_port[1]}"):  
        return None  # Не валидный формат

    ip, port = ip_port

    # 🔥 Оставляем ТОЛЬКО HTTP(S). SOCKS часто работает нестабильно.
    protocols_to_check = ['http']

    results = []

    for protocol in protocols_to_check:
        session = requests.Session()
        
        full_proxy_url = f"{protocol}://{ip}:{port}"  # Собираем полную ссылку здесь
        proxies = {
            "http": full_proxy_url,
            "https": full_proxy_url
        }

        adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=50)
        session.mount('http://', adapter)
        session.mount('https://', adapter)

        # Адаптивный User-Agent для пинга
        session.headers.update({'User-Agent': random.choice(user_agents)})

        #######################################################################
        # Этап 1: БЫСТРАЯ ПРОВЕРКА ЧЕРЕЗ httpbin.org (PING)
        # Мы сначала проверяем базовую доступность и анонимность.
        #######################################################################
        try:
            # Получаем свой реальный внешний IP без прокси
            real_ip_resp = requests.get(
                "https://ifconfig.me/all.json",
                timeout=(PING_TIMEOUT_CONNECT, PING_TIMEOUT_READ),
                verify=False  # ❇️ Добавлено для обхода SSL-ошибок некоторых сайтов
            )
            real_ip_data = real_ip_resp.json()
            real_ip = real_ip_data.get("ip_addr")

            # То же самое, но через прокси
            response = session.get(
                "https://httpbin.org/ip",
                timeout=(PING_TIMEOUT_CONNECT, PING_TIMEOUT_READ),
                verify=False  # ❇️ Добавлено для обхода SSL-ошибок некоторых сайтов
            )
            
            data = response.json()
            origin = data.get('origin')

            # Метрика успеха №1: Статус-код 200 AND есть тело ответа
            # И наш реальный IP должен отличаться от того, что видит сервер!
            if (
                response.status_code != 200 or 
                not isinstance(origin, str) or 
                ip not in origin or 
                real_ip in origin
            ):
                print(f"[FAIL] {full_proxy_url} - Invalid ping result.")
                continue  # Следующий протокол

        except Exception as e:
            print(f"[FAIL] {full_proxy_url} - Ping error:", str(e))
            continue

        #######################################################################
        # Этап 2: БЫСТРАЯ ПРОВЕРКА ДОСТУПНОСТИ СТРИМА
        # Читаем всего 4 КБ данных за 5 секунд.
        # Это позволяет быстро отсечь мёртвые узлы.
        #######################################################################
        try:
            # Здесь можно указать любой твой поток или сайт для проверки
            response = session.get(
                "https://listen7.myradio24.com/iridium", 
                stream=True, 
                timeout=(STREAM_TIMEOUT_CONNECT, STREAM_TIMEOUT_READ),  # Увеличено время чтения стрима
                verify=False  # ❇️ Добавлено для обхода SSL-ошибок некоторых сайтов
            )  
            
            start_time = get_current_time()
            data_chunk = response.raw.read(4096)  # Меньше данных для быстрой диагностики
            end_time = get_current_time()

            # Метрика успеха №1: Получено минимум 1 Кбайт данных
            if not data_chunk or len(data_chunk) < 1024:
                print(f"[FAIL] {full_proxy_url} - Audio stream failed")
                continue  # Следующий протокол

            elapsed_seconds = end_time - start_time
            speed_kbps = len(data_chunk) / elapsed_seconds / 1024  # KB/s

            # 🔥 Понижаем планку скорости до 10 KB/s.
            # Для потокового аудио это критично важно!
            if speed_kbps < 10:
                print(f"[FAIL] {full_proxy_url} - Speed too low ({speed_kbps:.2f} KB/s)")
                continue

            latency = round((end_time - start_time) * 1000, 2)

            # Просто возвращаем URL рабочей прокси
            result = {'url': full_proxy_url}
            results.append(result)

        except Exception as e:
            print(f"[FAIL] {full_proxy_url} - Stream test error:", str(e))

    # Возвращаем ВСЕ рабочие варианты для этого IP
    return results

if __name__ == "__main__":
    MAX_WORK_TIME_MINUTES = 25
    TARGET_PROXY_COUNT_BASE = 10  # Я снизил базовое число до 10 для начала
    RESERVE_PERCENTAGE = 0.2  # Запас 20%

    # Загружаем старый файл с предыдущими рабочими прокси
    old_proxies_dict = {}
    try:
        with open("working_proxies.txt", "r") as file:
            # Строгий разбор каждой строки старого файла
            for line in file:
                parts = line.strip().split('|')[:1]  # Берём только первую часть (URL)
                url = parts[0].strip()

                # Извлекаем чистый IP:PORT для дальнейшей работы
                _, address = url.split('://')[:2]
                ip_port = address.split(':')

                # Проверки формата
                if len(ip_port) != 2 or not ip_port[1].isdigit():
                    raise ValueError(f"Invalid format: {url}")

                ip, _port = ip_port
                ports = old_proxies_dict.setdefault(ip, {})
                ports[url] = True  # Просто помечаем URL как ранее найденный
    
        print("[INFO] Previous proxy list loaded.")
    except FileNotFoundError:
        pass

    # Сначала проверяем старые прокси
    print("\n[INFO] Checking previous working proxies...")
    found_old_proxies = []
    for ip, urls in old_proxies_dict.items():
        for url in urls:
            # Передаём чистую пару IP:PORT
            results = check_proxy(url.replace('http://', '').replace('socks5h://', ''))
            if results:
                found_old_proxies.extend(results)

    # Теперь проверяем новые источники
    print("\n[INFO] Fetching new proxies to reach target count...")
    start_script_time = datetime.datetime.now()

    # Пробуем сначала загрузить из кэша
    all_proxies = []

    # Если нет кэша или он устарел — загружаем заново
    if not all_proxies:
        # Вместо загрузки из API собираем данные с веб-сайтов
        print("\n[INFO] Fetching new proxies from web sources...")
        all_proxies = scrape_free_proxy_sources()

        # Фильтруем мусор при помощи нашей функции
        valid_lines = load_proxies_from_source("\n".join(all_proxies))

        if len(valid_lines) == 0:
            print("[WARNING] No valid proxies found on any source.")
        else:
            all_proxies = valid_lines

    # Проверяем новые адреса
    found_new_proxies = []
    for proxy in all_proxies:
        # Проверка лимита времени
        elapsed_minutes = (datetime.datetime.now() - start_script_time).total_seconds() / 60
        if elapsed_minutes >= MAX_WORK_TIME_MINUTES:
            break

        sleep(0.1)
        results = check_proxy(proxy)
        if results:
            found_new_proxies.extend(results)

    # Объединение результатов
    total_target_count = int(TARGET_PROXY_COUNT_BASE * (1 + RESERVE_PERCENTAGE))

    unique_results = {}  # {IP: {port1, port2}} -> чтобы не было дублей
    for item in found_old_proxies + found_new_proxies:
        ip = item['url'].split('//')[1].split(':')[0]
        ports = unique_results.setdefault(ip, {})
        ports[item['url']] = item

    sorted_items = sorted([v for p in unique_results.values() for v in p.values()],
                          key=lambda x: x['url'])  # Сортируем просто по URL

    final_list = sorted_items[:total_target_count]

    # Сохраняем основной рабочий файл
    with open("working_proxies.txt", "w") as file:
        # Формат: Только чистый URL
        # Больше не сохраняем Latency и Speed, они нам сейчас не нужны
        for item in final_list:
            file.write(item['url'] + "\n")

    # ❇️ Выводим первые несколько узлов прямо в логи GitHub Actions
    print(f"\n[INFO] Found {len(final_list)} working proxies:")
    for i, node in enumerate(final_list[:5]):
        print(f"Proxy #{i+1}: {node['url']} (Speed ~{int(node.get('speed_kbps', 0))} KB/s)")





