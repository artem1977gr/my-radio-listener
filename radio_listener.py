import requests
from datetime import datetime
import time
import subprocess


# Настройки (изменён только этот URL)
RADIO_URL = "https://listen7.myradio24.com/rockataka_128" # <-- Новый адрес!
SESSION_DURATION_SECONDS = 1000 # Длительность одной сессии: ~16 мин 40 сек
CONNECT_INTERVAL_SECONDS = 100 # Пауза перед повторным подключением: 1 мин 40 сек
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
)
headers = {
    'User-Agent': USER_AGENT,
}


def main():
    """Основной цикл прослушивания."""
    
    while True:
        start_time = time.time()
        
        try:
            with requests.get(RADIO_URL, stream=True, timeout=20, headers=headers) as response:
                # Проверяем ответ сервера ДО начала работы с данными
                if not response.ok or 'location' in response.headers:
                    raise Exception(
                        f"[{datetime.now():%H:%M:%S}] HTTP Error {response.status_code}: {response.reason}."
                        f"\nURL: {RADIO_URL}"
                        f"\nHeaders sent by server: {dict(response.headers)}"
                    )
                
                elapsed = int(time.time() - start_time)
                print(f"[{datetime.now():%H:%M:%S}] Session started ({elapsed}s). Connecting to '{RADIO_URL}'.")

                player = subprocess.Popen([
                    "mpv",
                    "--really-quiet", 
                    "-no-video", 
                    "-"
                ], stdin=subprocess.PIPE)

                for chunk in response.iter_content(chunk_size=65536):
                    elapsed = int(time.time() - start_time)
                    
                    # Завершаем сессию через SESSION_DURATION_SECONDS
                    if elapsed >= SESSION_DURATION_SECONDS:
                        break

                    # Если сервер закрыл соединение раньше времени
                    if chunk is None or len(chunk) == 0:
                        print(f"[{datetime.now():%H:%M:%S}] Stream closed by server after {elapsed} seconds.")
                        break

                    player.stdin.write(chunk)
                    player.stdin.flush()

        except Exception as e:
            print(f"[{datetime.now():%H:%M:%S}] [ERROR] {e}")
            
        finally:
            # Ждём завершения плеера или завершаем его принудительно
            if player.poll() is None:
                player.terminate()
                player.wait(timeout=5)

            # Делаем паузу до следующего запуска
            elapsed_session = int(time.time() - start_time)
            wait_seconds = max(0, CONNECT_INTERVAL_SECONDS - elapsed_session)
            print(f"[{datetime.now():%H:%M:%S}] Session ended ({elapsed_session}s). Waiting for {wait_seconds}s before reconnecting to '{RADIO_URL}'.")
            time.sleep(wait_seconds)


if __name__ == '__main__':
    main()
