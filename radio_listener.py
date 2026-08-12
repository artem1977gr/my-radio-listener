import requests
import subprocess
import time

# Ваша прямая ссылка на поток от MyRadio24
RADIO_URL = 'https://listen7.myradio24.com/sintezi'
SESSION_DURATION_SECONDS = 300 # время прослушивания одной сессии !
# CONNECT_INTERVAL_SECONDS убираем, он нам больше не нужен

def keep_radio_alive():
    print(f"[{time.strftime('%H:%M:%S')}] Starting listener for {RADIO_URL}...")
    
    headers = {
        'User-Agent': (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
        ),
        'Icy-MetaData': '1' # Для получения метаданных
    }

    try:
        with requests.get(RADIO_URL, stream=True, timeout=20, headers=headers) as response:
            response.raise_for_status()
            
            start_time = time.time() # Начало сессии

            player = subprocess.Popen(
                ['mpv', '--no-video', '--quiet', '-'],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
            buffer_size = 65536  
            
            #### МИНИМАЛЬНОЕ ИЗМЕНЕНИЕ ####
            # Добавим маленькую задержку внутри цикла, чтобы не грузить CPU.
            # Сервер всё равно отдаёт поток пакетами, поэтому можно подождать.
            for chunk in response.iter_content(chunk_size=buffer_size):
                if not chunk:
                    break

                elapsed = int(time.time() - start_time)
                
                # Завершаем сессию через SESSION_DURATION_SECONDS
                if elapsed >= SESSION_DURATION_SECONDS:
                    print(f"[{time.strftime('%H:%M:%S')}] Session ended after {elapsed}s.")
                    break # Выход из цикла -> конец сессии

                # Передаём данные в mpv
                try:
                    player.stdin.write(chunk)
                except BrokenPipeError:
                    break

                #### ВАЖНЫЙ МОМЕНТ ####
                # Делаем крошечную паузу в цикле, чтобы дать системе передышку.
                # Без этой задержки скрипт может потреблять слишком много ресурсов.
                time.sleep(300) # всемя перезапуска одной сесии 10 мин

                # Дополнительная проверка: если mpv завершился сам
                if player.poll() is not None:
                    break

    except requests.exceptions.RequestException as e:
        print(f"Connection error: {e}. Reconnecting immediately...") # Немедленно пытаемся снова
        
    finally:
        # Завершаем процесс плеера
        if 'player' in locals() and player.poll() is None:
            player.terminate()
            try:
                player.wait(timeout=5)
            except subprocess.TimeoutExpired:
                player.kill()

if __name__ == '__main__':
    while True:
        keep_radio_alive()
