import socket
import time
from urllib.parse import urlparse
from multiprocessing import Process
import random
from datetime import datetime, timezone


# ⚡️ ВАЖНЫЙ БЛОК ДЛЯ РУЧНОЙ НАСТРОЙКИ ⚡️
STATION_WEIGHTS = {
    "sintezi": 31,
    "rockataka": 8,
    "iridium": 7,
    "nevermind": 30,
}
BASE_LISTENERS = sum(STATION_WEIGHTS.values())
RADIOS = []
for station, weight in STATION_WEIGHTS.items():
    RADIOS.extend([f"https://listen7.myradio24.com/{station}"] * int(weight))
REFERER_URL = "https://radio.art-test-1.store"
SESSION_DURATION_MIN = CHECK_INTERVAL_SEC  # Минимум равен интервалу проверки (5 минут)
SESSION_DURATION_MAX = SESSION_DURATION_MIN * 3  # Максимум ~15 минут
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


def keep_radio_alive(slot_index, url):  # Первый аргумент — номер слота
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
                proc_name = f"Slot #{slot_index}"

                while int(time.time() - start_time) < session_duration:
                    try:
                        sock.recv(1024)
                    except socket.timeout:
                        pass
                    except Exception as e:
                        print(f"[{time.strftime('%H:%M:%S')}] [{proc_name}] Read error for {url}: {e}")
                        break

        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] [{proc_name}] Connection error for {url}: {e}. Reconnecting...")
        
        finally:
            elapsed = int(time.time() - start_time)
            mins, secs = divmod(elapsed, 60)
            print(f"[{mins}:{secs:02d}] Listener on {url} ended.")


CHECK_INTERVAL_SEC = 300       # Как часто проверять расписание (раз в 5 минут)
GRACEFUL_STOP_DELAY = 120     # Задержка перед принудительным убийством процесса (сек)

TARGET_PERCENT_BY_HOUR = {
    0: 22, 1: 25, 2: 35, 3: 55, 4: 85, 5: 98, 6: 92, 7: 80,
    8: 75, 9: 78, 10: 76, 11: 74, 12: 77, 13: 82, 14: 90, 15: 100,
    16: 88, 17: 75, 18: 65, 19: 50, 20: 40, 21: 35, 22: 30, 23: 25
}


class SlotProcess(Process):
    def __init__(self, slot, group=None, target=None, name=None, args=(), kwargs={}, *, daemon=None):
        super().__init__(group=group, target=target, name=name, args=args, kwargs=kwargs, daemon=daemon)
        self.slot = slot  # Сохраняем номер слота


def get_target_listeners_for_now():
    utc_hour = datetime.now(timezone.utc).hour
    percent = TARGET_PERCENT_BY_HOUR.get(utc_hour, 0) / 100  
    target_count = int(BASE_LISTENERS * percent)
    return target_count


def scheduler_manager(active_processes):
    """⚡️ Финальная логика ✅"""
    # Мы создаём новый список для живых процессов.
    alive_processes = []  

    # Проверяем ВСЕ активные процессы.
    # Если у процесса нет атрибута `.slot`, значит он старый или зомби.
    for process in active_processes[:]:  # Копируем срез списка, чтобы избежать изменения во время итерации
        if process.is_alive() and hasattr(process, 'slot'):  # Оставляем только наши процессы
            alive_processes.append(process)

    new_target = get_target_listeners_for_now()

    occupied_slots = {getattr(p, 'slot', None) for p in alive_processes}
    free_slots = set(range(len(RADIOS))) - occupied_slots

    to_spawn = max(new_target - len(alive_processes), 0)

    #### ⚡️ Равномерное добавление процессов ✅
    # Мы выбираем свободные слоты случайным образом, чтобы избежать перекрытия.
    slots_to_fill = random.sample(list(free_slots), min(to_spawn, len(free_slots)))

    # Если свободных слотов нет, ничего не создаём.
    if not slots_to_fill:
        return alive_processes

    for slot_index in slots_to_fill:
        radio_url = RADIOS[slot_index]
        p = SlotProcess(
            slot=slot_index,
            target=keep_radio_alive,
            args=(slot_index, radio_url,)  # Передаём оба параметра правильно
        )
        p.start()
        print(f"[MANAGER] Spawned listener #{slot_index} -> {radio_url}")
        alive_processes.append(p)

    #### УДАЛЕНИЕ ЛИШНИХ ПРОЦЕССОВ (Плавно!) ####
    # ⚡️ Выровняй эту строку строго под def!!!
    elif len(alive_processes) > new_target:
        processes_to_kill = []

        # ⚡️ Важный фикс PICKLE ERROR ✅ Для плавного перехода мы сортируем по PID.
        # Метод _popen.pid возвращает уникальный ID процесса ОС.
        # Это гарантирует уникальную идентификацию даже после перезагрузки сервера.
        # Мы проверяем наличие _popen, потому что процесс мог уже завершиться естественным путём.
        sorted_processes = [(p._popen.pid, p) for p in alive_processes if hasattr(p, "_popen")]

        # Сортируем по уникальному идентификатору ОС.
        # Самые старые процессы будут иметь меньший PID.
        sorted_processes.sort(key=lambda x: x[0])  # От старых к новым
        alive_processes = [item[1] for item in sorted_processes[:new_target]]  # Оставляем самых молодых

        processes_to_kill = [item[1] for item in sorted_processes[new_target:]]

        for p in processes_to_kill:
            if p.is_alive():  # Ещё раз проверяем живость
                p.terminate()
                p.join(timeout=GRACEFUL_STOP_DELAY)
                if p.is_alive():
                    p.kill()

    # ⚡️ Возвращаем очищенный список
    return alive_processes


if __name__ == "__main__":
    manager_active = []
    
    initial_target = get_target_listeners_for_now()
    print(f"[INIT] Starting at {initial_target} listeners based on current UTC hour.")

    try:
        while True:
            # ⚡️ Финальная структура цикла ✅ Работает только со свежим списком от менеджера.
            manager_active = scheduler_manager(manager_active)
            
            time.sleep(CHECK_INTERVAL_SEC)  # Спим 5 минут (300 сек)

    except KeyboardInterrupt:
        print("\n[MAIN] Shutdown signal received. Terminating all processes...")
        for p in manager_active:
            if p.is_alive():
                p.terminate()
                p.join(timeout=5)
                if p.is_alive():
                    p.kill()
