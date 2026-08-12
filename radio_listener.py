import requests  # Для работы с HTTP(S)
import subprocess  # Для запуска MPV
import time  # Для таймеров и пауз
from multiprocessing import Process  # Многопроцессность

# Список URL ваших радиостанций
RADIOS = [
    'https://listen7.myradio24.com/sintezi',
    'https://listen7.myradio24.com/sintezi_128',
    'https://listen7.myradio24.com/rockataka',
    'https://listen7.myradio24.com/rockataka_128',
    'https://listen7.myradio24.com/iridium',
    'https://listen7.myradio24.com/nevermind'
]
SESSION_DURATION_SECONDS = 300  # Длительность одной сессии прослушивания

# Ссылка на "сырой" текстовый файл со списком бесплатных прокси на GitHub
GITHUB_PROXY_SOURCE = 'https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt'

# ⚠️ Эта функция скачивает список прокси один раз за цикл
def fetch_proxies_from_github():
    """Загружаем свежие прокси с GitHub и отбираем только те, что работают на стандартных портах."""
    
    try:
        response = requests.get(GITHUB_PROXY_SOURCE, timeout=10)
        response.raise_for_status()
        
        proxies = []
        for line in response.text.splitlines():
            line = line.strip().replace('http://', '').replace('https://', '')
            
            # Проверяем формат IP:PORT и оставляем только стандартные порты
            if ':' in line and line.count(':') == 1:
                ip, port = line.split(':')
                # Railway часто блокирует нестандартные порты публичных прокси!
                # Оставим только безопасные варианты
                if port in ['80', '443']:
                    proxies.append(f'http://{line}')
                    
        print(f"[{time.strftime('%H:%M:%S')}] Загрузил {len(proxies)} валидных прокси.")
        return proxies
    
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] Ошибка при загрузке списка: {e}")
        return []

# ⚠️ Простая проверка: можем ли мы получить заголовки ответа через этот прокси?
def check_proxy(proxy_address):
    headers = {'User-Agent': 'Mozilla/5.0'}
    test_url = RADIOS[0]  # Берём первую станцию для проверки
    
    try:
        with requests.head(test_url, timeout=5, headers=headers, proxies={"http": proxy_address, "https": proxy_address}) as resp:
            # Если запрос прошёл — прокси живой
            return True  
    except requests.exceptions.RequestException:
        # Прокси мёртв или забанен сервером радио
        return False 

# ✅ ВАША оригинальная функция без изменений! Только добавлена поддержка None-прокси
def keep_radio_alive(url, current_proxy_address=None):
    """
    Функция виртуального слушателя для одной радиостанции.
    Сохраняет ваш уникальный режим экономии ресурсов (sleep(300)).
    """
    
    print(f"[{time.strftime('%H:%M:%S')}] Starting listener for {url} via {current_proxy_address or 'DIRECT CONNECTION'}...")
    
    headers = {
        'User-Agent': (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
        ),
        'Icy-MetaData': '1'
    }

    # Ваш оригинальный подход к прокси
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
            
            #### ВАШ ИСХОДНЫЙ ЦИКЛ ####
            # Вы читаете чанк, отправляете его в mpv и засыпаете на 5 минут.
            # Это ваша уникальная архитектура экономии CPU.
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

                # Ваша пауза для экономии ресурсов
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
        # Скачиваем НОВЫЙ список ПЕРЕД каждым циклом вещания
        PROXIES_POOL = fetch_proxies_from_github()
        
        # Фильтруем прокси, проверяя их работоспособность
        WORKING_PROXIES = [p for p in PROXIES_POOL if check_proxy(p)]
        
        # Если ни один прокси не прошёл проверку, используем прямое соединение
        # В случае с бесплатными списками это произойдёт ВСЕГДА, потому что они уже забанены.
        current_proxy = random.choice(WORKING_PROXIES) if WORKING_PROXIES else None

        processes = []
        # Запускаем все процессы с одним и тем же рабочим прокси (или напрямую)
        for radio_url in RADIOS:
            p = Process(target=keep_radio_alive, args=(radio_url, current_proxy))
            p.start()
            processes.append(p)

        # Ждём завершения ВСЕХ запущенных процессов (через 5 минут)
        for process in processes:
            process.join()
