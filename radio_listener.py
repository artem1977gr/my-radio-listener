import requests
import subprocess
import time
from multiprocessing import Process

# Глобальные настройки
RADIOS = [
    'https://listen7.myradio24.com/sintezi',
    'https://listen7.myradio24.com/sintezi_128',
    'https://listen7.myradio24.com/rockataka',
    'https://listen7.myradio24.com/rockataka_128',
    'https://listen7.myradio24.com/iridium',
    'https://listen7.myradio24.com/nevermind'
]
SESSION_DURATION_SECONDS = 260 # Длительность одной сессии


def keep_radio_alive(url):
    """Функция виртуального слушателя для одной радиостанции."""
    
    print(f"[{time.strftime('%H:%M:%S')}] Starting listener for {url}...")

    headers = {
        # Оставляем стандартный User-Agent без изменений (можно заменить на свой)
        'User-Agent': (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 Chrome/128.0 Safari/537.36"
        ),
        
        # ВАЖНО: Указываем ТВОЙ тестовый сайт!
        # Сервер будет считать, что слушатель пришёл именно оттуда.
        'Referer': 'https://radio.art-test-1.store', 
        
        # Для получения названий треков из метаданных потока
        'Icy-MetaData': '1'
    }

    # ↓↓↓ ВСЕ ЭТИ СТРОКИ ДОЛЖНЫ БЫТЬ НА ОДНОМ УРОВНЕ ОТСТУПА! ↓↓↓
    try:
        with requests.get(url, stream=True, timeout=20, headers=headers) as response:
            response.raise_for_status()
            
            start_time = time.time() 

            # Проверка наличия mpv
            if not hasattr(subprocess, 'Popen'):
                raise RuntimeError("mpv is not available")

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

                # Пауза ровно на длительность сессии
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
    while True:
        processes = []

        # Запускаем виртуальных слушателей для всех радиостанций из списка RADIOS
        for radio_url in RADIOS:
            p = Process(target=keep_radio_alive, args=(radio_url,))
            p.start()
            processes.append(p)

        # Ждём завершения ВСЕХ запущенных процессов (т.е. окончания сессии).
        # После этого мы выйдем из цикла ожидания и запустим новый набор процессов.
        for process in processes:
            process.join()
