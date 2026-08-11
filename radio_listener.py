import requests
from datetime import datetime
import time
import subprocess


# Настройки (измените URL на нужный вам)
RADIO_URL = 'https://listen7.myradio24.com/sintezi'
SESSION_DURATION_SECONDS = 900 # Длительность одной сессии: ~15 минут
CONNECT_INTERVAL_SECONDS = 180 # Пауза между попытками: 3 минуты

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
)
HEADERS = {
    'User-Agent': USER_AGENT,
    'Icy-MetaData': '1' # Для получения метаданных от Icecast-серверов
}


def keep_radio_alive():
    """Функция одной сессии."""
    
    try:
        with requests.get(RADIO_URL, stream=True, timeout=20, headers=HEADERS) as response:
            #### МИНИМАЛЬНОЕ ИЗМЕНЕНИЕ №1 ####
            start_time = time.time()  # Начало сессии

            if not response.ok or 'location' in response.headers:
                raise Exception(
                    f"HTTP Error {response.status_code}: {response.reason}. "
                    f"\nURL: {RADIO_URL}"
                    f"\nHeaders sent by server: {dict(response.headers)}"
                )
            
            player = subprocess.Popen([
                'mpv', '--no-video', '--quiet', '-'],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

            buffer_size = 65536  
            
            #### ВАЖНЫЙ МОМЕНТ! ###
            # Мы НЕ добавляем проверку времени внутри этого цикла!
            for chunk in response.iter_content(chunk_size=buffer_size):
                if not chunk:
                    break

                player.stdin.write(chunk)
                player.stdin.flush()

                # Дополнительная проверка: если mpv завершился сам
                if player.poll() is not None:
                    break

    except requests.exceptions.RequestException as e:
        print(f"[{datetime.now():%H:%M:%S}] Connection error: {e}. Reconnecting immediately...")
        
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
        #### КЛЮЧЕВАЯ ЧАСТЬ — ЖДЁМ ЗАДЕРЖКУ ВНЕ ЦИКЛА ПРОИЗВОДСТВА ДАННЫХ ####
        time.sleep(wait_seconds)
