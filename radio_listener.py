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
SESSION_DURATION_MIN = 600
SESSION_DURATION_MAX = 1200

def keep_radio_alive(url):
    parsed_url = urlparse(url)
    host = parsed_url.netloc.split(':')[0] # Получаем только домен без порта
    path = parsed_url.path  # Важно! Теперь это /sintezi, а не просто sintezi

    headers = (
        f"GET {path} HTTP/1.1\r\n"  # Используем правильный путь
        f"Host: {host}\r\n"
        f"Icy-MetaData: 1\r\n"
        f"User-Agent: Mozilla/5.0 Chrome/129 Safari/537.36\r\n"
        f"Referer: {REFERER_URL}\r\n"
        #### КЛЮЧЕВЫЙ МОМЕНТ ####
        # Обязательно указываем, чтобы сервер держал соединение открытым.
        f"Connection: Keep-Alive\r\n"
        "\r\n"
    )

    while True:  
        session_duration = random.randint(SESSION_DURATION_MIN, SESSION_DURATION_MAX)
        
        try:
            with socket.create_connection((host, 80)) as sock:
                sock.sendall(headers.encode())
                
                start_time = time.time()

                while int(time.time() - start_time) < session_duration:
                    data = sock.recv(1)
                    if not data or data.startswith(b'ICY'):
                        continue
                    time.sleep(random.uniform(1, 2))

        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] Connection error for {url}: {e}. Reconnecting...")
        
        finally:
            print(f"[{time.strftime('%H:%M:%S')}] Session ended after {session_duration}s for {url}.")

if __name__ == "__main__":
    processes = []
    for radio_url in RADIOS:
        p = Process(target=keep_radio_alive, args=(radio_url,))
        p.start()
