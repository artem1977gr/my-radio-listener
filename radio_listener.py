import socket
import time
from urllib.parse import urlparse # Для правильной работы с URL
from multiprocessing import Process
import random
from datetime import datetime
from zoneinfo import ZoneInfo


# Глобальные настройки (твои текущие)
RADIOS = [
    *(['https://listen7.myradio24.com/sintezi'] * 20),
    *(['https://listen7.myradio24.com/rockataka'] * 5), 
    *(['https://listen7.myradio24.com/iridium'] * 5),
    *(['https://listen7.myradio24.com/nevermind'] * 10)
]
REFERER_URL = "https://radio.art-test-1.store"
SESSION_DURATION_MIN = 100   # Минимум ~1:40 мин 🔥 НИКАКИЕ ИЗМЕНЕНИЯ НЕ ВНОСИЛ!
SESSION_DURATION_MAX = 1600  # Максимум ~27 минут 🔥 НИКАКИЕ ИЗМЕНЕНИЯ НЕ ВНОСИЛ!
MOSCOW_TZ = ZoneInfo("Europe/Moscow") # Таймзона для графика нагрузки

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
    parsed_url = urlparse(url)
    host = parsed_url.netloc.split(':')[0] 
    path = parsed_path = parsed_url.path or '/'

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
                # 🔹 ФИКС №1: Убираем явный таймаут чтения! Сокет должен быть живым всегда.
                response_headers = b""
                while True:
                    chunk = sock.recv(4096)
                    if not chunk or b"\r\n\r\n" in response_headers:
                        break
                    response_headers += chunk

                start_time = time.time()

                #### ОПТИМИЗАЦИЯ ПОД ОБЛАЧНЫЕ СЕРВЕРЫ ####
                finish_time = start_time + session_duration  # Жёсткий лимит на закрытие

                # 🔹 ФИКС №2: Читаем данные БЕЗ ЛИМИТА по времени.
                # Сервер увидит нас как живого клиента даже при тишине в эфире.
                while int(time.time()) < finish_time:
                    try:
                        data = sock.recv(1024)
                        
                        # Пустой пакет — это нормально. Продолжаем слушать.
                        # Так мы держим соединение открытым.
                        if not data:
                            continue
                            
                    except Exception as e:
                        print(f"[{time.strftime('%H:%M:%S')}] Read error for {url}: {e}")
                        break

        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] Connection error for {url}: {e}. Reconnecting...")
        
        finally:
            elapsed = int(time.time() - start_time)
            mins, secs = divmod(elapsed, 60)
            print(f"[{mins}:{secs:02d}] Listener on {url} ended.")




if __name__ == "__main__":
    processes = []

    def get_target_pool():
        """
        Возвращает список URL для запуска, учитывая график нагрузки.
        Этот метод вычисляет целевое число потоков только один раз за час.
        """
        hour_str = datetime.now(MOSCOW_TZ).strftime("%H")
        factor = HOURLY_LOAD[hour_str]
        target_total = int(len(RADIOS) * factor)
        pool = RADIOS.copy()
        random.shuffle(pool)
        return pool[:target_total]

    # 🔸 ПУНКТ А: Запуск всех нужных процессов ОДИН РАЗ.
    # Здесь мы создаём все процессы, которые нужны прямо сейчас.
    urls_to_start = get_target_pool()
    for url in urls_to_start:
        p = Process(target=keep_radio_alive, args=(url,))
        p._start_time = time.time()
        p.start()
        processes.append(p)

    # 🔸 ПУНКТ Б: Цикл обслуживания.
    # Мы проверяем состояние процессов каждые 60 секунд.
    # Мы ничего не убиваем вручную. Мы ждём, пока они умрут сами.
    while True:
        # Проверка состояния процессов.
        alive_new = []  # Сюда будут попадать живые процессы.

        # Проходимся по всем запущенным ранее процессам.
        for p in processes:
            # exitcode будет None у живых процессов.
            # Как только он становится числом (например, 0 или 1), процесс мёртв.
            if p.exitcode is None:
                # Процесс ещё работает.
                alive_new.append(p)
            else:
                # Процесс завершился своей смертью.
                pass  # Ничего не делаем, он уже отработал своё время.

        # Обновляем список активных процессов.
        processes = alive_new

        # 🔸 ПУНКТ В: Постепенное заполнение пула.
        # Если кто-то из старых процессов умер, нам нужно запустить замену.
        needed = len(get_target_pool()) - len(processes)

        # Защита от бесконечного цикла создания новых процессов ночью.
        # Когда нагрузка падает ниже 1, нужен может быть отрицательным.
        if needed > 0 and len(processes) < len(RADIOS):  # Не пытаемся создать больше, чем есть в списке
            # Берём оставшиеся URL из пула.
            # Мы используем срезы, чтобы не повторять одни и те же потоки подряд.
            # Если пул закончился, начинаем сначала.
            pool = get_target_pool()
            offset = len(processes) % len(pool)
            urls_to_start = pool[offset : offset + needed]
            
            for url in urls_to_start:
                p = Process(target=keep_radio_alive, args=(url,))
                p._start_time = time.time()
                p.start()
                processes.append(p)

        # Время сна между циклами проверки.
        # Можно увеличить до 300 сек (5 минут).
        time.sleep(60)
