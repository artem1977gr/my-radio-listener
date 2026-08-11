import requests
import subprocess
import time

# Ваша прямая ссылка на поток от MyRadio24
RADIO_URL = 'https://listen7.myradio24.com/sintezi'
SESSION_DURATION_SECONDS = 900 # ~15 минут. Минимальная правка!
CONNECT_INTERVAL_SECONDS = 180 # Пауза между попытками: 3 минуты. МИНИМАЛЬНОЕ ИЗМЕНЕНИЕ!

def keep_radio_alive():
    print(f"[{time.strftime('%H:%M:%S')}] Starting listener for {RADIO_URL}...")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Icy-MetaData': '1'
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
            
            for chunk in response.iter_content(chunk_size=buffer_size):
                if chunk:
                    try:
                        player.stdin.write(chunk)
                    except BrokenPipeError:
                        break
                
                elapsed = int(time.time() - start_time)
                # Завершаем сессию через SESSION_DURATION_SECONDS
                if elapsed >= SESSION_DURATION_SECONDS:
                    break # Выход из цикла -> конец сессии

                if player.poll() is not None:
                    break
                    
    except requests.exceptions.RequestException as e:
        print(f"Connection error: {e}. Reconnecting in 10 seconds...")
        time.sleep(10)
    finally:
        #### МИНИМАЛЬНАЯ ПРАВКА ####
        # Завершаем процесс плеера
        if 'player' in locals() and player.poll() is None:
            player.terminate()
            try:
                player.wait(timeout=5)
            except subprocess.TimeoutExpired:
                player.kill()
        
        # Делаем паузу до следующего запуска
        elapsed_session = int(time.time() - start_time)
        wait_seconds = max(0, CONNECT_INTERVAL_SECONDS - elapsed_session)
        print(f"[{time.strftime('%H:%M:%S')}] Session ended ({elapsed_session}s). Waiting for {wait_seconds}s before reconnecting to '{RADIO_URL}'.")
        #### ВАЖНЫЙ МОМЕНТ ####
        # Если сессия длилась меньше 3 минут, мы ждём остаток времени.
        # Если она длилась больше 3 минут, мы всё равно делаем паузу в 3 минуты.
        time.sleep(CONNECT_INTERVAL_SECONDS)
