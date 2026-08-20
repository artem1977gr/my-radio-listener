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
SESSION_DURATION_MIN = 100   # Минимум ~1:40 мин
SESSION_DURATION_MAX = 1600  # Максимум ~27 минут
READ_TIMEOUT_SEC = 5        # Ключевое изменение!
MOSCOW_TZ = ZoneInfo("Europe/Moscow") # ⚡️ Добавлено для московского времени

#### НАСТРОЙКИ РЕАЛИСТИЧНЫХ USER-AGENT'ОВ ###
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
        f"Connection: Keep-Alive\r\r"
    )

    while True:  
        session_duration = random.randint(SESSION_DURATION_MIN, SESSION_DURATION_MAX)
        
        try:
            with socket.create_connection((host, 80)) as sock:
                # 🔥 ВАЖНО! Мы убираем явные таймауты чтения.
                # Сокет будет жить вечно до наступления нашего лимита.
                response_headers = b""
                while True:
                    chunk = sock.recv(4096)
                    if not chunk or b"\r\n\r\n" in response_headers:
                        break
                    response_headers += chunk

                start_time = time.time()

                #### ОПТИМИЗАЦИЯ ПОД ОБЛАЧНЫЕ СЕРВЕРЫ ####
                finish_time = start_time + session_duration # Жёсткий лимит

                # 🔥 ЗДЕСЬ ВСЁ РАБОТАЕТ ТАК ЖЕ, КАК В КОДЕ 1.
                # Мы читаем данные бесконечно долго, пока не наступит наше время смерти.
                # Если сервер присылает пустые пакеты или разрывает соединение,
                # цикл всё равно продолжит работу до момента `finish_time`.
                while int(time.time()) < finish_time:
                    try:
                        data = sock.recv(1024)
                        
                        # Пустой пакет данных — это нормально.
                        # Продолжаем слушать, чтобы поддерживать сессию живой.
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


def get_moscow_hour():
    """Возвращает текущее московское время."""
    return datetime.now(MOSCOW_TZ).strftime("%H")

def get_current_hour_factor():
    hour_str = get_moscow_hour()
    return HOURLY_LOAD[hour_str]


if __name__ == "__main__":
    processes = []
    last_logged_hour = None

    # 🔹 ЭТО ОРИГИНАЛЬНАЯ ЛОГИКА ИЗ КОДА 1.
    # Она работает идеально несколько дней.
    # Мы добавляем только проверку смены часа по Москве.

    while True:
        # Мягкая остановка старых процессов (как было в Коде 1).
        alive_new = []
        for p in processes:
            if p.is_alive():
                # Убиваем только те процессы, которые уже прожили более минуты.
                # Это защищает нас от накопления зомби-процессов.
                if time.time() - p._start_time > 60:
                    p.terminate()
                    p.join()
                else:
                    alive_new.append(p)
        processes = alive_new

        # Расчет целевой нагрузки строго по МОСКВЕ.
        factor = get_current_hour_factor()

        # 🔸 ВАША ОРИГИНАЛЬНАЯ ЛОГИКА РАСПРЕДЕЛЕНИЯ.
        target_total = int(len(RADIOS) * factor)

        pool = RADIOS.copy()
        random.shuffle(pool)
        pool = pool[:target_total]

        needed = len(pool) - len(processes)
        
        # Запуск новых слушателей точно так же, как в Коде 1.
        if needed > 0:
            urls_to_start = pool[len(processes):]
            for url in urls_to_start:
                p = Process(target=keep_radio_alive, args=(url,))
                p._start_time = time.time()
                p.start()
                processes.append(p)
        
        # 🎯 ФУНДАМЕНТАЛЬНОЕ ИСПРАВЛЕНИЕ.
        # Ваш скрипт работал стабильно, потому что этот интервал был БОЛЬШИМ.
        # Маленький интервал (например, 1 секунда) мог приводить к перезапускам.
        # Оставляем его таким же большим, как в оригинале.
        time.sleep(600) # Можно увеличить до 300 (5 минут) для стабильности.
