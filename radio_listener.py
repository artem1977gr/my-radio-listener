import socket
import time
import random
from urllib.parse import urlparse
from multiprocessing import Process, Queue, Event, current_process
from datetime import datetime, timezone

#### ОБЩИЕ НАСТРОЙКИ ####
SESSION_DURATION_MIN = 100   
SESSION_DURATION_MAX = 1600  
READ_TIMEOUT_SEC = 5        
CHECK_INTERVAL_SEC = 300     
GRACEFUL_STOP_DELAY = 120    

# ЕДИНЫЙ ГРАФИК ДЛЯ ВСЕХ СТАНЦИЙ
TARGET_PERCENT_BY_HOUR = {
    0: 22, 1: 25, 2: 35, 3: 55, 4: 85, 5: 98, 6: 92, 7: 80,
    8: 75, 9: 78, 10: 76, 11: 74, 12: 77, 13: 82, 14: 90, 15: 100,
    16: 88, 17: 75, 18: 65, 19: 50, 20: 40, 21: 35, 22: 30, 23: 25
}

# --- ГЛОБАЛЬНЫЕ КОНСТАНТЫ СТАНЦИЙ ---
RADIO_SINTEZI = "https://listen7.myradio24.com/sintezi"
REFERER_SINTEZI = "https://source-sintezi.ru"
MAX_SINTEZI = 31

RADIO_NEVERMIND = "https://listen7.myradio24.com/nevermind"
REFERER_NEVERMIND = "https://source-nevermind.ru"
MAX_NEVERMIND = 30

RADIO_ROCKATAKA = "https://listen7.myradio24.com/rockataka"
REFERER_ROCKATAKA = "https://source-rockataka.ru"
MAX_ROCKATAKA = 8

RADIO_IRIDIUM = "https://listen7.myradio24.com/iridium"
REFERER_IRIDIUM = "https://source-iridium.ru"
MAX_IRIDIUM = 10

def generate_user_agent():
    PLATFORM_WEIGHTS = [{"os": "Windows", "version": "NT 10.0; Win64; x64", "weight": 0.1}, {"os": "Mac OS X", "version": "10_15_7", "weight": 0.05},
                        {"os": "Android", "version": "13", "arch": "SM-S901B", "weight": 0.3}, {"os": "iPhone", "version": "16_6", "model": "iPhone14,2", "weight": 0.2},
                        {"os": "Linux", "version": "x86_64", "weight": 0.05}, {"os": "X11", "version": "Ubuntu; Linux x86_64", "weight": 0.05}]
    BROWSER_WEIGHTS = [{"name": "Chrome", "version": "129.0.0.0", "weight": 0.6}, {"name": "Firefox", "version": "121.0", "weight": 0.2},
                       {"name": "Safari", "version": "605.1.15", "weight": 0.1}, {"name": "Edge", "version": "120.0.2210.57", "weight": 0.05}, {"name": "Opera", "version": "98.0.4825.16", "weight": 0.05}]
    
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

# --- МЕНЕДЖЕРЫ-ДЕМОНЫ (теперь они НЕ daemon, а просто функции для запуска в процессах) ---

def sintezi_manager_loop(command_queue, stop_event):
    active_listeners = []
    while not stop_event.is_set():
        try:
            cmd = command_queue.get(timeout=1)
            if cmd == "kill_all":
                for p in active_listeners:
                    if p.is_alive(): p.terminate(); p.join(timeout=5); p.kill()
                active_listeners.clear()
                continue
            elif isinstance(cmd, tuple) and cmd[0] == "spawn":
                slot_index = cmd[1]
                p = Process(target=keep_radio_alive, args=(RADIO_SINTEZI, REFERER_SINTEZI))
                p.start()
                active_listeners.insert(slot_index, p)
                print(f"[SINTEZI-MANAGER] Spawned #{slot_index}")
        except Exception:
            pass
            
        # Регулярная проверка каждые 5 минут
        time.sleep(CHECK_INTERVAL_SEC)
        alive = [p for p in active_listeners if p.is_alive()]
        target = int(MAX_SINTEZI * (TARGET_PERCENT_BY_HOUR[datetime.now(timezone.utc).hour] / 100))
        
        # Убиваем лишних
        to_kill = len(alive) - target
        if to_kill > 0:
            processes_to_kill = alive[:to_kill]
            for p in processes_to_kill:
                if p.is_alive(): p.terminate(); p.join(timeout=GRACEFUL_STOP_DELAY); p.kill()
            active_listeners = alive[to_kill:]
            print(f"[SINTEZI-MANAGER] Killed {to_kill} excess listeners.")
            
        # Добираем недостающих
        all_slots = set(range(MAX_SINTEZI))
        occupied = set(active_listeners.index(p) for p in alive if p in active_listeners)
        free = list(all_slots - occupied)
        
        current_live = len(alive)
        to_spawn = target - current_live
        if to_spawn > 0 and free:
            slots_to_fill = random.sample(free, min(to_spawn, len(free)))
            for slot_index in slots_to_fill:
                command_queue.put(("spawn", slot_index))

