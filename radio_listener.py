import socket
import time
from multiprocessing import Process # Многопроцессность для запуска нескольких станций параллельно
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
SESSION_DURATION_MAX = 400   # Максимум ~6 мин 40 сек

def keep_radio_alive(url):
    """Функция виртуального слушателя через низкоуровневый сокет."""
    
    headers = (
        f"GET / HTTP/1.1\r\n"
        f"Host: listen7.myradio24.com\r\n"
        f"Icy-MetaData: 1\r\n"
        f"User-Agent: Mozilla/5.0 Chrome/129 Safari/537.36\r\n"
        f"Referer: {REFERER_URL}\r\n"
        "\r\n"
    )

    while True:  
        session_duration = random.randint(SESSION_DURATION_MIN, SESSION_DURATION_MAX)
        
        try:
            with socket.create_connection(("listen7.myradio24.com", 80)) as sock:
                # Отправляем запрос вручную
                sock.sendall(headers.encode())
                
                start_time = time.time()

                #### ОПТИМИЗАЦИЯ ПОД ОБЛАЧНЫЕ СЕРВЕРЫ ####
                # Читаем всего 1 байт каждые 1–2 секунды.
                # Это поддерживает соединение активным без буферизации данных.
                while int(time.time() - start_time) < session_duration:
                    # Пытаемся прочитать один байт
                    data = sock.recv(1)
                    
                    # Если пришли метаданные (обычно начинаются с ICY), просто пропускаем их
                    if not data or data.startswith(b'ICY'):
                        continue

                    # Пауза между чтением байтов для экономии CPU
                    time.sleep(random.uniform(1, 2))

        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] Connection error for {url}: {e}. Reconnecting...")
        
        finally:
            print(f"[{time.strftime('%H:%M:%S')}] Session ended after {session_duration}s for {url}.")

if __name__ == '__main__':
    processes = []
    
    # Запускаем ВСЕХ слушателей ОДНОВРЕМЕННО через процессы
    # Каждый процесс будет жить своей жизнью благодаря циклу while True внутри функции
    for radio_url in RADIOS:
        p = Process(target=keep_radio_alive, args=(radio_url,))
        p.start()
