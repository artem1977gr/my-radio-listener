import socket
import time
import random
from urllib.parse import urlparse
from multiprocessing import Process, current_process
from datetime import datetime, timezone

#### ОБЩИЕ НАСТРОЙКИ ####
SESSION_DURATION_MIN = 100   
SESSION_DURATION_MAX = 1600  
READ_TIMEOUT_SEC = 5        
CHECK_INTERVAL_SEC = 300     
GRACEFUL_STOP_DELAY = 120    

# Настройки User-Agent остаются общими для всех станций
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

def keep_radio_alive(url, referer_url):
    parsed_url = urlparse(url)
    host = parsed_url.netloc.split(':')[0] 
    path = parsed_url.path or '/' 
    headers = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: {host}\r\n"
        f"Icy-MetaData: 1\r\n"
        f"User-Agent: {generate_user_agent()}\r\n"
        f"Referer: {referer_url}\r\n"
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
            elapsed = int(time.time() - start_time)
            mins, secs = divmod(elapsed, 60)
            print(f"[{mins}:{secs:02d}] Listener on {url} ended.")

# --- СТАНЦИЯ 1: sintezi ---
RADIO_SINTEZI = "https://listen7.myradio24.com/sintezi"
MAX_SINTEZI = 31
REFERER_SINTEZI = "https://source-sintezi.ru"
TARGET_PERCENT_BY_HOUR_SINTEZI = {
    0: 23, 1: 26, 2: 35, 3: 55, 4: 84, 5: 97, 6: 94, 7: 81,
    8: 74, 9: 77, 10: 77, 11: 74, 12: 77, 13: 81, 14: 90, 15: 100,
    16: 87, 17: 74, 18: 65, 19: 52, 20: 39, 21: 35, 22: 29, 23: 26
}
manager_sintezi_active = []

def get_target_sintezi():
    utc_hour = datetime.now(timezone.utc).hour
    percent = TARGET_PERCENT_BY_HOUR_SINTEZI[utc_hour]
    return int(MAX_SINTEZI * (percent / 100))

def scheduler_sintezi(active_processes):
    alive = [p for p in active_processes if p.is_alive()]
    target = get_target_sintezi()
    current_live = len(alive)
    free_slots = set(range(MAX_SINTEZI)) - {active_processes.index(p) for p in alive}
    to_spawn = target - current_live
    if to_spawn > 0 and free_slots:
        slots_to_fill = random.sample(list(free_slots), min(to_spawn, len(free_slots)))
        for slot_index in slots_to_fill:
            p = Process(target=keep_radio_alive, args=(RADIO_SINTEZI, REFERER_SINTEZI))
            p.start()
            active_processes.insert(slot_index, p)
            print(f"[SINTEZI-MANAGER] Spawned #{slot_index}")
    elif current_live > target:
        processes_to_kill = list(reversed(alive))[:current_live - target]
        for p in processes_to_kill:
            if p.is_alive(): p.terminate(); p.join(timeout=GRACEFUL_STOP_DELAY); p.kill()
        active_processes = [p for p in alive if p not in processes_to_kill]
    manager_sintezi_active.clear(); manager_sintezi_active.extend(active_processes)

# --- СТАНЦИЯ 2: nevermind ---
RADIO_NEVERMIND = "https://listen7.myradio24.com/nevermind"
MAX_NEVERMIND = 30
REFERER_NEVERMIND = "https://source-nevermind.ru"
TARGET_PERCENT_BY_HOUR_NEVERMIND = {
    0: 23, 1: 27, 2: 37, 3: 57, 4: 87, 5: 100, 6: 97, 7: 83,
    8: 77, 9: 80, 10: 80, 11: 77, 12: 80, 13: 83, 14: 93, 15: 103,
    16: 90, 17: 77, 18: 67, 19: 53, 20: 40, 21: 37, 22: 30, 23: 27
}
manager_nevermind_active = []

