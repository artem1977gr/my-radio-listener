import requests
from datetime import datetime # <--- Я добавил эту строку!
import time
import subprocess


# Настройки (измените URL на нужный вам)
RADIO_URL = 'https://listen7.myradio24.com/rockataka_128'  # <-- Ваш поток!
SESSION_DURATION_SECONDS = 3600   # Длительность одной сессии: ~1 ЧАС! 
                               # Попробуйте начать с этого значения.
CONNECT_INTERVAL_SECONDS = 600  # Пауза между попытками: 10 минут! 
                               # Можно увеличить до 1800 (30 мин).

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

            player = subprocess.Popen([
                'mpv', '--no-video', '--quiet', '-'],
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

                #### КЛЮЧЕВАЯ ПРАВКА ####
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
        
        #### МИНИМАЛЬНОЕ ИЗМЕНЕНИЕ №17 ####
        # Гарантированная большая пауза между сессиями.
        # Сервер MyRadio24 требует реальных перерывов.
        MIN_PAUSE_SECONDS = 600  # 10 минут! 
                           # Можно увеличить до 900 или даже 1800 (30 мин)!
        wait_seconds = max(MIN_PAUSE_SECONDS, CONNECT_INTERVAL_SECONDS)

        print(f"[{datetime.now():%H:%M:%S}] Session ended ({elapsed_session}s). Waiting for {wait_seconds}s before reconnecting to '{RADIO_URL}'.")
        #### ЭТО САМОЕ ГЛАВНОЕ — ЖДЁМ ЗАДЕРЖКУ ВНЕ ЦИКЛА ПРОИЗВОДСТВА ДАННЫХ ####
        time.sleep(wait_seconds)
