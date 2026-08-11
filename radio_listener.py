import requests
import subprocess
import time
from datetime import datetime


# URL вашего потока от MyRadio24
RADIO_URL = 'https://listen7.myradio24.com/sintezi'

def keep_radio_alive():
    """Функция для имитации непрерывного прослушивания."""
    
    # Время начала текущей сессии
    session_start_time = time.time()
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Starting listener for {RADIO_URL}...")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Icy-MetaData': '1'  # Поддержка метаданных Icecast
    }

    try:
        with requests.get(RADIO_URL, stream=True, timeout=20, headers=headers) as response:
            response.raise_for_status()  # Проверяем статус ответа

            # Запускаем mpv с уменьшенным буфером (~8 КБ)
            player = subprocess.Popen(
                ['mpv', '--no-video', '--quiet', '-'],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                bufsize=8 * 1024  
            )
            
            buffer_size = 65536 

            # Основной цикл загрузки
            while True:
                elapsed = int(time.time() - session_start_time)
                
                # Если прошло больше 2 часов, завершаем сессию
                if elapsed > 7200:  # 2 часа в секундах
                    break
                    
                chunk = next(response.iter_content(chunk_size=buffer_size), None)
                if not chunk or player.poll() is not None:
                    break
                
                try:
                    player.stdin.write(chunk)
                except BrokenPipeError:
                    break

    except requests.exceptions.RequestException as e:
        print(f"Connection error: {e}. Reconnecting in 60 seconds...")
        time.sleep(60)  # Ждём минуту перед повторной попыткой
        
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
        
        # Пауза между сессиями, чтобы избежать блокировок
        print("Session ended. Waiting before reconnecting...")
        time.sleep(300)  # Паузы в 5 минут (300 секунд)