def get_target_nevermind():
    utc_hour = datetime.now(timezone.utc).hour
    percent = TARGET_PERCENT_BY_HOUR_NEVERMIND[utc_hour]
    return int(MAX_NEVERMIND * (percent / 100))

def scheduler_nevermind(active_processes):
    alive = [p for p in active_processes if p.is_alive()]
    target = get_target_nevermind()
    current_live = len(alive)
    free_slots = set(range(MAX_NEVERMIND)) - {active_processes.index(p) for p in alive}
    to_spawn = target - current_live
    if to_spawn > 0 and free_slots:
        slots_to_fill = random.sample(list(free_slots), min(to_spawn, len(free_slots)))
        for slot_index in slots_to_fill:
            p = Process(target=keep_radio_alive, args=(RADIO_NEVERMIND, REFERER_NEVERMIND))
            p.start()
            active_processes.insert(slot_index, p)
            print(f"[NEVERMIND-MANAGER] Spawned #{slot_index}")
    elif current_live > target:
        processes_to_kill = list(reversed(alive))[:current_live - target]
        for p in processes_to_kill:
            if p.is_alive(): p.terminate(); p.join(timeout=GRACEFUL_STOP_DELAY); p.kill()
        active_processes = [p for p in alive if p not in processes_to_kill]
    manager_nevermind_active.clear(); manager_nevermind_active.extend(active_processes)

# --- СТАНЦИЯ 3: rockataka ---
RADIO_ROCKATAKA = "https://listen7.myradio24.com/rockataka"
MAX_ROCKATAKA = 8
REFERER_ROCKATAKA = "https://source-rockataka.ru"
TARGET_PERCENT_BY_HOUR_ROCKATAKA = {
    0: 25, 1: 25, 2: 38, 3: 50, 4: 88, 5: 100, 6: 88, 7: 75,
    8: 75, 9: 75, 10: 75, 11: 75, 12: 75, 13: 88, 14: 88, 15: 100,
    16: 88, 17: 75, 18: 62, 19: 50, 20: 38, 21: 38, 22: 25, 23: 25
}
manager_rockataka_active = []

def get_target_rockataka():
    utc_hour = datetime.now(timezone.utc).hour
    percent = TARGET_PERCENT_BY_HOUR_ROCKATAKA[utc_hour]
    return int(MAX_ROCKATAKA * (percent / 100))

def scheduler_rockataka(active_processes):
    alive = [p for p in active_processes if p.is_alive()]
    target = get_target_rockataka()
    current_live = len(alive)
    free_slots = set(range(MAX_ROCKATAKA)) - {active_processes.index(p) for p in alive}
    to_spawn = target - current_live
    if to_spawn > 0 and free_slots:
        slots_to_fill = random.sample(list(free_slots), min(to_spawn, len(free_slots)))
        for slot_index in slots_to_fill:
            p = Process(target=keep_radio_alive, args=(RADIO_ROCKATAKA, REFERER_ROCKATAKA))
            p.start()
            active_processes.insert(slot_index, p)
            print(f"[ROCKATAKA-MANAGER] Spawned #{slot_index}")
    elif current_live > target:
        processes_to_kill = list(reversed(alive))[:current_live - target]
        for p in processes_to_kill:
            if p.is_alive(): p.terminate(); p.join(timeout=GRACEFUL_STOP_DELAY); p.kill()
        active_processes = [p for p in alive if p not in processes_to_kill]
    manager_rockataka_active.clear(); manager_rockataka_active.extend(active_processes)

# --- СТАНЦИЯ 4: iridium ---
RADIO_IRIDIUM = "https://listen7.myradio24.com/iridium"
MAX_IRIDIUM = 10
REFERER_IRIDIUM = "https://source-iridium.ru"
TARGET_PERCENT_BY_HOUR_IRIDIUM = {
    0: 20, 1: 30, 2: 40, 3: 60, 4: 90, 5: 100, 6: 90, 7: 80,
    8: 80, 9: 80, 10: 80, 11: 70, 12: 80, 13: 80, 14: 90, 15: 100,
    16: 90, 17: 80, 18: 70, 19: 50, 20: 40, 21: 40, 22: 30, 23: 30
}
manager_iridium_active = []

