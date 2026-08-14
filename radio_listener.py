import requests
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
SESSION_DURATION_MIN = 30   # Минимум 5 минут
SESSION_DURATION_MAX = 900   # Максимум ~6 мин 40 сек

def keep_radio_alive(url):
    """Функция виртуального слушателя."""
    
    headers = {
        'User-Agent': (
            "Mozilla/5.0 Chrome/129 Safari/537.36"
        ),
        'Referer': REFERER_URL,
        'Icy-MetaData': '1',
        #### ВАЖНОЕ ИЗМЕНЕНИЕ ####
        # Это ключ к решению проблемы исчезновения слушателей.
        # Мы говорим серверу держать соединение открытым.
        'Connection': 'Keep-Alive'
    }

    while True:  
        session_duration = random.randint(SESSION_DURATION_MIN, SESSION_DURATION_MAX)
        
        try:
            with requests.get(
                url, stream=True, timeout=20, headers=headers,
                #### ЕЩЁ ОДНА ОПТИМИЗАЦИЯ ###
                # По умолчанию requests буферизует данные во внутреннем объекте Response.
                # Чтобы снизить нагрузку на память, используем raw-соединение.
                allow_redirects=False
            ) as response:
                response.raw.decode_content = False # Отключаем декодирование
                
                start_time = time.time()

                #### ЧТЕНИЕ БЕЗ НАКОПЛЕНИЯ ДАННЫХ В ПАМЯТИ ####
                # Читаем по одному байту напрямую из сырого потока.
                # Это поддерживает соединение активным, но не нагружает память.
                while int(time.time() - start_time) < session_duration:
                    data = response.raw.read(1)
                    
                    # Если пришли метаданные или конец файла
                    if not data or data.startswith(b'ICY'):
                        continue

                    # Пауза между чтением байтов для экономии CPU
                    time.sleep(random.uniform(0.5, 1))

        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] Connection error for {url}: {e}. Reconnecting...")
        
        finally:
            print(f"[{time.strftime('%H:%M:%S')}] Session ended after {session_duration}s for {url}.")

if __name__ == '__main__':
    processes = []
    
    # Запускаем ВСЕХ слушателей ОДНОВРЕМЕННО через процессы
    for radio_url in RADIOS:
        p = Process(target=keep_radio_alive, args=(radio_url,))
        p.start()
