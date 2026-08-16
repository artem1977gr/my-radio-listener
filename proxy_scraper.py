import requests
from time import sleep, time as get_current_time
import datetime
import os  # Для переименования файла под workflow
import random
import json


# ⚡️ НАИБОЛЕЕ НАДЁЖНЫЕ ИСТОЧНИКИ + дополнительные HTTP(S)
sources = [
    "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=10000",  # Без country=all
    "https://www.proxy-list.download/api/v1/get?type=http&anon=elite",
    
    # Дополнительные надёжные источники
    "https://raw.githubusercontent.com/roosterkid/openproxylists/master/MIXED_ANON_HTTP.txt",  # Текстовый файл с GitHub
    "https://api.openproxylist.xyz/http.txt"  # Простой API без параметров
]

# Настройки адаптивных таймаутов
PING_TIMEOUT_CONNECT = 5   # Быстрый пинг
PING_TIMEOUT_READ = 7
STREAM_TIMEOUT_CONNECT = 5  # Тест потока
STREAM_TIMEOUT_READ = 20

user_agents = [  # Ротация UA
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64; rv:88.0) Gecko/20100101 Firefox/88.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15'
]

working_proxies = []  # Сюда будут попадать только прошедшие проверку

def check_proxy(proxy_str):
    """Проверка одного IP:PORT."""
    
    if ':' not in proxy_str:
        return None  # Не валидный формат

    ip, port = proxy_str.split(':')

    # 📌 Логика пересечений: один IP может быть валиден сразу на нескольких портах
    protocols_to_check = ['socks5h', 'http'] if int(port) in [1080, 443, 8080] else ['http']

    results = []

    for protocol in protocols_to_check:
        session = requests.Session()
        
        full_proxy_url = f"{protocol}://{proxy_str}"
        proxies = {
            "http": full_proxy_url,
            "https": full_proxy_url
        }

        adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=50)
        session.mount('http://', adapter)
        session.mount('https://', adapter)

        # Адаптивный User-Agent для пинга
        session.headers.update({'User-Agent': random.choice(user_agents)})

        try:
            # Этап 1: Быстрый пинг через https://httpbin.org/ip
            response = session.get("https://httpbin.org/ip", timeout=(PING_TIMEOUT_CONNECT, PING_TIMEOUT_READ))
            
            # Валидируем ТЕЛО ОТВЕТА
            data = response.json()
            origin = data.get('origin')
            # Проверяем, что это именно наш IP, а не заглушка провайдера или HTML-код ошибки
            if response.status_code != 200 or not isinstance(origin, str) or ip not in origin:
                continue  # Следующий протокол

            # 📌 Симметрия портов
            # Игнорируем порты из вашего входящего диапазона (например, если вы слушаете на 8080–8090)
            INCOMING_PORT_RANGE = range(8080, 8091)
            if int(port) in INCOMING_PORT_RANGE:
                print(f"[FAIL] {full_proxy_url} - Port symmetry detected.")
                continue

            # Этап 2: Тест нашего конкретного аудио-потока
            # Здесь меняем User-Agent на плеер
            session.headers.update({
                'User-Agent': 'VLC/3.0.16 LibVLC/3.0.16'  # Пример реального плеера
            })

            # Более долгий таймаут для скачивания данных
            response = session.get("https://listen7.myradio24.com/iridium", stream=True, timeout=(STREAM_TIMEOUT_CONNECT, STREAM_TIMEOUT_READ))  
            
            start_time = get_current_time()
            data_chunk = response.raw.read(8192)  # Читаем примерно 8 КБ
            end_time = get_current_time()

            # Метрика успеха №2: Получено минимум 10 байт данных
            if not data_chunk or len(data_chunk) < 10:
                print(f"[FAIL] {full_proxy_url} - Audio stream failed")
                return None

            elapsed_seconds = end_time - start_time
            speed_kbps = len(data_chunk) / elapsed_seconds / 1024  # KB/s

            latency = round((end_time - start_time) * 1000, 2)

            # Минимальная скорость ~20 KB/s.
            if speed_kbps < 20:
                print(f"[FAIL] {full_proxy_url} - Speed too low ({speed_kbps:.2f} KB/s)")
                return None

            # Сохраняем результат как словарь
            result = {
                'url': full_proxy_url,
                'latency_ms': latency,
                'speed_kbps': speed_kbps,
            }
            results.append(result)

        except Exception as e:
            print(f"[FAIL] {full_proxy_url} - Error:", str(e))

    # Возвращаем ВСЕ рабочие варианты для этого IP
    return results


if __name__ == "__main__":
    MAX_WORK_TIME_MINUTES = 25
    TARGET_PROXY_COUNT_BASE = 30  # Базовое число
    RESERVE_PERCENTAGE = 0.2  # Запас 20%

    # Кэшируем список прокси из API между запусками
    cached_sources_file = ".cached_sources.json"
    all_proxies = []

    # Загружаем старый файл с предыдущими рабочими прокси
    old_proxies_dict = {}
    try:
        with open("working_proxies.txt", "r") as file:
            lines = file.readlines()
            for line in lines:
                parts = line.strip().split('|')
                url = parts[0].strip()  # Берём только URL
                ip = url.split('//')[1].split(':')[0]
                ports = old_proxies_dict.setdefault(ip, set())
                ports.add(url)
        print("[INFO] Previous proxy list loaded.")
    except FileNotFoundError:
        pass

    # Сначала проверяем старые прокси
    print("\n[INFO] Checking previous working proxies...")
    found_old_proxies = []
    for ip, urls in old_proxies_dict.items():
        for url in urls:
            # Мы уже знаем полный URL, так что сразу передаём его целиком
            results = check_proxy(url.replace('http://', '').replace('socks5h://', ''))
            if results:
                found_old_proxies.extend(results)

    # Теперь проверяем новые источники
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
    found_new_proxies = []
    for proxy in all_proxies:
        # Проверка лимита времени
        elapsed_minutes = (datetime.datetime.now() - start_script_time).total_seconds() / 60
        if elapsed_minutes >= MAX_WORK_TIME_MINUTES:
            break

        sleep(0.1)
        results = check_proxy(proxy.strip())
        if results:
            found_new_proxies.extend(results)

    # ✅ Объединение результатов
    # Считаем динамическую цель: базовое количество + запас
    total_target_count = int(TARGET_PROXY_COUNT_BASE * (1 + RESERVE_PERCENTAGE))

    # Преобразуем результаты в удобный вид для записи
    # {IP: {port1, port2}} -> чтобы не было дублей
    unique_results = {}
    for item in found_old_proxies + found_new_proxies:
        ip = item['url'].split('//')[1].split(':')[0]
        ports = unique_results.setdefault(ip, {})
        ports[item['url']] = item

    # Сортируем по скорости
    sorted_items = sorted([v for p in unique_results.values() for v in p.values()],
                          key=lambda x: x['speed_kbps'], reverse=True)

    # Берём нужное количество
    final_list = sorted_items[:total_target_count]

    # Сохраняем основной рабочий файл
    with open("working_proxies.txt", "w") as file:
        # Формат: URL | Latency ms | Speed KB/s
        for item in final_list:
            file.write(f"{item['url']} | {item['latency_ms']} | {item['speed_kbps']:.2f}\n")
