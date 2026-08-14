import requests
import subprocess
import time
from multiprocessing import Process # Многопроцессность для запуска нескольких станций параллельно

# Список URL радиостанций (добавлены твои новые потоки)
RADIOS = [
    'https://listen7.myradio24.com/sintezi',
    'https://listen7.myradio24.com/sintezi_128',
    'https://listen7.myradio24.com/sintezi',
    'https://listen7.myradio24.com/rockataka',
    'https://listen7.myradio24.com/rockataka_128',
    'https://listen7.myradio24.com/iridium',
    'https://listen7.myradio24.com/nevermind'
]
SESSION_DURATION_SECONDS = 300 

def keep_radio_alive(url):
    """Функция виртуального слушателя для одной радиостанции."""
    
    print(f"[{time.strftime('%H:%M:%S')}] Starting listener for {url}...")
    
    headers = {
        'User-Agent': (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
        ),
        'Icy-MetaData': '1'
    }

    try:
        with requests.get(url, stream=True, timeout=20, headers=headers) as response:
            response.raise_for_status()
            
            start_time = time.time() 

            player = subprocess.Popen(
                ['mpv', '--no-video', '--quiet', '-'],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
            buffer_size = 65536  
            
            #### ВАЖНЫЙ МОМЕНТ ####
            # Твой оригинальный цикл чтения данных остался без изменений.
            # Ты читаешь chunk, отправляешь его в mpv, а затем засыпаешь на 5 минут.
            # Это позволяет тебе экономить CPU до минимума.
            for chunk in response.iter_content(chunk_size=buffer_size):
                if not chunk:
                    break

                elapsed = int(time.time() - start_time)
                
                # Завершаем сессию через SESSION_DURATION_SECONDS
                if elapsed >= SESSION_DURATION_SECONDS:
                    print(f"[{time.strftime('%H:%M:%S')}] Session ended after {elapsed}s.")
                    break

                # Передаём данные в mpv
                try:
                    player.stdin.write(chunk)
                except BrokenPipeError:
                    break

                # Твоя пауза для экономии ресурсов — это ключевой момент твоей архитектуры!
                time.sleep(300) # <-- Оставляем твой режим работы по 5-минутным циклам

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
        print(f"[{time.strftime('%H:%M:%S')}] Listener for {url} terminated.")

if __name__ == '__main__':
    while True:
        processes = []

        # Запускаем виртуальных слушателей для всех радиостанций из списка RADIOS
        for radio_url in RADIOS:
            p = Process(target=keep_radio_alive, args=(radio_url,))
            p.start()
            processes.append(p)

        # Ждём завершения ВСЕХ запущенных процессов (т.е. окончания сессии).
        # Так как у тебя каждая сессия длится ровно 5 минут, все процессы завершатся примерно синхронно.
        # После этого мы выйдем из цикла ожидания и запустим новый набор процессов.
        for process in processes:
            process.join()
