import socket
import time
from urllib.parse import urlparse
from multiprocessing import Process, current_process
import random
from datetime import datetime, timezone


# Глобальные настройки потоков (сумма = пик)
RADIOS = [
    *(['https://listen7.myradio24.com/sintezi'] * 31),
    *(['https://listen7.myradio24.com/rockataka'] * 8), 
    *(['https://listen7.myradio24.com/iridium'] * 10),
    *(['https://listen7.myradio24.com/nevermind'] * 30),
    *(['https://listen7.myradio24.com/nevermind0'] * 10)
]
REFERER_URL = "https://fmradiofree.com"
SESSION_DURATION_MIN = 100   # Минимум ~1:40 мин
SESSION_DURATION_MAX = 1600  # Максимум ~27 минут
READ_TIMEOUT_SEC = 5        # Ключевое изменение!


#### ⚡️ НАСТРОЙКИ РЕАЛИСТИЧНЫХ USER-AGENT'ОВ ###
PLATFORM_WEIGHTS = [  
    {"os": "Windows", "version": "NT 10.0; Win64; x64", "weight": 0.1},  
    {"os": "Mac OS X", "version": "10_15_7", "weight": 0.05},
    
    # Мобильная аудитория (большинство пользователей)
    {"os": "Android", "version": "13", "arch": "SM-S901B", "weight": 0.3},
    {"os": "iPhone", "version": "16_6", "model": "iPhone14,2", "weight": 0.2},
    
    # Другие десктопы
    {"os": "Linux", "version": "x86_64", "weight": 0.05},
    {"os": "X11", "version": "Ubuntu; Linux x86_64", "weight": 0.05}
]

BROWSER_WEIGHTS = [  
    {"name": "Chrome", "version": "129.0.0.0", "weight": 0.6},  # Доминирует
    {"name": "Firefox", "version": "121.0", "weight": 0.2},
    {"name": "Safari", "version": "605.1.15", "weight": 0.1},
    {"name": "Edge", "version": "120.0.2210.57", "weight": 0.05},
    {"name": "Opera", "version": "98.0.4825.16", "weight": 0.05}
]


def generate_user_agent():
    """Генерирует реалистичный User-Agent."""
    #### ВЫБИРАЕМ ПЛАТФОРМУ ПО ВЕСАМ ####
    total_weight_platforms = sum(item["weight"] for item in PLATFORM_WEIGHTS)
    choice = random.uniform(0, total_weight_platforms)
    current_weight = 0
    for plat in PLATFORM_WEIGHTS:
        current_weight += plat["weight"]
        if choice < current_weight:
            platform_data = plat
            break
    
    #### ВЫБИРАЕМ БРАУЗЕР ПО ВЕСАМ ####
    total_weight_browsers = sum(item["weight"] for item in BROWSER_WEIGHTS)
    choice = random.uniform(0, total_weight_browsers)
    current_weight = 0
    for brw in BROWSER_WEIGHTS:
        current_weight += brw["weight"]
        if choice < current_weight:
            browser_data = brw
            break
    
    #### СОБИРАЕМ СТРОКУ ####
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
        
        #### КЛЮЧЕВОЕ ИЗМЕНЕНИЕ: генерируем сложный UA ###
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
                sock.settimeout(READ_TIMEOUT_SEC)  # Чтение каждые 5 секунд

                sock.sendall(headers.encode())
                
                response_headers = b""
                while True:
                    chunk = sock.recv(4096)
                    if not chunk or b"\r\n\r\n" in response_headers:
                        break
                    response_headers += chunk

                start_time = time.time()
                proc_name = current_process().name

                #### ОПТИМИЗАЦИЯ ПОД ОБЛАЧНЫЕ СЕРВЕРЫ ####
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


# --- НОВЫЕ ПАРАМЕТРЫ ДЛЯ УПРАВЛЕНИЯ ПО ВРЕМЕНИ ---
CHECK_INTERVAL_SEC = 300       # Как часто проверять расписание (раз в 5 минут)
GRACEFUL_STOP_DELAY = 120     # Задержка перед принудительным убийством процесса (сек)

