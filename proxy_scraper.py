import time
from urllib.parse import urlparse # Для правильной работы с URL
import requests
from bs4 import BeautifulSoup
import re
import socks


# Путь к выходному файлу (должен совпадать с тем, что указан в radio_listener.py)
PROXY_FILE_PATH = "working_proxies.txt"


def fetch_free_proxy_list_net():
    """Парсинг таблицы с Free-Proxy-List.net"""
    url = "https://free-proxy-list.net/"
    response = requests.get(url)
    
    soup = BeautifulSoup(response.text, 'html.parser')
    table = soup.find('table', id='proxylisttable')
    
    proxies = []
    for row in table.tbody.find_all('tr'):
        cols = [td.text.strip() for td in row.find_all('td')]
        
        # Берём только анонимные HTTP(S) прокси без авторизации
        if len(cols) >= 8 and cols[6] == 'yes' and not cols[4].startswith("SOCKS"):
            ip = cols[0]
            port = cols[1]
            
            # Простая проверка IP
            if re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", ip):
                proxies.append(f"{ip}:{port}")
    
    return proxies


def fetch_proxyscrape_api(country="ru"):
    """
    Получаем свежие прокси через ProxyScrape API.
    country=ru -> Только российские IP-адреса.
    """
    api_url = (
        f"https://api.proxyscrape.com/v2/?request=getproxies&protocol=http"
        "&timeout=5000&anonymity=all"
        f"&country={country}"
    )
    try:
        resp = requests.get(api_url)
        return resp.text.splitlines()
    except Exception as e:
        print(f"[ERROR] ProxyScrape API failed: {e}")
        return []


def check_proxy(proxy_str, target_url="https://listen7.myradio24.com/sintezi"):
    """
    Проверяет, может ли данный прокси пропустить потоковый контент.
    Возвращает True/False и время ответа.
    """
    host, port = proxy_str.rsplit(":", 1)
    port = int(port)

    s = socks.socksocket()
    s.set_proxy(socks.PROXY_TYPE_HTTP, host, port)
    s.settimeout(10)  

    parsed_url = target_url.split("/")[2] 
    start_time = time.time()

    try:
        # Пробуем установить TCP-соединение с сервером вещания ЧЕРЕЗ ПРОКСИ.
        # Если соединение прошло — значит, прокси пропускает аудиопоток.
        s.connect((parsed_url, 80))
        
        elapsed = time.time() - start_time
        return True, elapsed  # Прокси работает!
    except Exception as _:
        return False, None  # Прокси мёртв или блокирует аудио


def update_proxy_list():
    """
    Собирает бесплатные прокси из нескольких источников,
    проверяет их и сохраняет в working_proxies.txt.
    Сохраняет максимум 100 лучших по скорости.
    """
    all_sources = [
        ("Free-Proxy-List.net", fetch_free_proxy_list_net()),
        ("ProxyScrape API", fetch_proxyscrape_api())
    ]

    unique_proxies = set()
    for source_name, proxy_list in all_sources:
        print(f"\n[INFO] Found {len(proxy_list)} proxies from {source_name}.")
        unique_proxies.update(proxy_list)

    print(f"\n[INFO] Total unique proxies collected: {len(unique_proxies)}. Starting checks...")

    working_proxies = {}
    for i, proxy in enumerate(unique_proxies):
        ok, latency = check_proxy(proxy)
        if ok:
            print(f"[OK] #{i+1} {proxy} works! Latency: {latency:.2f}s")
            working_proxies[proxy] = latency
        else:
            print(f"[FAIL] #{i+1} {proxy} is dead.")

    # Сортируем по времени отклика и берём первые 100
    top_100 = dict(sorted(working_proxies.items(), key=lambda x: x[1])[:100])

    with open(PROXY_FILE_PATH, "w") as f:
        for proxy, latency in top_100.items():
            print(f"Saving {proxy} with latency {latency:.2f}s")  # Лог для отладки
            f.write(proxy + "\n")