def get_target_iridium():
    utc_hour = datetime.now(timezone.utc).hour
    percent = TARGET_PERCENT_BY_HOUR_IRIDIUM[utc_hour]
    return int(MAX_IRIDIUM * (percent / 100))

def scheduler_iridium(active_processes):
    alive = [p for p in active_processes if p.is_alive()]
    target = get_target_iridium()
    current_live = len(alive)
    free_slots = set(range(MAX_IRIDIUM)) - {active_processes.index(p) for p in alive}
    to_spawn = target - current_live
    if to_spawn > 0 and free_slots:
        slots_to_fill = random.sample(list(free_slots), min(to_spawn, len(free_slots)))
        for slot_index in slots_to_fill:
            p = Process(target=keep_radio_alive, args=(RADIO_IRIDIUM, REFERER_IRIDIUM))
            p.start()
            active_processes.insert(slot_index, p)
            print(f"[IRIDIUM-MANAGER] Spawned #{slot_index}")
    elif current_live > target:
        processes_to_kill = list(reversed(alive))[:current_live - target]
        for p in processes_to_kill:
            if p.is_alive(): p.terminate(); p.join(timeout=GRACEFUL_STOP_DELAY); p.kill()
        active_processes = [p for p in alive if p not in processes_to_kill]
    manager_iridium_active.clear(); manager_iridium_active.extend(active_processes)


if __name__ == "__main__":
    # Первоначальный запуск четырех менеджеров
    init_sin = get_target_sintezi()
    init_nev = get_target_nevermind()
    init_roc = get_target_rockataka()
    init_iri = get_target_iridium()
    print(f"[INIT] Sintezi:{init_sin} Nevermind:{init_nev} Rockataka:{init_roc} Iridium:{init_iri}")
    
    scheduler_sintezi(manager_sintezi_active)
    scheduler_nevermind(manager_nevermind_active)
    scheduler_rockataka(manager_rockataka_active)
    scheduler_iridium(manager_iridium_active)

    try:
        while True:
            time.sleep(CHECK_INTERVAL_SEC)
            
            s_alive = [p for p in manager_sintezi_active if p.is_alive()]
            n_alive = [p for p in manager_nevermind_active if p.is_alive()]
            r_alive = [p for p in manager_rockataka_active if p.is_alive()]
            i_alive = [p for p in manager_iridium_active if p.is_alive()]
            
            manager_sintezi_active = s_alive
            manager_nevermind_active = n_alive
            manager_rockataka_active = r_alive
            manager_iridium_active = i_alive

            new_sin = get_target_sintezi()
            new_nev = get_target_nevermind()
            new_roc = get_target_rockataka()
            new_iri = get_target_iridium()

            if len(s_alive) != new_sin or len(n_alive) != new_nev or len(r_alive) != new_roc or len(i_alive) != new_iri:
                timestamp = time.strftime('%H:%M:%S')
                print(f"[{timestamp}] GLOBAL ADJUSTMENT DETECTED.")
                scheduler_sintezi(manager_sintezi_active)
                scheduler_nevermind(manager_nevermind_active)
                scheduler_rockataka(manager_rockataka_active)
                scheduler_iridium(manager_iridium_active)

    except KeyboardInterrupt:
        print("\n[MAIN] Shutdown signal received. Terminating all substation managers...")
        for station_list in [manager_sintezi_active, manager_nevermind_active, manager_rockataka_active, manager_iridium_active]:
            for p in station_list:
                if p.is_alive():
                    p.terminate()
                    p.join(timeout=5)
                    if p.is_alive():
                        p.kill()
