import requests
from time import sleep, time as get_current_time
import datetime
import os  # Для переименования файла под workflow
import random
import certifi  # Доверенные корневые сертификаты
import json
from urllib3.util.retry import Retry
from urllib3.poolmanager import PoolManager


# ⚡️ НАИБОЛЕЕ НАДЁЖНЫЕ ИСТОЧНИКИ + дополнительные HTTP(S)
sources = [
    "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=10000",  # Без country=all
    "https://www.proxy-list.download/api/v1/get?type=http&anon=elite",
    
    # Дополнительные надёжные источники
    "https://raw.githubusercontent.com/roosterkid/openproxylists/master/MIXED_ANON_HTTP.txt",  # Текстовый файл с GitHub
    "https://api.openproxylist.xyz/http.txt"  # Простой API без параметров
]

# Настройки адаптивных таймаутов
PING_TIMEOUT_CONNECT = 3
PING_TIMEOUT_READ = 5
STREAM_TIMEOUT_CONNECT = 5
STREAM_TIMEOUT_READ = 20

# Пул соединений
pool_manager = PoolManager(
    num_pools=10,
    maxsize=50,
    retries=Retry(total=3, backoff_factor=0.1),
    ca_certs=certifi.where()  # Нормальные сертификаты!
)

user_agents = [  # Ротация UA
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64; rv:88.0) Gecko/20100101 Firefox/88.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15'
]

working_proxies = []  # Сюда будут попадать только прошедшие проверку
suspect_proxies = set()  # Здесь будем собирать IP для повторного теста

def check_proxy(proxy_str):
    """Проверка одного IP:PORT."""
    
    if ':' not in proxy_str:
        return False  # Не валидный формат

    ip, port = proxy_str.split(':')
    protocols_to_check = ['socks5h', 'http'] if int(port) in [1080, 443, 8080] else ['http']

    for protocol in protocols_to_check:
        session = requests.Session()
        
        # ✅ Правильная сборка полного URL для прокси
        full_proxy_url = f"{protocol}://{proxy_str}"
        proxies = {
            "http": full_proxy_url,
            "https": full_proxy_url
        }

        # Создаем сессию с нашим менеджером соединений
        adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=50, pool_block=True)
        session.mount('http://', adapter)
        session.mount('https://', adapter)

        # Устанавливаем случайный User-Agent
        session.headers.update({'User-Agent': random.choice(user_agents)})

        try:
            # Этап 1: Быстрый пинг через https://httpbin.org/ip
            response = session.get("https://httpbin.org/ip", timeout=(PING_TIMEOUT_CONNECT, PING_TIMEOUT_READ))
            
            # Метрика успеха №1: Статус-код 200 AND есть тело ответа с нужным контентом
            if response.status_code != 200 or '"origin"' not in response.text:
                continue  # Следующий протокол
        except Exception as e:
            print(f"[FAIL] {full_proxy_url} - Ping error:", str(e))

            # Собираем подозрительные ошибки для повторного теста
            if isinstance(e, requests.exceptions.ProxyError) and (
                    'Connection refused' in str(e) or 
                    'Tunnel connection failed: 500 Internal Server Error' in str(e)):
                suspect_proxies.add(full_proxy_url)

            continue

        # Этап 2: Тест нашего конкретного аудио-потока
        try:
            # Более долгий таймаут для скачивания данных
            response = session.get("https://listen7.myradio24.com/iridium", stream=True, timeout=(STREAM_TIMEOUT_CONNECT, STREAM_TIMEOUT_READ))  
            
            start_time = get_current_time()
            data_chunk = response.raw.read(8192)  # Читаем примерно 8 КБ
            end_time = get_current_time()

            # Метрика успеха №2: Получено минимум 10 байт данных
            if not data_chunk or len(data_chunk) < 10:
                print(f"[FAIL] {full_proxy_url} - Audio stream failed")
                return False

            elapsed_seconds = end_time - start_time
            speed_kbps = len(data_chunk) / elapsed_seconds / 1024  # KB/s

            latency = round((end_time - start_time) * 1000, 2)

            # Минимальная скорость ~20 KB/s.
            if speed_kbps < 20:
                print(f"[FAIL] {full_proxy_url} - Speed too low ({speed_kbps:.2f} KB/s)")
                return False

            working_proxies.append((speed_kbps, full_proxy_url))
            print(f"[OK] {full_proxy_url} - Latency: {latency} ms | Speed: {speed_kbps:.2f} KB/s")
            return True
        except Exception as e:
            print(f"[FAIL] {full_proxy_url} - Audio test failed:", str(e))

            # Собираем подозрительные ошибки для повторного теста
            if isinstance(e, requests.exceptions.ProxyError) and (
                    'Connection refused' in str(e) or 
                    'Tunnel connection failed: 500 Internal Server Error' in str(e)):
                suspect_proxies.add(full_proxy_url)

            break


