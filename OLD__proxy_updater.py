import requests
from urllib.parse import urlparse, urlunparse
import random
import argparse
import time


# Константы для проверки потока
STREAM_URL = 'https://listen7.myradio24.com/iridium'
STREAM_TIMEOUT_CONNECT = 5   # Таймаут подключения
STREAM_TIMEOUT_READ = 60     # Время скачивания первых данных (увеличено)
STREAM_MIN_SPEED = 1         # Минимальная скорость в KB/s

def check_proxy(api_key: str) -> dict | None:
    """
    Проверяет один узел по API-ключу Proxies.IO.
    
    Возвращает словарь с рабочим URL или None, если проверка провалилась.
    """
    # Генерируем случайный порт из диапазона резидентских прокси
    port = random.randint(80_000, 99_999)

    # Формируем полный URL прокси-сервера
    auth = f"{api_key}:"
    netloc = f"global.proxies.io:{port}"
    scheme = "http"

    # Создаём сессию с одним общим соединением
    session = requests.Session()
    proxies = {
        "http": f"{scheme}://{auth}@{netloc}",
        "https": f"{scheme}://{auth}@{netloc}"
    }

    try:
        # Шаг 1: Получаем реальный внешний IP-адрес текущего узла
        ip_response = session.get(
            "https://api.ipify.org",
            timeout=STREAM_TIMEOUT_CONNECT,
            proxies=proxies
        )
        
        if not ip_response.ok or not ip_response.text.strip():
            print(f"[FAIL] {netloc} - Couldn't get external IP")
            return None

        real_ip = ip_response.text.strip()  # Реальный IP узла

        # Заменим домен global.proxies.io на реальный IP
        parsed_netloc = urlparse(netloc)
        new_netloc = parsed_netloc._replace(hostname=real_ip).geturl()

        # Шаг 2: Проверка потока музыки на найденном реальном IP
        with session.get(STREAM_URL, stream=True, timeout=(STREAM_TIMEOUT_CONNECT, STREAM_TIMEOUT_READ), proxies=proxies) as r:
            start_time = time.time()
            
            # Читаем первые данные потока
            data_chunk = next(r.iter_content(chunk_size=10 * 1024))
            elapsed = time.time() - start_time

            speed_kbps = len(data_chunk) / elapsed / 1024

            if not data_chunk:
                print(f"[FAIL] {new_netloc} - No data received from stream")
                return None

            if speed_kbps < STREAM_MIN_SPEED:
                print(f"[FAIL] {new_netloc} - Speed too low ({speed_kbps:.2f} KB/s)")
                return None

            result = {'url': f"{scheme}://{auth}@{new_netloc}"}
            print(f"[OK] Added node: {result['url']} (Speed: {speed_kbps:.2f} KB/s)")
            return result

    except Exception as e:
        print(f"[FAIL] {netloc} - Error: {e}")
        return None
    finally:
        session.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Residental Proxy Updater for MyRadio Listener")
    parser.add_argument("--count", type=int, default=50, help="Number of ports to generate and test")
    args = parser.parse_args()

    api_key = input("Enter your Proxies.IO API key: ")

    working_proxies = []

    for _ in range(args.count):
        result = check_proxy(api_key)
        if result is not None:
            working_proxies.append(result["url"])

    # Сохранение списка рабочих узлов
    with open("working_proxies.txt", "w") as file:
        for p in working_proxies:
            file.write(p + "\n")
