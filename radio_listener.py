import socket
import time
from urllib.parse import urlparse  # Для правильной работы с URL
from multiprocessing import Process
import random
import os


# Глобальные настройки
RADIOS = [
    *(['https://listen7.myradio24.com/sintezi'] * 20),
    *(['https://listen7.myradio24.com/rockataka'] * 5), 
    *(['https://listen7.myradio24.com/iridium'] * 3),
    *(['https://listen7.myradio24.com/nevermind'] * 5)
]
REFERER_URL = "https://radio.art-test-1.store"
SESSION_DURATION_MIN = 100   # Минимум ~1:40 мин
SESSION_DURATION_MAX = 1600  # Максимум ~27 минут
READ_TIMEOUT_SEC = 5        # Ключевое изменение!


#### НАСТРОЙКИ РЕАЛИСТИЧНЫХ USER-AGENT'ОВ ###
PLATFORM_WEIGHTS = [  # Веса для платформ
    {"os": "Windows", "version": f"NT {random.randint(10, 11)}.0; Win64; x64", "weight": 0.1},  # Стационарные ПК
    {"os": "Mac OS X", "version": f"{random.randint(10, 15)}_{random.randint(9, 15)}_{random.randint(5, 9)}", "weight": 0.05},
    
    # Мобильная аудитория (большинство пользователей)
    {"os": "Android", "version": str(random.randint(10, 13)), "arch": f"Samsung Galaxy S{random.randint(9, 23)}", "weight": 0.3},
    {"os": "iPhone", "version": f"{random.randint(14, 17)}_{random.randint(0, 9)}", "model": f"iPhone{random.randint(10, 14)},2", "weight": 0.2},
    
    # Другие десктопы
    {"os": "Linux", "version": "x86_64", "weight": 0.05},
    {"os": "X11", "version": f"Ubuntu; Linux x86_64", "weight": 0.05}
]

BROWSER_WEIGHTS = [  # Веса для браузеров
    {"name": "Chrome", "version": f"{random.randint(110, 130)}.0.{random.randint(100, 999)}.0", "weight": 0.6},  # Доминирует
    {"name": "Firefox", "version": f"{random.randint(100, 120)}.0", "weight": 0.2},
    {"name": "Safari", "version": f"605.1.{random.randint(10, 20)}", "weight": 0.1},
    {"name": "Edge", "version": f"1{random.randint(0,3)}0.0.{random.randint(100, 999)}", "weight": 0.05},
    {"name": "Opera", "version": f"{random.randint(95, 105)}.0.0.{random.randint(10, 99)}", "weight": 0.05}
]


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


def get_random_proxy():
    """
    Возвращает случайный работающий URL.
    Поддерживает гибридный режим: 50% Москва (Amvera), 50% из working_proxies.txt
    """

    HYBRID_MODE = bool(os.getenv("USE_HYBRID_PROXIES"))

    default_moscow_ip = (
        "http://[user1234567890abcdefg:hijklmnopqrstuvwxyz]"
        "@listen7.myradio24.com:80"
    )  # Дефолтный Moscow IP от Amvera

    if not HYBRID_MODE:
        proxy_list_file = os.getenv("PROXY_LIST_FILE", "./working_proxies.txt")
        
        try:
            with open(proxy_list_file) as f:
                proxies = [line.strip() for line in f if line.strip()]
                return random.choice(proxies)
        except Exception as e:
            print(f"[ERROR] Error loading proxy list: {e}")
            return default_moscow_ip
    else:
        use_custom_proxy = random.random() < 0.5  # Вероятность 50%

        if use_custom_proxy:
            # Загружаем только те адреса, которые реально существуют
            try:
                with open("./working_proxies.txt") as f:
                    proxies = [line.strip() for line in f if line.strip()]
                    return random.choice(proxies)
            except FileNotFoundError:
                pass  # Используем Москву по умолчанию

        # Возвращаем дефолтный московский IP
        return default_moscow_ip


def keep_radio_alive(url):
    parsed_url = urlparse(url)
    
    # Разделяем хост и порт стриминг-сервера
    stream_host = parsed_url.netloc.split(':')[0] 
    path = parsed_url.path  

    #### КЛЮЧЕВОЙ МОМЕНТ ####
    # Выбираем случайный прокси (гибридный режим)
    proxy_url = get_random_proxy()

    # Парсим его на части
    proxy_parsed = urlparse(proxy_url)
    proxy_host = proxy_parsed.hostname
    proxy_port = int(proxy_parsed.port or 80)  # По умолчанию HTTP-порт

    # Логин и пароль должны быть экранированы квадратными скобками!
    auth_header = f"{proxy_url}\r\n"  # Передаём полный URL узла с логином/паролем

    headers = ""

    # Определяем тип соединения в зависимости от схемы потока
    if parsed_url.scheme == "http":
        # Простой GET-запрос для HTTP-потоков
        headers += f"GET {url} HTTP/1.1\r\n"
    else:  # https или пустой (тогда тоже считаем за https)
        # Метод CONNECT нужен для установления туннеля через прокси
        headers += f"CONNECT {parsed_url.netloc} HTTP/1.1\r\n"

    # Общие заголовки
    headers += (
        f"Host: {stream_host}\r\n"
        f"{auth_header}"
        f"Icy-MetaData: 1\r\n"
        f"User-Agent: {generate_user_agent()}\r\n"
        f"Referer: {REFERER_URL}\r\n"
        f"Connection: Keep-Alive\r\n"
        "\r\n"
    )

    while True:  
        session_duration = random.randint(SESSION_DURATION_MIN, SESSION_DURATION_MAX)
        
        try:
            #### ПОДКЛЮЧАЕМСЯ НЕ К СТРИМИНГУ, А К ПРОКСИ-УЗЛУ ###
            with socket.create_connection((proxy_host, proxy_port)) as sock:
                sock.settimeout(READ_TIMEOUT_SEC)  # Чтение каждые 5 секунд

                # Отправка запроса
                sock.sendall(headers.encode())
                
                response_headers = b""
                while True:
                    chunk = sock.recv(4096)
                    if not chunk or b"\r\n\r\n" in response_headers:
                        break
                    response_headers += chunk

                # Для HTTPS мы ждём ответ на CONNECT
                if parsed_url.scheme == "https":
                    status_line = response_headers.decode().split("\n")[0]
                    print(f"[DEBUG] Proxy response for {proxy_url}: {status_line}")
                    
                    # Если прокси отказал в соединении, прерываем цикл
                    if not status_line.startswith("HTTP/1.1 2"):
                        raise Exception(f"Proxy refused connection: {status_line}")

                start_time = time.time()

                #### ОПТИМИЗАЦИЯ ПОД ОБЛАЧНЫЕ СЕРВЕРЫ ####
                while int(time.time() - start_time) < session_duration:
                    try:
                        sock.recv(1024)
                    except socket.timeout:
                        pass
                    except Exception as e:
                        print(f"[{time.strftime('%H:%M:%S')}] Read error for {url}: {e}")
                        break

        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] Connection error for {url}: {e}. Reconnecting...")
        
        finally:
            elapsed = int(time.time() - start_time)
            print(f"[{elapsed//60}:{elapsed%60:02d}] Listener on {proxy_url} ended.")


if __name__ == "__main__":
    processes = []
    for radio_url in RADIOS:
        p = Process(target=keep_radio_alive, args=(radio_url,))
        p.start()
