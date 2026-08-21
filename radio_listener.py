import socket
import ssl  # <-- Добавлен импорт для шифрования
import time
from urllib.parse import urlparse
from multiprocessing import Process, current_process
import random
from datetime import datetime, timezone


# --- ВАШИ НАСТРОЙКИ (МЕНЯЙТЕ ЗДЕСЬ) ---

# 1. Список станций. Дублируйте URL столько раз, сколько веса хотите дать станции.
#    Порядок важен! Менеджер будет заполнять этот массив подряд.
RADIOS = [
    *(['https://listen7.myradio24.com/sintezi'] * 31),
    *(['https://listen7.myradio24.com/nevermind'] * 30),
    *(['https://listen7.myradio24.com/rockataka'] * 8),
    *(['https://listen7.myradio24.com/iridium'] * 10),
    *(['https://listen7.myradio24.com/63908'] * 30)
]
REFERER_URL = "https://www.fmradiofree.com"
SESSION_DURATION_MIN = 100   
SESSION_DURATION_MAX = 1600  
READ_TIMEOUT_SEC = 5        
CHECK_INTERVAL_SEC = 300    
GRACEFUL_STOP_DELAY = 120   

# 2. Суточное расписание нагрузки (процент от длины массива RADIOS)
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
        f"Host: {host}:443\r\n"  # Ключевое исправление: порт 443 в Host
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
    utc_hour = datetime.now(timezone.utc).hour
    percent = TARGET_PERCENT_BY_HOUR[utc_hour]
    
    # База берется из физического количества элементов в RADIOS (сумма весов)
    base_listeners = len(RADIOS)
    target_count = int(base_listeners * (percent / 100))
    return target_count


def scheduler_manager(active_processes):
    alive_processes = [p for p in active_processes if p.is_alive()]
    
    new_target = get_target_listeners_for_now()
    current_live = len(alive_processes)

    #### ДОБОР ПРОЦЕССОВ ####
    if to_spawn := new_target - current_live > 0:
        # Находим свободные ИНДЕКСЫ в глобальном массиве RADIOS
        free_slots = set(range(len(RADIOS))) - {active_processes.index(p) for p in alive_processes if p in active_processes}
        
        slots_to_fill = random.sample(list(free_slots), min(to_spawn, len(free_slots)))
        for slot_index in slots_to_fill:
            radio_url = RADIOS[slot_index]
            p = Process(target=keep_radio_alive, args=(radio_url,))
            p.start()
            # Вставляем новый процесс СТРОГО в его слот внутри общего списка
            active_processes.insert(slot_index, p)
            print(f"[MANAGER] Spawned listener #{slot_index} -> {radio_url}")

    #### УДАЛЕНИЕ ЛИШНИХ ПРОЦЕССОВ ####
    elif current_live > new_target:
        processes_to_kill = []
        # Идем с конца списка, чтобы не сбивать индексы при удалении
        for i in range(len(alive_processes) - 1, -1, -1):
            if len(processes_to_kill) >= current_live - new_target:
                break
            processes_to_kill.append(alive_processes[i])

        for p in processes_to_kill:
            if p.is_alive():
                p.terminate()
                p.join(timeout=GRACEFUL_STOP_DELAY)
                if p.is_alive():
                    p.kill()
        
        # Удаляем убитые процессы из основного списка
        active_processes = [p for p in active_processes if p not in processes_to_kill]

    return active_processes


if __name__ == "__main__":
    manager_active = []
    
    initial_target = get_target_listeners_for_now()
    print(f"[INIT] Starting at {initial_target} listeners based on current UTC hour.")
    
    # Первоначальный запуск
    manager_active = scheduler_manager(manager_active)

    try:
        while True:
            time.sleep(CHECK_INTERVAL_SEC)
            
            new_target = get_target_listeners_for_now()
            alive_processes = [p for p in manager_active if p.is_alive()]
            
            # Обновляем главный список актуальными живыми процессами
            manager_active = alive_processes
            
            if len(alive_processes) != new_target:
                timestamp = time.strftime('%H:%M:%S')
                print(f"[{timestamp}] Schedule change detected. Target: {new_target}, Live: {len(alive_processes)}. Adjusting...")
                manager_active = scheduler_manager(alive_processes)

    except KeyboardInterrupt:
        print("\n[MAIN] Shutdown signal received. Terminating all processes...")
        for p in manager_active:
            if p.is_alive():
                p.terminate()
                p.join(timeout=5)
                if p.is_alive():
                    p.kill()