if __name__ == "__main__":
    MAX_WORK_TIME_MINUTES = 25
    TARGET_PROXY_COUNT = 30

    # Кэшируем список прокси из API между запусками
    cached_sources_file = ".cached_sources.json"
    all_proxies = []

    # Загружаем старый файл с предыдущими рабочими прокси
    old_proxies = []
    try:
        with open("working_proxies.txt", "r") as file:
            old_proxies = [line.strip() for line in file.readlines()]
        print("[INFO] Previous proxy list loaded.")
    except FileNotFoundError:
        print("[INFO] Previous proxy list not found.")

    # Сначала проверяем старые прокси
    print("\n[INFO] Checking previous working proxies...")
    for proxy in old_proxies:
        result = check_proxy(proxy.replace('http://', '').replace('socks5h://', ''))

    # Если у нас уже есть нужное количество рабочих старых адресов — завершаем работу
    if len(working_proxies) >= TARGET_PROXY_COUNT:
        print("[INFO] Target number of proxies reached from the previous list. Skipping external sources.")
    else:
        # Загрузка новых прокси
        print("\n[INFO] Fetching new proxies to reach target count...")
        start_script_time = datetime.datetime.now()

        # Пробуем сначала загрузить из кэша
        try:
            with open(cached_sources_file, "r") as cache_file:
                all_proxies = json.load(cache_file)
            print("[INFO] Proxy lists loaded from cache.")
        except FileNotFoundError:
            pass

        # Если нет кэша или он устарел — загружаем заново
        if not all_proxies:
            for source in sources:
                print(f"\n[INFO] Scraping from {source}")
                
                # Анти-DDoS защита источника: случайная задержка
                sleep(random.uniform(1, 3))

                try:
                    resp = requests.get(source, timeout=10)
                    all_proxies.extend(resp.text.splitlines())
                except Exception as e:
                    print(f"[ERROR] Failed to fetch data from {source}:", str(e))
                    continue

            # Сохраняем кэш
            with open(cached_sources_file, "w") as cache_file:
                json.dump(all_proxies, cache_file)

        # Проверяем новые адреса
        for proxy in all_proxies:
            # Проверка лимита времени или количества
            elapsed_minutes = (datetime.datetime.now() - start_script_time).total_seconds() / 60
            if elapsed_minutes >= MAX_WORK_TIME_MINUTES or len(working_proxies) >= TARGET_PROXY_COUNT:
                print("[WARNING] Script has reached the target number of proxies or time limit.")
                break

            sleep(0.1)
            result = check_proxy(proxy.strip())

    # Повторная проверка аутсайдеров
    print("\n[INFO] Re-checking suspicious proxies that previously returned Connection Refused or Tunnel errors...")
    for proxy_url in suspect_proxies:
        # Мы уже знаем полный URL, так что сразу передаём его целиком
        result = check_proxy(proxy_url.replace('http://', '').replace('socks5h://', ''))

    # ✅ СОРТИРУЕМ ПО СКОРОСТИ ОТ БОЛЬШЕЙ К МЕНЬШЕЙ
    sorted_proxies = sorted(working_proxies, key=lambda x: x[0], reverse=True)

    # Разделяем на старые и новые
    sorted_old_proxies = [(speed, url) for speed, url in sorted_proxies if url in old_proxies]
    sorted_new_proxies = [(speed, url) for speed, url in sorted_proxies if url not in old_proxies]

    # Сохраняем ВСЕ старые рабочие прокси, а затем добавляем недостающее количество новых
    with open("working_proxies.txt", "w") as file:
        # Пишем ВСЕ старые
        for _, p in sorted_old_proxies:
            file.write(p + "\n")
        
        # Добавляем новые до достижения цели
        needed_count = max(TARGET_PROXY_COUNT - len(sorted_old_proxies), 0)
        for i, (_, p) in enumerate(sorted_new_proxies[:needed_count]):
            file.write(p + "\n")