# Остальные три менеджера идентичны по логике (меняются только константы MAX_* и RADIO_*)
def nevermind_manager_loop(command_queue, stop_event):
    active_listeners = []
    while not stop_event.is_set():
        try:
            cmd = command_queue.get(timeout=1)
            if cmd == "kill_all":
                for p in active_listeners:
                    if p.is_alive(): p.terminate(); p.join(timeout=5); p.kill()
                active_listeners.clear()
            elif isinstance(cmd, tuple) and cmd[0] == "spawn":
                slot_index = cmd[1]
                p = Process(target=keep_radio_alive, args=(RADIO_NEVERMIND, REFERER_NEVERMIND))
                p.start()
                active_listeners.insert(slot_index, p)
                print(f"[NEVERMIND-MANAGER] Spawned #{slot_index}")
        except Exception:
            pass
        time.sleep(CHECK_INTERVAL_SEC)
        alive = [p for p in active_listeners if p.is_alive()]
        target = int(MAX_NEVERMIND * (TARGET_PERCENT_BY_HOUR[datetime.now(timezone.utc).hour] / 100))
        to_kill = len(alive) - target
        if to_kill > 0:
            processes_to_kill = alive[:to_kill]
            for p in processes_to_kill:
                if p.is_alive(): p.terminate(); p.join(timeout=GRACEFUL_STOP_DELAY); p.kill()
            active_listeners = alive[to_kill:]
            print(f"[NEVERMIND-MANAGER] Killed {to_kill} excess listeners.")
        all_slots = set(range(MAX_NEVERMIND))
        occupied = set(active_listeners.index(p) for p in alive if p in active_listeners)
        free = list(all_slots - occupied)
        current_live = len(alive)
        to_spawn = target - current_live
        if to_spawn > 0 and free:
            slots_to_fill = random.sample(free, min(to_spawn, len(free)))
            for slot_index in slots_to_fill:
                command_queue.put(("spawn", slot_index))

def rockataka_manager_loop(command_queue, stop_event):
    active_listeners = []
    while not stop_event.is_set():
        try:
            cmd = command_queue.get(timeout=1)
            if cmd == "kill_all":
                for p in active_listeners:
                    if p.is_alive(): p.terminate(); p.join(timeout=5); p.kill()
                active_listeners.clear()
            elif isinstance(cmd, tuple) and cmd[0] == "spawn":
                slot_index = cmd[1]
                p = Process(target=keep_radio_alive, args=(RADIO_ROCKATAKA, REFERER_ROCKATAKA))
                p.start()
                active_listeners.insert(slot_index, p)
                print(f"[ROCKATAKA-MANAGER] Spawned #{slot_index}")
        except Exception:
            pass
        time.sleep(CHECK_INTERVAL_SEC)
        alive = [p for p in active_listeners if p.is_alive()]
        target = int(MAX_ROCKATAKA * (TARGET_PERCENT_BY_HOUR[datetime.now(timezone.utc).hour] / 100))
        to_kill = len(alive) - target
        if to_kill > 0:
            processes_to_kill = alive[:to_kill]
            for p in processes_to_kill:
                if p.is_alive(): p.terminate(); p.join(timeout=GRACEFUL_STOP_DELAY); p.kill()
            active_listeners = alive[to_kill:]
            print(f"[ROCKATAKA-MANAGER] Killed {to_kill} excess listeners.")
        all_slots = set(range(MAX_ROCKATAKA))
        occupied = set(active_listeners.index(p) for p in alive if p in active_listeners)
        free = list(all_slots - occupied)
        current_live = len(alive)
        to_spawn = target - current_live
        if to_spawn > 0 and free:
            slots_to_fill = random.sample(free, min(to_spawn, len(free)))
            for slot_index in slots_to_fill:
                command_queue.put(("spawn", slot_index))

