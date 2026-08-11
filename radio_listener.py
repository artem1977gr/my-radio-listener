import requests
import subprocess
import time
from datetime import datetime


# URL вашего потока от MyRadio24
RADIO_URL = 'https://listen7.myradio23.com/sintezi'
SESSION_DURATION_SECONDS = 300  # 5 минут
CONNECT_INTERVAL_SECONDS = 180  # Интервал между попытками: 3 минуты

def keep_radio_alive():
    """Поддерживает активное подключение к радиопотоку."""
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Starting listener for {RADIO_URL}...")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Icy-MetaData': '1'  # Поддержка метаданных Icecast
    }

    try:
        with requests.get(RADIO_URL, stream=True, timeout=20, headers=headers) as response:
            response.raise_for_status()
            
            player = subprocess.Popen(
                ['mpv', '--no-video', '--quiet', '-'],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                bufsize=65536 * 2  # Буфер ~128 КБ
            )
            
            start_time = time.time()
            
            while True:
                elapsed = int(time.time() - start_time)
                
                # Проверяем, прошло ли нужное время сессии
                if elapsed >= SESSION_DURATION_SECONDS:
                    break
                    
                chunk = next(response.iter_content(chunk_size=65536), None)
                if not chunk or player.poll() is not None:
                    break
                
                try:
                    player.stdin.write(chunk)
                except BrokenPipeError:
                    break

    except requests.exceptions.RequestException as e:
        print(f"Connection error: {e}. Reconnecting immediately.")
        
    finally:
        # Завершаем процесс mpv
        if 'player' in locals() and player.poll() is None:
            player.terminate()
            try:
                player.wait(timeout=5)
            except subprocess.TimeoutExpired:
                player.kill()

if __name__ == '__main__':
    while True:
        keep_radio_alive()
        # Ждём перед следующей попыткой подключения
        time.sleep(CONNECT_INTERVAL_SECONDS)
