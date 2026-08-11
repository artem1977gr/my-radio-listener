import requests
from datetime import datetime
import time
import subprocess


# Настройки
RADIO_URL = "https://myradio24.org/iridium"
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
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Starting listener service...")
    
    while True:
        start_time = time.time()
        
        try:
            with requests.get(RADIO_URL, stream=True, timeout=20, headers=headers) as response:
                # Проверяем ответ сервера ДО начала работы с данными
                if not response.ok or 'location' in response.headers:
                    raise Exception(
                        f"HTTP Error {response.status_code}: {response.reason}."
                        f"\nURL: {RADIO_URL}"
                        f"\nHeaders sent by server: {dict(response.headers)}"
                    )
                
                # Запускаем плеер mpv без вывода звука (-no-video), но с попыткой воспроизведения.
                player = subprocess.Popen([
                    "mpv",
                    "--really-quiet", # Минимум логов
                    "-no-video",      # Отключаем видео (если вдруг)
                    "-"              # Читать данные из stdin
                ], stdin=subprocess.PIPE)

                # Основной цикл чтения данных из потока
                for chunk in response.iter_content(chunk_size=65536):
                    elapsed = int(time.time() - start_time)
                    
                    # Проверяем длительность сессии
                    if elapsed >= SESSION_DURATION_SECONDS:
                        break # Завершаем чтение после заданного времени

                    # Если сервер закрыл соединение раньше времени
                    if chunk is None or len(chunk) == 0:
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] Stream closed by server after {elapsed} seconds.")
                        break

                    player.stdin.write(chunk)
                    player.stdin.flush()

        except Exception as e:
            # Выводим полное сообщение об ошибке
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [ERROR] {e}")
            
        finally:
            # Завершаем процесс плеера
            if player.poll() is None:
                player.terminate()
                player.wait(timeout=5)

            # Делаем паузу до следующего запуска
            elapsed_session = int(time.time() - start_time)
            wait_seconds = max(0, CONNECT_INTERVAL_SECONDS - elapsed_session)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Session ended ({elapsed_session}s). Waiting for {wait_seconds}s before reconnecting to '{RADIO_URL}'.")
            time.sleep(wait_seconds)


if __name__ == '__main__':
    main()
