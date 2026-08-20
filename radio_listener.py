import socket
import time
from urllib.parse import urlparse
from multiprocessing import Process
import random
from collections import Counter
from datetime import datetime
from zoneinfo import ZoneInfo

# Глобальные настройки (ЕДИНСТВЕННЫЙ источник данных)
RADIOS = [
    *(['https://listen7.myradio24.com/sintezi'] * 20),
    *(['https://listen7.myradio24.com/rockataka'] * 5), 
    *(['https://listen7.myradio24.com/iridium'] * 5),
    *(['https://listen7.myradio24.com/nevermind'] * 10)
]
REFERER_URL = "https://radio.art-test-1.store"
SESSION_DURATION_MIN = 100   
SESSION_DURATION_MAX = 1600  
READ_TIMEOUT_SEC = 5        
MOSCOW_TZ = ZoneInfo("Europe/Moscow")

#### НАСТРОЙКИ РЕАЛИСТИЧНЫХ USER-AGENT'ОВ ###
PLATFORM_WEIGHTS = [  
    {"os": "Windows", "version": "NT 10.0; Win64; x64", "weight": 0.1},  
    {"os": "Mac OS X", "version": "10_15_7", "weight": 0.05},
    {"os": "Android", "version": "13", "arch": "SM-S901B", "weight": 0.3},
    {"os": "iPhone", "version": "16_6", "model": "iPhone14,2", "weight": 0.2},
    {"os": "Linux", "version": "x86_64", "weight": 0.05},
    {"os": "X11", "version": "Ubuntu; Linux x86_64", "weight": 0.05}
]

BROWSER_WEIGHTS = [  
    {"name": "Chrome", "version": "129.0.0.0", "weight": 0.6},  
    {"name": "Firefox", "version": "121.0", "weight": 0.2},
    {"name": "Safari", "version": "605.1.15", "weight": 0.1},
    {"name": "Edge", "version": "120.0.2210.57", "weight": 0.05},
    {"name": "Opera", "version": "98.0.4825.16", "weight": 0.05}
]

#### СУТОЧНЫЙ ПРОФИЛЬ НАГРУЗКИ ####
HOURLY_LOAD = {
    "00": 0.35, "01": 0.30, "02": 0.25, "03": 0.22, "04": 0.25, "05": 0.35,
    "06": 0.55, "07": 0.85, "08": 0.98, "09": 0.92, "10": 0.80, "11": 0.75,
    "12": 0.78, "13": 0.76, "14": 0.74, "15": 0.77, "16": 0.82, "17": 0.90,
    "18": 1.00, "19": 0.88, "20": 0.75, "21": 0.65, "22": 0.50, "23": 0.40
}

def generate_user_agent():
    total_weight_platforms = sum(item["weight"] for item in PLATFORM_WEIGHTS)
    choice = random.uniform(0, total_weight_platforms)
    current_weight = 0
    for plat in PLATFORM_WEIGHTS:
        current_weight += plat["weight"]
        if choice < current_weight:
            platform_data = plat
            break
    
    total_weight_browsers = sum(item["weight"] for item in BROWSER_WEIGHTS)
    choice = random.uniform(0, total_weight_browsers)
    current_weight = 0
    for brw in BROWSER_WEIGHTS:
        current_weight += brw["weight"]
        if choice < current_weight:
            browser_data = brw
            break
    
    ua_template = (
        f"Mozilla/5.0 ({platform_data['os']} {platform_data.get('version', '')}; "
        f"{platform_data.get('arch', '')} {platform_data.get('model', '')}) "
        f"AppleWebKit/{random.randint(537, 605)}.{random.randint(1, 36)} "
        f"(KHTML, like Gecko) {browser_data['name']}/{browser_data['version']} "
        f"Safari/537.{random.randint(30, 40)}"
    )
    return ua_template.strip()


