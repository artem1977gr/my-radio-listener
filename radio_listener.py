import socket
import ssl  # <-- Добавлен импорт для шифрования
import time
from urllib.parse import urlparse
from multiprocessing import Process, current_process
import random
from datetime import datetime, timezone
from collections import Counter

# --- ВАШИ НАСТРОЙКИ (МЕНЯЙТЕ ЗДЕСЬ) ---

# 1. Список станций (фулл-лист софта)
RADIOS = [
    *(['https://listen7.myradio24.com/sintezi'] * 31),
    *(['https://listen7.myradio24.com/nevermind'] * 30),
    *(['https://listen7.myradio24.com/rockataka'] * 8),
    *(['https://listen7.myradio24.com/iridium'] * 10),
    *(['https://listen7.myradio24.com/63908'] * 30)
]

# 2. Словарь ВЕСОВ (используется для математически точного распределения)
STATION_WEIGHTS = {
    "https://listen7.myradio24.com/sintezi": 31,
    "https://listen7.myradio24.com/nevermind": 30,
    "https://listen7.myradio24.com/rockataka": 8,
    "https://listen7.myradio24.com/iridium": 10,
    "https://listen7.myradio24.com/63908": 30
}
TOTAL_BASE_WEIGHT = sum(STATION_WEIGHTS.values())  # Это число 109

# 3. Базовый сайт-реферер
REFERER_URL = "https://www.fmradiofree.com"

# 4. Длительность сессии одного потока (в секундах)
SESSION_DURATION_MIN = 100   
SESSION_DURATION_MAX = 1600  
READ_TIMEOUT_SEC = 5        
CHECK_INTERVAL_SEC = 300    
GRACEFUL_STOP_DELAY = 120   

# 5. Суточное расписание нагрузки (процент от TOTAL_BASE_WEIGHT)
TARGET_PERCENT_BY_HOUR = {
    0: 22, 1: 25, 2: 35, 3: 55, 4: 85, 5: 98, 6: 92, 7: 80,
    8: 75, 9: 78, 10: 76, 11: 74, 12: 77, 13: 82, 14: 90, 15: 100,
    16: 88, 17: 75, 18: 65, 19: 50, 20: 40, 21: 35, 22: 30, 23: 25
}

#### ⚡️ НАСТРОЙКИ РЕАЛИСТИЧНЫХ USER-AGENT'ОВ ###
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


def generate_user_agent():
    total_weight_platforms = sum(item["weight"] for item in PLATFORM_WEIGHTS)
    choice = random.uniform(0, total_weight_platforms)
    platform_data = next(plat for plat in PLATFORM_WEIGHTS if (choice := choice - plat["weight"]) < 0)

    total_weight_browsers = sum(item["weight"] for item in BROWSER_WEIGHTS)
    choice = random.uniform(0, total_weight_browsers)
    browser_data = next(brw for brw in BROWSER_WEIGHTS if (choice := choice - brw["weight"]) < 0)

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
    path = parsed_url.path or '/'

    headers = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: {host}:443\r\n"  # Обязательно указываем порт в Host
        f"Icy-MetaData: 1\r\n"
        f"User-Agent: {generate_user_agent()}\r\n"
        f"Referer: {REFERER_URL}\r\n"
        f"Connection: Keep-Alive\r\n"
        "\r\n"
    )

    while True:  
        session_duration = random.randint(SESSION_DURATION_MIN, SESSION_DURATION_MAX)
        try:
            raw_sock = socket.create_connection((host, 443))
            sock = ssl.wrap_socket(raw_sock)
            
            sock.settimeout(READ_TIMEOUT_SEC)
            sock.sendall(headers.encode())
            
            response_headers = b""
            while True:
                chunk = sock.recv(4096)
                if not chunk or b"\r\n\r\n" in response_headers:
                    break
                response_headers += chunk

            start_time = time.time()
            proc_name = current_process().name
            while int(time.time() - start_time) < session_duration:
                try:
                    sock.recv(1024)
                except socket.timeout:
                    pass
                except Exception as e:
                    print(f"[{time.strftime('%H:%M:%S')}] [{proc_name}] Read error for {url}: {e}")
                    break
        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] [{current_process().name}] Connection error for {url}: {e}. Reconnecting...")
        finally:
            try:
                sock.close()
            except Exception:
                pass


