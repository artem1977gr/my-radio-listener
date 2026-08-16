import requests
from time import sleep, time as get_current_time
import datetime
import os  # Для переименования файла под workflow

# ⚡️ НАИБОЛЕЕ НАДЁЖНЫЕ ИСТОЧНИКИ + дополнительные HTTP(S)
sources = [
    "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=10000",  # Без country=all
    "https://www.proxy-list.download/api/v1/get?type=http&anon=elite",
    
    # Дополнительные надёжные источники
    "https://raw.githubusercontent.com/roosterkid/openproxylists/master/MIXED_ANON_HTTP.txt",  # Текстовый файл с GitHub
    "https://api.openproxylist.xyz/http.txt"  # Простой API без параметров
]

working_proxies = []  # Сюда будут попадать только прошедшие проверку

def check_proxy(proxy_str):
    """Проверка одного IP:PORT."""
    
    if ':' not in proxy_str:
        return False  # Не валидный формат

    ip, port = proxy_str.split(':')
    protocols_to_check = ['socks5', 'http'] if int(port) in [1080, 443, 8080] else ['http']

    for protocol in protocols_to_check:
        session = requests.Session()
        
        full_proxy_url = f"{protocol}://{proxy_str}"
        proxies = {
            "http": full_proxy_url,
            "https": full_proxy_url
        }
        session.proxies.update(proxies)

        try:
            response = session.get("https://httpbin.org/ip", timeout=(5, 10), verify=False)
            
            # Метрика успеха №1: Статус-код 200 AND есть тело ответа
            if response.status_code != 200 or len(response.text.strip()) < 10:
                continue  # Следующий протокол
        except Exception as e:
            print(f"[FAIL] {full_proxy_url} - Connection error:", str(e))
            continue

        # Тест нашего конкретного аудио-потока
        try:
            response = session.get("https://listen7.myradio24.com/iridium", stream=True, timeout=(5, 15))  
            
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
            break


if __name__ == "__main__":
    MAX_WORK_TIME_MINUTES = 25
    TARGET_PROXY_COUNT = 30

    # Загружаем старый файл с предыдущими рабочими прокси
    old_proxies = []
    try:
        with open("working_proxies.txt", "r") as file:
            old_proxies = [line.strip() for line in file.readlines()]
        print("[INFO] Previous proxy list loaded.")
    except FileNotFoundError:
        print("[INFO] Previous proxy list not found.")

    # Проверяем сначала все старые прокси
    print("\n[INFO] Checking previous working proxies...")
    for proxy in old_proxies:
        # Мы уже знаем полный URL, так что сразу передаём его целиком
        result = check_proxy(proxy.replace('http://', '').replace('socks5://', ''))

    # Теперь проверяем новые источники
    print("\n[INFO] Fetching and checking new proxies...")
    start_script_time = datetime.datetime.now()

    for source in sources:
        print(f"\n[INFO] Scraping from {source}")
        
        try:
            resp = requests.get(source, timeout=10)
            proxies_list = resp.text.splitlines()
        except Exception as e:
            print(f"[ERROR] Failed to fetch data from {source}:", str(e))
            continue

        for proxy in proxies_list:
            # Проверка лимита времени или количества
            elapsed_minutes = (datetime.datetime.now() - start_script_time).total_seconds() / 60
            if elapsed_minutes >= MAX_WORK_TIME_MINUTES:
                print("[WARNING] Script has reached the time limit.")
                break

            sleep(0.1)
            result = check_proxy(proxy.strip())

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