def keep_radio_alive(url):
    parsed_url = urlparse(url)
    host = parsed_url.netloc.split(':')[0] 
    path = parsed_url.path  

    headers = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: {host}\r\n"
        f"Icy-MetaData: 1\r\n"
        f"User-Agent: {generate_user_agent()}\r\n"
        f"Referer: {REFERER_URL}\r\n"
        f"Connection: Keep-Alive\r\n"
        "\r\n"
    )

    while True:  
        session_duration = random.randint(SESSION_DURATION_MIN, SESSION_DURATION_MAX)
        
        try:
            with socket.create_connection((host, 80)) as sock:
                sock.settimeout(READ_TIMEOUT_SEC)
                sock.sendall(headers.encode())
                
                response_headers = b""
                while True:
                    chunk = sock.recv(4096)
                    if not chunk or b"\r\n\r\n" in response_headers:
                        break
                    response_headers += chunk

                start_time = time.time()
                while int(time.time() - start_time) < session_duration:
                    try:
                        sock.recv(1024)
                    except socket.timeout:
                        pass
                    except Exception as e:
                        # Время ошибок остается системным (без привязки к MSK)
                        print(f"[{time.strftime('%H:%M:%S')}] Read error for {url}: {e}")
                        break

        except Exception as e:
            # Время ошибок остается системным (без привязки к MSK)
            print(f"[{time.strftime('%H:%M:%S')}] Connection error for {url}: {e}. Reconnecting...")
        
        finally:
            elapsed = int(time.time() - start_time)
            mins, secs = divmod(elapsed, 60)
            print(f"[{mins}:{secs:02d}] Listener on {url} ended.")


def get_moscow_hour():
    """Возвращает текущий час строкой ('00'-'23') именно по Москве."""
    # ПОЛНОСТЬЮ ИСПРАВЛЕНО: используем только datetime
    return datetime.now(MOSCOW_TZ).strftime("%H")


def get_current_hour_factor():
    hour_str = get_moscow_hour()
    return HOURLY_LOAD.get(hour_str, 1.0)


def build_target_pool(target_total, source_list):
    pool = []
    counts = Counter(source_list)
    unique_urls = list(dict.fromkeys(source_list))
    
    base_quotas = dict(counts)
    
    if target_total < sum(base_quotas.values()):
        temp_pool = []
        for url in unique_urls:
            share = round(target_total * (base_quotas[url] / sum(base_quotas.values())))
            temp_pool.extend([url] * share)
        
        diff = target_total - len(temp_pool)
        if diff > 0:
            for _ in range(diff):
                temp_pool.append(random.choice(unique_urls))
        elif diff < 0:
            for _ in range(abs(diff)):
                if temp_pool:
                    temp_pool.pop()
        
        pool = temp_pool
    else:
        for url in unique_urls:
            pool.extend([url] * base_quotas[url])
            
        remainder = target_total - len(pool)
        if remainder > 0:
            for i in range(remainder):
                pool.append(unique_urls[i % len(unique_urls)])

    random.shuffle(pool)
    return pool


if __name__ == "__main__":
    processes = []
    last_logged_hour = None
    
    while True:
        alive_new = []
        for p in processes:
            if p.is_alive():
                if time.time() - p._start_time > 60:
                    p.terminate()
                    p.join()
                else:
                    alive_new.append(p)
        processes = alive_new

        # Расчет нагрузки ПО МОСКОВСКОМУ ВРЕМЕНИ
        current_hour = get_moscow_hour()
        
        if current_hour != last_logged_hour:
            full_time = datetime.now(MOSCOW_TZ).strftime('%H:%M:%S')
            print(f"[{full_time}] Hour changed to {current_hour}:00 (MSK). Adjusting load...")
            last_logged_hour = current_hour

        factor = get_current_hour_factor()
        target_total = int(len(RADIOS) * factor)
        
        target_pool = build_target_pool(target_total, RADIOS)

        needed = len(target_pool) - len(processes)
        
        if needed > 0:
            urls_to_start = target_pool[len(processes):]
            for url in urls_to_start:
                p = Process(target=keep_radio_alive, args=(url,))
                p._start_time = time.time()
                p.start()
                processes.append(p)
        
        time.sleep(60)
