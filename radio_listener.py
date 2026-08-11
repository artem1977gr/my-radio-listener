import requests
import subprocess
import time

# Ваша прямая ссылка на поток от MyRadio24
RADIO_URL = 'https://listen7.myradio24.com/sintezi'

def keep_radio_alive():
    print(f"[{time.strftime('%H:%M:%S')}] Starting listener for {RADIO_URL}...")
    
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
            
            for chunk in response.iter_content(chunk_size=buffer_size):
                if chunk:
                    try:
                        player.stdin.write(chunk)
                    except BrokenPipeError:
                        break
                
                if player.poll() is not None:
                    break
                    
    except requests.exceptions.RequestException as e:
        print(f"Connection error: {e}. Reconnecting in 10 seconds...")
        time.sleep(10)
    finally:
        if 'player' in locals() and player.poll() is None:
            player.terminate()
            try:
                player.wait(timeout=5)
            except subprocess.TimeoutExpired:
                player.kill()

if __name__ == '__main__':
    while True:
        keep_radio_alive()