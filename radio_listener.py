import socket
import time
from urllib.parse import urlparse
from multiprocessing import Process, current_process
import random
from datetime import datetime, timezone

# Глобальные настройки потоков (сумма = пик в 40 слушателей)
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

# --- ПАРАМЕТРЫ УПРАВЛЕНИЯ ПО ВРЕМЕНИ ---
BASE_LISTENERS = len(RADIOS)  # Максимальное число слушателей в пик (40)
CHECK_INTERVAL_SEC = 300       # Как часто проверять расписание (раз в 5 минут)
GRACEFUL_STOP_DELAY = 120     # Задержка перед принудительным убийством процесса (сек)

# Ваша таблица активности, нормализованная под BASE_LISTENERS (пик 40 человек в 15:00 UTC)
TARGET_LISTENERS_BY_HOUR = {
    0: 8, 1: 10, 2: 14, 3: 22, 4: 34, 5: 39, 6: 36, 7: 32,
    8: 30, 9: 31, 10: 30, 11: 29, 12: 30, 13: 32, 14: 36, 15: 40,
    16: 35, 17: 30, 18: 26, 19: 20, 20: 16, 21: 14, 22: 12, 23: 10
}

def generate_user_agent():
    """Генерирует реалистичный User-Agent."""
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
    """
    Функция отдельного слушателя.
    Поддерживает соединение активным случайное время от SESSION_DURATION_MIN до MAX.
    """
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

def get_target_listeners_for_now():
    """Получает целевое число слушателей для текущего часа по UTC"""
    utc_hour = datetime.now(timezone.utc).hour
    return TARGET_LISTENERS_BY_HOUR[utc_hour]

def scheduler_manager(active_processes, target_count):
    """
    Управляет пулом процессов: добирает или убирает слушателей до нужного числа.
    При сокращении пула убивает самые старые процессы.
    """
    current_count = len(active_processes)
    
    # Если нужно больше слушателей
    if current_count < target_count:
        to_spawn = target_count - current_count
        urls_pool = RADIOS.copy()
        random.shuffle(urls_pool)
        
        for i in range(to_spawn):
            radio_url = urls_pool[i % len(urls_pool)]
            p = Process(target=keep_radio_alive, args=(radio_url,))
            p.start()
            active_processes.append(p)
            print(f"[MANAGER] Spawned listener #{len(active_processes)} -> {radio_url}")
            
    # Если нужно меньше слушателей
    elif current_count > target_count:
        to_stop = current_count - target_count
        
        # Агрессивно завершаем лишние процессы (самые старые в списке)
        processes_to_kill = active_processes[:to_stop]
        remaining_processes = active_processes[to_stop:]
        
        for p in processes_to_kill:
            if p.is_alive():
                p.terminate()
                p.join(timeout=GRACEFUL_STOP_DELAY)
                if p.is_alive():
                    p.kill()
        
        active_processes.clear()
        active_processes.extend(remaining_processes)
        print(f"[MANAGER] Reduced pool to {len(active_processes)} listeners")

if __name__ == "__main__":
    manager_active = []
    
    # Первоначальный запуск на текущее значение по UTC
    initial_target = get_target_listeners_for_now()
    print(f"[INIT] Starting at {initial_target} listeners based on current UTC hour.")
    scheduler_manager(manager_active, initial_target)

    try:
        while True:
            time.sleep(CHECK_INTERVAL_SEC)  # Спит 5 минут (300 сек)
            
            new_target = get_target_listeners_for_now()
            # Очищаем список от завершившихся естественным путем процессов
            alive_processes = [p for p in manager_active if p.is_alive()]
            current_live = len(alive_processes)
            manager_active = alive_processes
            
            if current_live != new_target:
                timestamp = time.strftime('%H:%M:%S')
                print(f"[{timestamp}] Schedule change detected. Target: {new_target}, Live: {current_live}. Adjusting...")
                scheduler_manager(manager_active, new_target)

    except KeyboardInterrupt:
        print("\n[MAIN] Shutdown signal received. Terminating all processes...")
        for p in manager_active:
            if p.is_alive():
                p.terminate()
                p.join(timeout=5)
                if p.is_alive():
                    p.kill()
