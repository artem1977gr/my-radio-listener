import requests
from time import sleep, time as get_current_time  # Исправление ошибки!
import datetime

# Список источников. Можно добавить больше сайтов или использовать разные протоколы.
sources = [
    "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=10000&country=all",
]

working_proxies = []

def check_proxy(proxy):
    """Проверяет прокси на работоспособность."""
    
    session = requests.Session()
    proxies = {
        "http": f"http://{proxy}",
        "https": f"http://{proxy}"
    }
    session.proxies.update(proxies)

    # Проверка доступности через Google
    try:
        response = session.get("http://www.google.com", timeout=(3, 3))  # Уменьшили таймаут до 3+3 сек
        if response.status_code != 200:
            print(f"[FAIL] {proxy} - Status code: {response.status_code}")
            return False
    except Exception as e:
        print(f"[FAIL] {proxy} - Connection error:", str(e))
        return False

    # Тест скорости (только заголовки). Тайм-аут чтения уменьшен до 1 секунды.
    try:
        start_time = get_current_time()  # Используем импортированное время
        _ = session.head('http://ip-api.com/json/', timeout=(3, 1))
        end_time = get_current_time()
        latency = round((end_time - start_time) * 1000, 2)
        
        # Увеличим порог до 5 секунд. На бесплатных прокси редко бывают идеальные 3 мс.
        if latency > 5000:
            print(f"[FAIL] {proxy} - Latency too high ({latency} ms)")
            return False
        else:
            print(f"[OK] {proxy} - Latency: {latency} ms")
    except Exception as e:
        print(f"[FAIL] {proxy} - Speed test failed:", str(e))
        return False

    working_proxies.append(proxy)
    return True


if __name__ == "__main__":
    # Запускаем таймер перед циклом парсинга
    start_script_time = datetime.datetime.now()
    MAX_WORK_TIME_MINUTES = 10  # Ограничение по времени работы скрипта

    for source in sources:
        print(f"\n[INFO] Scraping from {source}")
        
        try:
            resp = requests.get(source, timeout=10)
            proxies_list = resp.text.splitlines()
        except Exception as e:
            print(f"[ERROR] Failed to fetch data from {source}:", str(e))
            continue

        for proxy in proxies_list:
            # Проверка лимита времени
            elapsed_minutes = (datetime.datetime.now() - start_script_time).total_seconds() / 60
            if elapsed_minutes >= MAX_WORK_TIME_MINUTES:
                print("[WARNING] Script has been running for more than {} minutes without finding enough working proxies. Stopping.".format(MAX_WORK_TIME_MINUTES))
                break

            # Ставим небольшую задержку между проверками
            sleep(0.1)
            check_proxy(proxy.strip())

    print("\n[INFO] Working proxies:")
    if len(working_proxies) == 0:
        print("[WARNING] No working proxies found.")
    else:
        with open("working_proxies.txt", "w") as file:
            for p in working_proxies:
                file.write(p + "\n")
