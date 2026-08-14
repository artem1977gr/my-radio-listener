import requests
import time
from multiprocessing import Process # Многопроцессность для запуска нескольких станций параллельно
import random  # Для генерации случайной задержки между запуском процессов


# Глобальные настройки
SESSION_DURATION_SECONDS = 345  # Длительность одной сессии (в секундах). Это ~5 мин 45 сек.

# Список URL радиостанций с нужным количеством виртуальных слушателей
RADIOS = (
    ['https://listen7.myradio24.com/sintezi'] * 4 +     # Четыре слушателя
    ['https://listen7.myradio24.com/sintezi_128'] * 2 +
    ['https://listen7.myradio24.com/rockataka'] * 4 +   # Исправлено myradio26 -> myradio24!
    ['https://listen7.myradio24.com/rockataka_128'] * 2,
    ['https://listen7.myradio24.com/iridium'] * 2,
    ['https://listen7.myradio24.com/nevermind'] * 2
)


def keep_radio_alive(url):
    """Функция виртуального слушателя для одной радиостанции."""
    
    print(f"[{time.strftime('%H:%M:%S')}] Starting listener for {url}...")

    headers = {
        'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128.0 Safari/537.36",
        
        # ВАЖНО: Указываем ТВОЙ тестовый сайт!
        # Сервер будет считать, что слушатель пришёл именно оттуда.
        'Referer': 'https://radio.art-test-1.store',
        
        # Для получения названий треков из метаданных потока
        'Icy-MetaData': '1'
    }

    try:
        with requests.get(url, stream=True, timeout=20, headers=headers) as response:
            response.raise_for_status()
            
            start_time = time.time() 

            #### ВАЖНЫЙ МОМЕНТ ####
            # Мы читаем chunk, но ничего с ним не делаем.
            # Просто поддерживаем соединение активным.
            buffer_size = 65536  
            
            for _ in response.iter_content(chunk_size=buffer_size): # Используем _, т.к. chunk нам больше не нужен
                if int(time.time() - start_time) >= SESSION_DURATION_SECONDS:
                    break

                # Пауза ровно на длительность сессии (~5:45)
                time.sleep(SESSION_DURATION_SECONDS)

    except requests.exceptions.RequestException as e:
        print(f"Connection error: {e}. Reconnecting immediately...") 
        
    finally:
        print(f"[{time.strftime('%H:%M:%S')}] Listener for {url} terminated.")


if __name__ == '__main__':
    while True:  # Главный цикл работы скрипта
        processes = []
        
        # ⚠️ ИСПРАВЛЕНИЕ ЗДЕСЬ! Разворачиваем RADIOS, чтобы получить каждую ссылку отдельно.
        # Раньше ты передавал весь подсписок [url] * N как один аргумент.
        for i, radio_url in enumerate(RADIOS):
            p = Process(target=keep_radio_alive, args=(radio_url,))
            
            delay = random.randint(15, 30)  # Случайная задержка при старте каждого нового слушателя
            print(f"[{time.strftime('%H:%M:%S')}] Запуск {i+1}/{len(RADIOS)} через ~{delay} сек.: {radio_url}")
            time.sleep(delay)
            p.start()
            processes.append(p)

        # После того как ВСЕ процессы запущены, мы ждём их завершения,
        # чтобы потом снова запустить новый набор процессов по кругу.
        for process in processes:
            process.join()  # Блокируем выполнение основного потока, пока не завершится процесс
