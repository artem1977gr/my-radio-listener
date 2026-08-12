import requests
import subprocess
import time
from multiprocessing import Process # Многопроцессность для запуска нескольких станций параллельно
import random

# Список URL радиостанций
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
    """
    Загружаем свежие прокси с GitHub и отбираем только стандартные порты,
    которые гарантированно должны работать через Railway.
    """
    
    try:
        response = requests.get(GITHUB_PROXY_SOURCE, timeout=10)
        response.raise_for_status()
        
        proxies = []
        for line in response.text.splitlines():
            # Очищаем строку от мусора
            line = line.strip().replace('http://', '').replace('https://', '')
            
            # Проверяем формат: должно быть ровно одно двоеточие (ip:port)
            if ':' not in line or line.count(':') != 1:
                continue
                
            ip, port = line.split(':')
            # Оставляем только безопасные порты! Railway часто блокирует другие.
            # Если вы используете платные прокси — можно убрать эту проверку.
            if port in ['80', '443']:
                proxies.append(f'http://{line}')
                    
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] Ошибка при загрузке списка: {e}")
        return []
    
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

    #### ВАЖНЫЙ МОМЕНТ ####
    # Прокси выбирается ВНЕ функции, поэтому здесь мы просто используем переменную current_proxy_address
    # Она будет либо валидным адресом, либо None (если прокси не нашлось).
    proxies = {"http": current_proxy_address, "https": current_proxy_address} if current_proxy_address else None

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
            
            #### ВАШ ИСХОДНЫЙ ЦИКЛ РАБОТЫ СОХРАНЁН ###
            # Вы читаете первый чанк данных, отправляете его в mpv и засыпаете на 5 минут.
            # За это время плеер успевает воспроизвести поток, а соединение остаётся открытым.
            # Этот подход работает идеально без прокси, но требует специальных условий для них.
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

                # Ваша пауза для таймера окончания сессии
                time.sleep(300) # <-- Оставлено без изменений

                # Дополнительная проверка: если mpv завершился сам
                if player.poll() is not None:
                    break

    except requests.exceptions.ProxyError:
        print(f"[{time.strftime('%H:%M:%S')}] Proxy error/dead: {current_proxy_address}")
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
        # ⚠️ Ключевое изменение: выбор прокси вынесен сюда!
        # Скачиваем НОВЫЙ список ПЕРЕД каждым циклом вещания
        PROXY_POOL = fetch_proxies_from_github()
        
        # Выбираем один случайный прокси для ВСЕГО текущего цикла.
        # Если список пуст — будем слушать напрямую.
        current_proxy_address = random.choice(PROXY_POOL) if PROXY_POOL else None

        processes = []

        # Запускаем виртуальных слушателей для всех радиостанций из списка RADIOS
        # Все процессы будут использовать одну и ту же прокси-сессию.
        for radio_url in RADIOS:
            p = Process(target=keep_radio_alive, args=(radio_url,))
            p.start()
            processes.append(p)

        # Ждём завершения ВСЕХ запущенных процессов (т.е. окончания сессии).
        # Так как у вас каждая сессия длится ровно 5 минут, все процессы завершатся примерно синхронно.
        # После этого мы выйдем из цикла ожидания и запустим новый набор процессов.
        for process in processes:
            process.join()