def iridium_manager_loop(command_queue, stop_event):
    active_listeners = []
    while not stop_event.is_set():
        try:
            cmd = command_queue.get(timeout=1)
            if cmd == "kill_all":
                for p in active_listeners:
                    if p.is_alive(): p.terminate(); p.join(timeout=5); p.kill()
                active_listeners.clear()
            elif isinstance(cmd, tuple) and cmd[0] == "spawn":
                slot_index = cmd[1]
                p = Process(target=keep_radio_alive, args=(RADIO_IRIDIUM, REFERER_IRIDIUM))
                p.start()
                active_listeners.insert(slot_index, p)
                print(f"[IRIDIUM-MANAGER] Spawned #{slot_index}")
        except Exception:
            pass
        time.sleep(CHECK_INTERVAL_SEC)
        alive = [p for p in active_listeners if p.is_alive()]
        target = int(MAX_IRIDIUM * (TARGET_PERCENT_BY_HOUR[datetime.now(timezone.utc).hour] / 100))
        to_kill = len(alive) - target
        if to_kill > 0:
            processes_to_kill = alive[:to_kill]
            for p in processes_to_kill:
                if p.is_alive(): p.terminate(); p.join(timeout=GRACEFUL_STOP_DELAY); p.kill()
            active_listeners = alive[to_kill:]
            print(f"[IRIDIUM-MANAGER] Killed {to_kill} excess listeners.")
        all_slots = set(range(MAX_IRIDIUM))
        occupied = set(active_listeners.index(p) for p in alive if p in active_listeners)
        free = list(all_slots - occupied)
        current_live = len(alive)
        to_spawn = target - current_live
        if to_spawn > 0 and free:
            slots_to_fill = random.sample(free, min(to_spawn, len(free)))
            for slot_index in slots_to_fill:
                command_queue.put(("spawn", slot_index))

if __name__ == "__main__":
    # Очереди команд для каждого менеджера
    q_sin, q_nev, q_roc, q_iri = Queue(), Queue(), Queue(), Queue()
    stop_event = Event()

    # Запуск менеджеров как обычных процессов (без daemon=True)
    m1 = Process(target=sintezi_manager_loop, args=(q_sin, stop_event))
    m2 = Process(target=nevermind_manager_loop, args=(q_nev, stop_event))
    m3 = Process(target=rockataka_manager_loop, args=(q_roc, stop_event))
    m4 = Process(target=iridium_manager_loop, args=(q_iri, stop_event))
    
    m1.start(); m2.start(); m3.start(); m4.start()
    
    # ПЕРВИЧНАЯ ИНИЦИАЛИЗАЦИЯ через команды
    init_sin = int(MAX_SINTEZI * (TARGET_PERCENT_BY_HOUR[datetime.now(timezone.utc).hour] / 100))
    init_nev = int(MAX_NEVERMIND * (TARGET_PERCENT_BY_HOUR[datetime.now(timezone.utc).hour] / 100))
    init_roc = int(MAX_ROCKATAKA * (TARGET_PERCENT_BY_HOUR[datetime.now(timezone.utc).hour] / 100))
    init_iri = int(MAX_IRIDIUM * (TARGET_PERCENT_BY_HOUR[datetime.now(timezone.utc).hour] / 100))
    
    print(f"[INIT] Starting at Sintezi:{init_sin} Nevermind:{init_nev} Rockataka:{init_roc} Iridium:{init_iri}")
    
    for i in range(init_sin): q_sin.put(("spawn", i))
    for i in range(init_nev): q_nev.put(("spawn", i))
    for i in range(init_roc): q_roc.put(("spawn", i))
    for i in range(init_iri): q_iri.put(("spawn", i))

    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        print("\n[MAIN] Shutdown signal received.")
        stop_event.set()
        
        # Чистим все очереди, чтобы менеджеры не зависли на .get()
        for q in [q_sin, q_nev, q_roc, q_iri]:
            while not q.empty(): q.get()
        # Шлем команду экстренной очистки
        q_sin.put("kill_all"); q_nev.put("kill_all"); q_roc.put("kill_all"); q_iri.put("kill_all")
        
        time.sleep(3)
        for p in [m1, m2, m3, m4]:
            if p.is_alive(): p.terminate(); p.join(timeout=5); p.kill()