def get_target_listeners_for_now():
    """
    Получает целевое число слушателей как процент от суммы весов всех станций.
    Возвращает цель и сам словарь весов для менеджера.
    """
    utc_hour = datetime.now(timezone.utc).hour
    percent = TARGET_PERCENT_BY_HOUR[utc_hour]
    
    target_count = int(TOTAL_BASE_WEIGHT * (percent / 100))
    return target_count, STATION_WEIGHTS


def scheduler_manager(active_processes):
    alive_processes = [p for p in active_processes if p.is_alive()]
    
    new_target, station_weights = get_target_listeners_for_now()
    
    max_possible_listeners = TOTAL_BASE_WEIGHT
    target_count = min(new_target, max_possible_listeners)
    current_live = len(alive_processes)

    #### ШАГ 1: Считаем текущую нагрузку по URL ####
    live_urls = []
    for p in alive_processes:
        try:
            live_urls.append(p._args[0])
        except (AttributeError, IndexError):
            continue
            
    current_counts = Counter(live_urls)

    #### ШАГ 2: Вычисляем идеальную квоту для КАЖДОЙ станции ####
    targets_per_station = {}
    for station_url, weight in station_weights.items():
        ideal_count = int(target_count * (weight / TOTAL_BASE_WEIGHT))
        targets_per_station[station_url] = ideal_count

    #### ШАГ 3: ДОБОР ПРОЦЕССОВ строго по пропорции ####
    if to_spawn := target_count - current_live > 0:
        spawn_queue = []
        
        for station_url, ideal_count in targets_per_station.items():
            have_now = current_counts.get(station_url, 0)
            need_for_this_station = ideal_count - have_now
            
            if need_for_this_station > 0:
                spawn_queue.extend([station_url] * need_for_this_station)
                
                if len(spawn_queue) >= to_spawn:
                    break
        
        for radio_url in spawn_queue[:to_spawn]:
            p = Process(target=keep_radio_alive, args=(radio_url,))
            p.start()
            alive_processes.append(p)
            print(f"[MANAGER] Spawned listener -> {radio_url}")

    #### ШАГ 4: УДАЛЕНИЕ ЛИШНИХ ПРОЦЕССОВ строго по пропорции ####
    elif current_live > target_count:
        processes_to_kill = []
        
        for i in range(len(alive_processes) - 1, -1, -1):
            if len(processes_to_kill) >= current_live - target_count:
                break
            
            p = alive_processes[i]
            try:
                proc_url = p._args[0]
            except (AttributeError, IndexError):
                continue

            have_now = current_counts.get(proc_url, 0)
            ideal_count = targets_per_station.get(proc_url, 0)
            
            if have_now > ideal_count:
                processes_to_kill.append(p)
                current_counts[proc_url] -= 1

        for p in processes_to_kill:
            if p.is_alive():
                p.terminate()
                p.join(timeout=GRACEFUL_STOP_DELAY)
                if p.is_alive():
                    p.kill()
        
        alive_processes = [p for p in alive_processes if p not in processes_to_kill]

    return alive_processes


if __name__ == "__main__":
    manager_active = []
    initial_target, _ = get_target_listeners_for_now()
    print(f"[INIT] Starting at {initial_target} listeners based on current UTC hour.")
    manager_active = scheduler_manager(manager_active)

    try:
        while True:
            time.sleep(CHECK_INTERVAL_SEC)
            new_target, _ = get_target_listeners_for_now()
            alive_processes = [p for p in manager_active if p.is_alive()]
            if current_live := len(alive_processes) != new_target:
                timestamp = time.strftime('%H:%M:%S')
                print(f"[{timestamp}] Schedule change detected. Target: {new_target}, Live: {current_live}. Adjusting...")
                manager_active = scheduler_manager(alive_processes)
    except KeyboardInterrupt:
        print("\n[MAIN] Shutdown signal received. Terminating all processes...")
        for p in manager_active:
            if p.is_alive():
                p.terminate()
                p.join(timeout=5)
                if p.is_alive():
                    p.kill()
