import requests
import time
from multiprocessing import Process
import random


# Глобальные настройки
SESSION_DURATION_SECONDS = 345  # ~5 минут 45 секунд

# ⚠️ СЛЕДУЮЩИЙ БЛОК НЕ ИЗМЕНЯЙ!
# Мы создаем "вложенные" списки для каждого количества слушателей,
# чтобы потом их развернуть и запустить каждый элемент отдельно.
RADIOS = [
    *(['https://listen7.myradio24.com/sintezi'] * 4),
    *(['https://listen7.myradio24.com/sintezi_128'] * 2),
    *(['https://listen7.myradio24.com/rockataka'] * 4),
    *(['https://listen7.myradio24.com/rockataka_128'] * 2),
    *(['https://listen7.myradio24.com/iridium'] * 2),
    *(['https://listen7.myradio24.com/nevermind'] * 2),
]
# Теперь RADIOS — это плоский список из 16 отдельных строк-URL.

def keep_radio_alive(url):
    print(f"[{time.strftime('%H:%M:%S')}] Starting listener for {url}...")
    
    headers = {
        'User-Agent': "Mozilla/5.0 Chrome/128",
        'Referer': 'https://radio.art-test-1.store',
        'Icy-MetaData': '1'
    }

    try:
        with requests.get(url, stream=True, timeout=20, headers=headers) as response:
            response.raise_for_status()
            
            start_time = time.time() 

            #### ВАЖНЫЙ МОМЕНТ ####
            # Поддерживаем соединение активным ровно SESSION_DURATION_SECONDS.
            buffer_size = 65536  
            
            for _ in response.iter_content(chunk_size=buffer_size): # Используем _, т.к. chunk нам больше не нужен
                if int(time.time() - start_time) >= SESSION_DURATION_SECONDS:
                    break

                # Пауза на всю длительность сессии (~5:45).
                # Благодаря этому CPU почти не нагружается.
                time.sleep(SESSION_DURATION_SECONDS)

    except requests.exceptions.RequestException as e:
        print(f"Connection error: {e}. Reconnecting immediately...") 
        
    finally:
        print(f"[{time.strftime('%H:%M:%S')}] Listener for {url} terminated.")


if __name__ == '__main__':
    while True:  # Главный цикл работы скрипта
        processes = []
        
        # ❗ ОЧЕНЬ ВАЖНО! ❗
        # Здесь мы перебираем КАЖДЫЙ ЭЛЕМЕНТ списка RADIOS.
        # Раньше у тебя был подсписок [url] * N, который передавался целиком.
        # Сейчас url — это одна строка.
        for i, radio_url in enumerate(RADIOS):
            p = Process(target=keep_radio_alive, args=(radio_url,))
            
            delay = random.randint(15, 30)  # Случайная задержка при старте
            print(f"[{time.strftime('%H:%M:%S')}] Запуск {i+1}/{len(RADIOS)} через ~{delay} сек.: {radio_url}")
            time.sleep(delay)
            p.start()
            processes.append(p)

        # Ждем завершения ВСЕХ запущенных процессов.
        # После этого скрипт начнет новый круг запуска.
        for process in processes:
            process.join()
