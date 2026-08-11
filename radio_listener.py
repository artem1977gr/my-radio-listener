import requests
import subprocess
import time
from datetime import timedelta  # Для удобной работы со временем

# Ваша прямая ссылка на поток от MyRadio24
RADIO_URL = 'https://listen7.myradio24.com/sintezi'

def keep_radio_alive():
    print(f"[{time.strftime('%H:%M:%S')}] Starting listener for {RADIO_URL}...")
    
    # ⚙️ Добавляем переменную для отслеживания начала сессии
    start_time = time.time()

    # Заголовки для обхода защиты сервера
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Icy-MetaData': '1'
    }

    try:
        with requests.get(RADIO_URL, stream=True, timeout=20, headers=headers) as response:
            response.raise_for_status()
            
            player = subprocess.Popen(
                ['mpv', '--no-video', '--quiet', '-'],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
            buffer_size = 65536 
            
            # ⚙️ Основной цикл чтения потока
            while True:
                elapsed = time.time() - start_time
                
                # ⚙️ Условие остановки через 20-30 минут
                if timedelta(minutes=20) <= timedelta(seconds=elapsed) <= timedelta(minutes=30):
                    break  # Выходим из цикла после нужного интервала
                    
                chunk = next(response.iter_content(chunk_size=buffer_size), None)
                if not chunk or player.poll() is not None:
                    break  # Ошибка в потоке или плеер закрылся

                try:
                    player.stdin.write(chunk)
                except BrokenPipeError:
                    break

    except requests.exceptions.RequestException as e:
        # ⚙️ Улучшенная логика задержки при ошибках
        error_message = f"Connection error: {e}"
        
        # Если ошибка связана с сетью (таймаут, сброс соединения), ждём дольше
        if isinstance(e, (requests.Timeout, requests.ConnectionError)):
            wait_seconds = 60  # Ждём минуту перед повторной попыткой
            error_message += ". Waiting 60 seconds before reconnecting..."
        else:
            wait_seconds = 10  # Для других ошибок достаточно 10 секунд
            error_message += ". Reconnecting in 10 seconds..."
        
        print(error_message)
        time.sleep(wait_seconds)
    
    finally:
        # Закрываем плеер
        if 'player' in locals() and player.poll() is None:
            player.terminate()
            try:
                player.wait(timeout=5)
            except subprocess.TimeoutExpired:
                player.kill()

if __name__ == '__main__':
    while True:
        keep_radio_alive()
