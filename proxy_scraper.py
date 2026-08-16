import requests
from time import sleep

# Список сайтов для парсинга
sources = [
    "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=10000&country=all",
    # Добавьте сюда другие источники
]

working_proxies = []

def check_proxy(proxy):
    """Проверяет прокси на работоспособность."""
    # Создаем сессию с этим прокси
    session = requests.Session()
    proxies = {
        "http": f"http://{proxy}",
        "https": f"http://{proxy}"
    }
    session.proxies.update(proxies)

    # 1) Пингуем Google через прокси (проверка доступности)
    try:
        response = session.get("http://www.google.com", timeout=5)
        if response.status_code != 200:
            print(f"[FAIL] {proxy} - Status code: {response.status_code}")
            return False
    except Exception as e:
        print(f"[FAIL] {proxy} - Connection error:", str(e))
        return False

    # 2) Проверяем скорость ответа (оставляем порог в 3 секунды)
    try:
        start_time = time.time()
        _ = session.head('http://ip-api.com/json/', timeout=3)
        end_time = time.time()
        latency = round((end_time - start_time) * 1000, 2)
        
        if latency > 3000:
            print(f"[FAIL] {proxy} - Latency too high ({latency} ms)")
            return False
        else:
            print(f"[OK] {proxy} - Latency: {latency} ms")
    except Exception as e:
        print(f"[FAIL] {proxy} - Speed test failed:", str(e))
        return False

    # Если дошли до этого места — прокси прошел все тесты
    working_proxies.append(proxy)
    return True


for source in sources:
    print(f"\n[INFO] Scraping from {source}")
    try:
        resp = requests.get(source, timeout=10)
        proxies_list = resp.text.splitlines()
    except Exception as e:
        print(f"[ERROR] Failed to fetch data from {source}:", str(e))
        continue

    for proxy in proxies_list:
        # Ставим небольшую задержку между проверками, чтобы не забанили
        sleep(0.1)
        check_proxy(proxy.strip())

print("\n[INFO] Working proxies:")
if len(working_proxies) == 0:
    print("[WARNING] No working proxies found.")
else:
    with open("working_proxies.txt", "w") as file:
        for p in working_proxies:
            file.write(p + "\n")