# 🔥 ВАЖНО! Здесь мы вычисляем BASE_LISTENERS динамически,
# исходя из длины вашего списка RADIOS. Это база для расчёта процентов.
BASE_LISTENERS = len(RADIOS)

# ✅ ТАБЛИЦА ПРОЦЕНТОВ ОТ MAXIMUM
# Теперь каждый час выражен в процентах от BASE_LISTENERS.
TARGET_PERCENT_BY_HOUR = {
    0: 22, 1: 25, 2: 35, 3: 55, 4: 85, 5: 98, 6: 92, 7: 80,
    8: 75, 9: 78, 10: 76, 11: 74, 12: 77, 13: 82, 14: 90, 15: 100,
    16: 88, 17: 75, 18: 65, 19: 50, 20: 40, 21: 35, 22: 30, 23: 25
}


def get_target_listeners_for_now():
    """
    Получает целевое число слушателей как процент от текущего размера списка URL.
    """
    utc_hour = datetime.now(timezone.utc).hour
    percent = TARGET_PERCENT_BY_HOUR[utc_hour]
    target_count = int(BASE_LISTENERS * (percent / 100))
    return target_count


def scheduler_manager(active_processes):
    """
    Управляет пулом процессов так, чтобы их было ровно столько,
    сколько указано в расписании, но не больше длины списка RADIOS.
    """
    alive_processes = [p for p in active_processes if p.is_alive()]

    # Текущее время по UTC
    new_target = get_target_listeners_for_now()

    # Мы ограничиваем целевую цифру длиной нашего списка URL
    max_possible_listeners = len(RADIOS)
    target_count = min(new_target, max_possible_listeners)

    current_live = len(alive_processes)

    #### ДОБОР ПРОЦЕССОВ ####
    # Нам нужно столько же процессов, сколько указано в графике, но не более длины списка
    free_slots = set(range(len(RADIOS)))  # Все возможные слоты
    occupied_slots = {active_processes.index(p) for p in alive_processes}  # Занятые слоты
    free_slots -= occupied_slots  # Оставшиеся свободные слоты

    to_spawn = target_count - current_live
    if to_spawn > 0 and free_slots:
        slots_to_fill = random.sample(list(free_slots), min(to_spawn, len(free_slots)))
        for slot_index in slots_to_fill:
            radio_url = RADIOS[slot_index]
            p = Process(target=keep_radio_alive, args=(radio_url,))
            p.start()
            # Важно вставить новый процесс в его слот, чтобы сохранить порядок
            alive_processes.insert(slot_index, p)
            print(f"[MANAGER] Spawned listener #{slot_index} -> {radio_url}")

    #### УДАЛЕНИЕ ЛИШНИХ ПРОЦЕССОВ ####
    elif current_live > target_count:
        processes_to_kill = []
        # Сначала пытаемся убить самые старые процессы (с большими индексами)
        for i, p in enumerate(reversed(alive_processes)):
            if len(processes_to_kill) >= current_live - target_count:
                break
            processes_to_kill.append(p)

        for p in processes_to_kill:
            if p.is_alive():
                p.terminate()
                p.join(timeout=GRACEFUL_STOP_DELAY)
                if p.is_alive():
                    p.kill()

        # Удаляем убитые процессы из списка
        alive_processes = [p for p in alive_processes if p not in processes_to_kill]

    manager_active.clear()
    manager_active.extend(alive_processes)


if __name__ == "__main__":
    manager_active = []
    
    # Первоначальный запуск на текущее значение по UTC
    initial_target = get_target_listeners_for_now()
    print(f"[INIT] Starting at {initial_target} listeners based on current UTC hour.")
    scheduler_manager(manager_active)

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
                scheduler_manager(manager_active)

    except KeyboardInterrupt:
        print("\n[MAIN] Shutdown signal received. Terminating all processes...")
        for p in manager_active:
            if p.is_alive():
                p.terminate()
                p.join(timeout=5)
                if p.is_alive():
                    p.kill()
