import requests
from time import sleep, time as get_current_time
import datetime
import os  # Для переименования файла под workflow
import random
import json
import re  # <--- Добавлено для регулярных выражений


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
PING_TIMEOUT_READ = 5      # Сократили время проверки доступности стрима
STREAM_TIMEOUT_CONNECT = 5  # Тест полной скорости
STREAM_TIMEOUT_READ = 20

user_agents = [  # Ротация UA
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64; rv:88.0) Gecko/20100101 Firefox/88.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1'
]

working_proxies = []  # Сюда будут попадать только прошедшие проверку

# Регулярное выражение для проверки формата IPv4:Port
PROXY_PATTERN = re.compile(r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?):\d+$')

def load_proxies_from_source(raw_text):
    """Загружает прокси из сырого текста, фильтруя по формату."""
    lines = raw_text.splitlines()
    valid_proxies = []
    
    for line in lines:
        candidate = line.strip()
        # Проверяем, похожа ли строка на прокси, и нет ли в ней HTML-тегов или мусора
        if PROXY_PATTERN.match(candidate) and '<' not in candidate and '>' not in candidate:
            valid_proxies.append(candidate)
            
    return valid_proxies

def check_proxy(proxy_str):
    """
    ✅ УЛУЧШЕННАЯ проверка одного IP:PORT.
    Теперь быстрее и эффективнее находит рабочие узлы.
    """
    
    if ':' not in proxy_str:
        return None  # Не валидный формат

    ip, port = proxy_str.split(':')

    # 🔥 ИЗМЕНЕНИЕ: Оставляем ТОЛЬКО HTTP(S).
    # Socks5 часто работает нестабильно или не поддерживает CONNECT через SSL/TLS.
    protocols_to_check = ['http']

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
            # Этап 1: БЫСТРАЯ ПРОВЕРКА ДОСТУПНОСТИ СТРИМА
            # Читаем всего 4 КБ данных за 5 секунд.
            # Это позволяет быстро отсечь мёртвые узлы.
            response = session.get("https://listen7.myradio24.com/iridium", stream=True, timeout=(PING_TIMEOUT_CONNECT, PING_TIMEOUT_READ))  
            
            start_time = get_current_time()
            data_chunk = response.raw.read(4096)  # Меньше данных для быстрой диагностики
            end_time = get_current_time()

            # Метрика успеха №1: Получено минимум 1 Кбайт данных
            if not data_chunk or len(data_chunk) < 1024:
                print(f"[FAIL] {full_proxy_url} - Audio stream failed")
                continue  # Следующий протокол

            elapsed_seconds = end_time - start_time
            speed_kbps = len(data_chunk) / elapsed_seconds / 1024  # KB/s

            # 🔥 ИЗМЕНЕНИЕ: Понижаем планку скорости до 10 KB/s.
            # Для потокового аудио это критично важно!
            if speed_kbps < 10:
                print(f"[FAIL] {full_proxy_url} - Speed too low ({speed_kbps:.2f} KB/s)")
                continue

            latency = round((end_time - start_time) * 1000, 2)

            # Этап 2: ГЛУБОКАЯ ПРОВЕРКА СКОРОСТИ (опционально удалён)
            # Мы можем оставить старый таймаут на 20 сек, 
            # но для экономии времени лучше убрать эту часть.

            # Просто возвращаем URL рабочей прокси
            result = {'url': full_proxy_url}
            results.append(result)

        except Exception as e:
            print(f"[FAIL] {full_proxy_url} - Error:", str(e))

    # Возвращаем ВСЕ рабочие варианты для этого IP
    return results


if __name__ == "__main__":
    MAX_WORK_TIME_MINUTES = 25
    TARGET_PROXY_COUNT_BASE = 10  # Я снизил базовое число до 10 для начала
    RESERVE_PERCENTAGE = 0.2  # Запас 20%

    # Кэшируем список прокси из API между запусками
    cached_sources_file = ".cached_sources.json"
    all_proxies = []

    # Загружаем старый файл с предыдущими рабочими прокси
    old_proxies_dict = {}
    try:
        with open("working_proxies.txt", "r") as file:
            # Строгий разбор каждой строки старого файла
            for line in file:
                parts = line.strip().split('|')
                url = parts[0].strip()  # Берём только URL
                
                _, address = url.split('://')[:2]
                # Проверка регуляркой: должен соответствовать формату IPv4:Port
                if not PROXY_PATTERN.match(address):
                    raise ValueError(f"Invalid format: {address}")

                ip_port = address.split(':')
                # Разбиваем на IP и PORT
                if len(ip_port) != 2 or not ip_port[1].isdigit():
                    raise ValueError(f"Invalid format: {url}")

                ip, _port = ip_port
                ports = old_proxies_dict.setdefault(ip, {})
                ports[url] = True  # Просто помечаем URL как ранее найденный
    
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
            # Всегда проверяем кэшированные данные тем же способом,
            # чтобы исключить любые ошибки разбора
            cached_data = json.load(cache_file)
            all_proxies = load_proxies_from_source("\n".join(cached_data))
    
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
                
                # Фильтруем строки ДО добавления их в общий массив.
                # Это гарантирует, что в all_proxies никогда не попадёт мусор.
                valid_lines = load_proxies_from_source(resp.text)

                # Проверяем, что мы получили хоть что-то валидное
                if len(valid_lines) == 0:
                    print("[WARNING] Source returned no valid proxies.")
                else:
                    all_proxies.extend(valid_lines)

            except Exception as e:
                print(f"[ERROR] Failed to fetch data from {source}:", str(e))
                continue

        # Сохраняем кэш только после того, как все источники прошли фильтрацию
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

    # Объединение результатов
    total_target_count = int(TARGET_PROXY_COUNT_BASE * (1 + RESERVE_PERCENTAGE))

    unique_results = {}  # {IP: {port1, port2}} -> чтобы не было дублей
    for item in found_old_proxies + found_new_proxies:
        ip = item['url'].split('//')[1].split(':')[0]
        ports = unique_results.setdefault(ip, {})
        ports[item['url']] = item

    sorted_items = sorted([v for p in unique_results.values() for v in p.values()],
                          key=lambda x: x['url'])  # Сортируем просто по URL, т.к. скорость у нас одна

    final_list = sorted_items[:total_target_count]

    # Сохраняем основной рабочий файл
    with open("working_proxies.txt", "w") as file:
        # Формат: Только чистый URL
        # Больше не сохраняем Latency и Speed, они нам сейчас не нужны
        for item in final_list:
            file.write(item['url'] + "\n")
