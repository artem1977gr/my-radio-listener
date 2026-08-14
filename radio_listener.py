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
SESSION_DURATION_MIN = 300   # Минимум 5 минут
SESSION_DURATION_MAX = 900   # Максимум ~15 мин (можно увеличить!)
READ_TIMEOUT_SEC = 5        # Ключевое изменение!


def keep_radio_alive(url):
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
                # ⚡️ ВАЖНОЕ ИЗМЕНЕНИЕ: устанавливаем небольшой таймаут на чтение
                sock.settimeout(READ_TIMEOUT_SEC)  # Чтение каждые 5 секунд

                sock.sendall(headers.encode())
                
                # Сначала получаем ответ сервера и парсим его заголовки
                response_headers = b""
                while True:
                    chunk = sock.recv(4096) # Читаем порциями по 4 КБ
                    if not chunk:
                        break
                    response_headers += chunk
                    
                    # Ждём появления пустой строки, которая завершает заголовки ответа
                    if b"\r\n\r\n" in response_headers:
                        break

                start_time = time.time()

                #### НАДЕЖНЫЙ СПОСОБ ПОДДЕРЖАНИЯ СОЕДИНЕНИЯ ####
                # Мы просто пытаемся читать данные небольшими кусками каждые READ_TIMEOUT_SEC секунд.
                # Если данных нет — сокет вернёт исключение TimeoutError, которое мы игнорируем.
                # За счёт этого сервер видит стабильное потребление трафика,
                # а наш скрипт практически не нагружает CPU и память.
                while int(time.time() - start_time) < session_duration:
                    try:
                        # Пытаемся прочитать данные (не важно сколько)
                        sock.recv(1024)
                    except socket.timeout:
                        pass  # Игнорируем отсутствие данных
                    except Exception as e:
                        print(f"[{time.strftime('%H:%M:%S')}] Read error for {url}: {e}")
                        break

        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] Connection error for {url}: {e}. Reconnecting...")
        
        finally:
            print(f"[{time.strftime('%H:%M:%S')}] Session ended after {session_duration}s for {url}.")


if __name__ == "__main__":
    processes = []
    for radio_url in RADIOS:
        p = Process(target=keep_radio_alive, args=(radio_url,))
        p.start()
