import requests
import time
from multiprocessing import Process # Многопроцессность для запуска нескольких станций параллельно
import random


# Глобальные настройки
RADIOS = [
    *(['https://listen7.myradio24.com/sintezi'] * 4),
    *(['https://listen7.myradio24.com/sintezi_128'] * 2),
    *(['https://listen7.myradio24.com/rockataka'] * 4), # Исправлено: теперь myradio24!
    *(['https://listen7.myradio24.com/rockataka_128'] * 2),
    *(['https://listen7.myradio24.com/iridium'] * 2),
    *(['https://listen7.myradio24.com/nevermind'] * 2)
]
REFERER_URL = "https://radio.art-test-1.store"
SESSION_DURATION_MIN = 300   # Минимум 5 минут
SESSION_DURATION_MAX = 900   # Максимум ~6 мин 40 сек

def keep_radio_alive(url):
    """Функция виртуального слушателя для одной радиостанции."""
    
    headers = {
        'User-Agent': (
            "Mozilla/5.0 Chrome/129 Safari/537.36"
        ),
        'Referer': REFERER_URL,
        'Icy-MetaData': '1'
    }

    while True:  # Бесконечный цикл жизни одного слушателя
        
        session_duration = random.randint(SESSION_DURATION_MIN, SESSION_DURATION_MAX) 
        
        try:
            with requests.get(url, stream=True, timeout=20, headers=headers) as response:
                response.raise_for_status()
                
                start_time = time.time() 

                #### ОПТИМИЗАЦИЯ ####
                # Читаем очень маленькие порции (по 1 байту).
                # Это поддерживает соединение активным, но не нагружает память.
                for _ in response.iter_content(chunk_size=1):  
                    if int(time.time() - start_time) >= session_duration:
                        break

        except Exception as e:
            print(f"Connection error: {e}. Reconnecting immediately...")
        
        finally:
            print(f"[{time.strftime('%H:%M:%S')}] Session ended after {session_duration}s for {url}.")

if __name__ == '__main__':
    processes = []
    
    # Запускаем ВСЕХ слушателей ОДНОВРЕМЕННО через процессы
    # Каждый процесс будет жить своей жизнью благодаря циклу while True внутри функции
    for radio_url in RADIOS:
        p = Process(target=keep_radio_alive, args=(radio_url,))
        p.start()
