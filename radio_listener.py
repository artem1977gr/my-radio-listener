import requests
import subprocess
import time
from multiprocessing import Process # Многопроцессность для запуска нескольких станций параллельно
import random  # Для генерации случайной задержки между запуском процессов


# Глобальные настройки
SESSION_DURATION_SECONDS = 345  # Длительность одной сессии (в секундах). Это 5 мин 45 сек.

# Список URL радиостанций с нужным количеством виртуальных слушателей
RADIOS = (
    ['https://listen7.myradio24.com/sintezi'] * 4,
    ['https://listen7.myradio24.com/sintezi_128'] * 2,
    ['https://listen7.myradio26.com/rockataka'] * 4,
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

            player = subprocess.Popen(
                ['mpv', '--no-video', '--quiet', '-'],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
            buffer_size = 65536  
            
            #### ВАЖНЫЙ МОМЕНТ ####
            # Ты читаешь chunk, отправляешь его в mpv, а затем засыпаешь на сессию.
            # Это позволяет тебе экономить CPU до минимума.
            for chunk in response.iter_content(chunk_size=buffer_size):
                if not chunk or int(time.time() - start_time) >= SESSION_DURATION_SECONDS:
                    break

                # Передаём данные в mpv
                try:
                    player.stdin.write(chunk)
                except BrokenPipeError:
                    break

                # Пауза ровно на длительность сессии (~5:45)
                time.sleep(SESSION_DURATION_SECONDS)

                # Дополнительная проверка: если mpv завершился сам
                if player.poll() is not None:
                    break

    except requests.exceptions.RequestException as e:
        print(f"Connection error: {e}. Reconnecting immediately...") 
        
    finally:
        # Завершаем процесс плеера
        if 'player' in locals() and player.poll() is None:
            player.terminate()
            try:
                player.wait(timeout=5)
            except subprocess.TimeoutExpired:
                player.kill()
        print(f"[{time.strftime('%H:%M:%S')}] Listener for {url} terminated.")


if __name__ == '__main__':
    while True:  # Главный цикл работы скрипта
        processes = []
        
        # Запускаем виртуальных слушателей ПО ОЧЕРЕДИ со СЛУЧАЙНОЙ задержкой
        for i, radio_url in enumerate(RADIOS):
            p = Process(target=keep_radio_alive, args=(radio_url,))
            
            # Генерируем случайную задержку от 15 до 30 секунд для КАЖДОГО нового слушателя
            delay = random.randint(15, 30)  

            print(f"[{time.strftime('%H:%M:%S')}] Запуск {i+1}/{len(RADIOS)} через ~{delay} сек.: {radio_url}")
            time.sleep(delay)  # Ждём перед запуском процесса
            p.start()
            processes.append(p)

        # После того как ВСЕ процессы запущены, мы ждём их завершения,
        # чтобы потом снова запустить новый набор процессов по кругу.
        for process in processes:
            process.join()  # Блокируем выполнение основного потока, пока не завершится процесс
