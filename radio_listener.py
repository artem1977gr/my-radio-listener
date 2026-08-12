import requests
import subprocess
import time
from multiprocessing import Process
import random

# Список URL радиостанций (добавлены твои новые потоки)
RADIOS = [
    'https://listen7.myradio24.com/sintezi',
    'https://listen7.myradio24.com/sintezi_128',
    'https://listen7.myradio24.com/rockataka',
    'https://listen7.myradio24.com/rockataka_128',
    'https://listen7.myradio24.com/iridium',
    'https://listen7.myradio24.com/nevermind'
]
SESSION_DURATION_SECONDS = 300 

# Ссылка на "сырой" файл со списком HTTP-прокси на GitHub
GITHUB_PROXY_SOURCE = 'https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt'

def fetch_proxies_from_github():
    """Загружает список прокси в формате IP:PORT напрямую из репозитория."""
    proxies = []
    try:
        response = requests.get(GITHUB_PROXY_SOURCE, timeout=10)
        response.raise_for_status()
        
        for line in response.text.splitlines():
            line = line.strip()
            # Пропускаем комментарии и пустые строки
            if not line or line.startswith('#'):
                continue
            
            # Убираем протокол, если он вдруг есть в файле, оставляем чистый ip:port
            clean_line = line.replace('http://', '').replace('https://', '')
            
            # Добавляем http:// для библиотеки requests, проверяя базовый формат
            if ':' in clean_line and clean_line.count(':') == 1:
                proxies.append(f"http://{clean_line}")
                
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] Ошибка при загрузке прокси с GitHub: {e}")
        
    return proxies

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

    # --- ИЗМЕНЕННЫЙ БЛОК ---
    # Получаем свежий список прямо перед запуском каждого отдельного процесса
    proxy_list = fetch_proxies_from_github()
    
    # Выбираем один случайный прокси для этой конкретной сессии
    current_proxy_address = random.choice(proxy_list) if proxy_list else None
    
    # Формируем словарь только если адрес найден
    proxies = {"http": current_proxy_address, "https": current_proxy_address} if current_proxy_address else None
    
    # Для отладки: можно раскомментировать, чтобы видеть выбранный IP
    # if current_proxy_address:
    #     print(f"[{time.strftime('%H:%M:%S')}] Listener for {url} will use proxy: {current_proxy_address}")
    # else:
    #     print(f"[{time.strftime('%H:%M:%S')}] Listener for {url} will use direct connection.")
    # --- КОНЕЦ ИЗМЕНЕНИЙ ---

    try:
        with requests.get(url, stream=True, timeout=20, headers=headers, proxies=proxies) as response:
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

    except requests.exceptions.ProxyError:
        print(f"[{time.strftime('%H:%M:%S')}] Proxy error/dead for {url}: {current_proxy_address}")
    except requests.exceptions.RequestException as e:
        print(f"[{time.strftime('%H:%M:%S')}] Connection error: {e}. Reconnecting immediately...") 
        
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
