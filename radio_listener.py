import socket
import time
from urllib.parse import urlparse # Для правильной работы с URL
from multiprocessing import Process
import random


# Глобальные настройки
RADIOS = [
    *(['https://listen7.myradio24.com/sintezi'] * 4),
    *(['https://listen7.myradio24.com/sintezi_128'] * 2),
    *(['https://listen7.myradio24.com/rockataka'] * 4), 
    *(['https://listen7.myradio24.com/rockataka_128'] * 2),
    *(['https://listen7.myradio24.com/iridium'] * 2),
    *(['https://listen7.myradio24.com/nevermind'] * 2)
]
REFERER_URL = "https://radio.art-test-1.store"
SESSION_DURATION_MIN = 600   # Минимум 10 минут
SESSION_DURATION_MAX = 1200  # Максимум ~20 мин


def keep_radio_alive(url):
    """Функция виртуального слушателя."""
    
    parsed_url = urlparse(url)
    host = parsed_url.netloc.split(':')[0] # Получаем только домен без порта
    path = parsed_url.path  

    headers = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: {host}\r\n"
        #### КЛЮЧЕВОЙ МОМЕНТ ####
        # Обязательно включаем получение метаданных!
        # Сервер будет отправлять их примерно раз в минуту.
        f"Icy-MetaData: 1\r\n"
        
        f"User-Agent: Mozilla/5.0 Chrome/129 Safari/537.36\r\n"
        f"Referer: {REFERER_URL}\r\n"
        f"Connection: Keep-Alive\r\n"
        "\r\n"
    )

    while True:  
        session_duration = random.randint(SESSION_DURATION_MIN, SESSION_DURATION_MAX)
        
        try:
            with socket.create_connection((host, 80)) as sock:
                sock.sendall(headers.encode())
                
                # Сначала получаем ответ сервера и парсим его заголовки
                response_headers = b""
                while True:
                    chunk = sock.recv(4096) # Читаем порциями по 4 КБ
                    response_headers += chunk
                    
                    # Ждём появления пустой строки, которая завершает заголовки ответа
                    if b"\r\n\r\n" in response_headers:
                        break

                # Парсинг заголовка icymetaint
                meta_int_str = [line for line in response_headers.decode().split("\r\n") 
                                if line.lower().startswith("icy-metaint")]
                # Если сервер не прислал этот заголовок, ставим стандартный интервал ~25 KB
                meta_interval = int(meta_int_str[0].split(":")[1]) if meta_int_str else 25600

                print(f"[{time.strftime('%H:%M:%S')}] Connected to {url} ({meta_interval})") # <--- Добавил вывод названия

                start_time = time.time()

                #### НАДЕЖНЫЙ СПОСОБ ПОДДЕРЖАНИЯ СОЕДИНЕНИЯ ####
                # Мы ждём прихода блоков метаданных (~раз в минуту).
                # Это гарантирует активность соединения без лишнего потребления ресурсов.
                while int(time.time() - start_time) < session_duration:
                    # Читаем ровно столько, сколько нужно для получения одного блока метаданных + небольшой запас
                    sock.recv(meta_interval + 256)
                    # Пауза ~1 сек для экономии CPU
                    time.sleep(random.uniform(0.8, 1.2))

        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] Connection error for {url}: {e}. Reconnecting...")
        
        finally:
            #### ИСПРАВИЛА ЭТУ СТРОКУ ###
            print(f"[{time.strftime('%H:%M:%S')}] Session ended after {session_duration}s for {url}.")


if __name__ == "__main__":
    processes = []
    for radio_url in RADIOS:
        p = Process(target=keep_radio_alive, args=(radio_url,))
        p.start()
