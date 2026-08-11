import requests
import subprocess
import time

# Ваша прямая ссылка на поток от MyRadio24
RADIO_URL = 'https://listen7.myradio24.com/rockataka_128' # <-- Ваш поток!
SESSION_DURATION_SECONDS = 900   # Длительность одной сессии: ~15 минут
#### МИНИМАЛЬНОЕ ИЗМЕНЕНИЕ ####
# Возвращаем константу для паузы между попытками
CONNECT_INTERVAL_SECONDS = 180  # Пауза между попытками: 3 минуты

def keep_radio_alive():
    print(f"[{datetime.now():%H:%M:%S}] Starting listener for {RADIO_URL}...")
    
    headers = {
        'User-Agent': (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
        ),
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
            
            #### ВАЖНЫЙ МОМЕНТ ###
            # Мы НЕ добавляем проверку времени внутри этого цикла!
            # Таймер должен быть снаружи.
            for chunk in response.iter_content(chunk_size=buffer_size):
                if not chunk:
                    break

                elapsed = int(time.time() - start_time)
                
                # Передаём данные в mpv
                try:
                    player.stdin.write(chunk)
                except BrokenPipeError:
                    break

                #### КЛЮЧЕВАЯ ПРАВКА! ###
                # Делаем крошечную паузу в цикле, чтобы дать системе передышку.
                # Без этой задержки скрипт может потреблять слишком много ресурсов CPU.
                time.sleep(0.1) # Пауза в 100 миллисекунд

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
        
        #### МИНИМАЛЬНОЕ ИЗМЕНЕНИЕ №2 ####
        elapsed_session = int(time.time() - start_time)
        wait_seconds = max(0, CONNECT_INTERVAL_SECONDS - elapsed_session)
        print(f"[{datetime.now():%H:%M:%S}] Session ended ({elapsed_session}s). Waiting for {wait_seconds}s before reconnecting to '{RADIO_URL}'.")
        #### ВАЖНЫЙ МОМЕНТ — ЖДЁМ ЗАДЕРЖКУ ВНЕ ЦИКЛА ПРОИЗВОДСТВА ДАННЫХ ####
        time.sleep(wait_seconds)
