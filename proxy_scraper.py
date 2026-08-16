import requests
from time import sleep, time as get_current_time
import datetime

# Список источников данных
sources = [
    # Только HTTP(S) прокси
    "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=10000&country=all",
    "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/http.txt",  # Много адресов
    "https://www.proxy-list.download/api/v1/get?type=http&anon=elite",  # Только элитные анонимные

    # Смешанные списки (могут быть как HTTP, так и SOCKS)
    "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/mixed.txt",
    "https://raw.githubusercontent.com/roosterkid/openproxylists/master/MIXED_ANON_HTTP.txt",
]

working_proxies = []

def check_proxy(proxy_str):
    """Проверка одного IP:PORT."""
    
    if ':' not in proxy_str:
        return False  # Не валидный формат

    ip, port = proxy_str.split(':')
    protocols_to_check = ['socks5', 'http'] if int(port) in [1080, 443, 8080] else ['http']

    for protocol in protocols_to_check:
        session = requests.Session()
        proxies = {
            "http": f"{protocol}://{proxy_str}",
            "https": f"{protocol}://{proxy_str}"
        }
        session.proxies.update(proxies)

        try:
            response = session.get("http://www.google.com", timeout=(3, 3))
            if response.status_code != 200:
                continue  # Следующий протокол
        except Exception:
            continue

        # Тест скорости ТОЛЬКО ДЛЯ HTTP(S)
        if protocol == 'http':
            try:
                start_time = get_current_time()
                _ = session.head('http://ip-api.com/json/', timeout=(3, 1))  
                end_time = get_current_time()
                latency = round((end_time - start_time) * 1000, 2)
                
                # Немного увеличил порог до 7 секунд
                if latency > 7_000:
                    print(f"[FAIL] {protocol}:{proxy_str} - Latency too high ({latency} ms)")
                    break
                else:
                    print(f"[OK] {protocol}:{proxy_str} - Latency: {latency} ms")
                    working_proxies.append(f"{protocol}://{proxy_str}")
                    break
            except Exception as e:
                print(f"[FAIL] {protocol}:{proxy_str} - Speed test failed:", str(e))
                break
        
        # Для SOCKS просто добавляем после успешного пинга
        print(f"[OK] {protocol}:{proxy_str}")
        working_proxies.append(f"{protocol}://{proxy_str}")
        break


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
            elapsed_minutes = (datetime.datetime.now() - start_script_time).total_seconds() / 60
            if elapsed_minutes >= MAX_WORK_TIME_MINUTES:
                print("[WARNING] Script has been running for more than {} minutes without finding enough working proxies. Stopping.".format(MAX_WORK_TIME_MINUTES))
                break

            sleep(0.1)
            check_proxy(proxy.strip())

    # СРАЗУ СОХРАНЯЕМ В ФАЙЛ, КОТОРЫЙ ЖДЁТ GITHUB ACTIONS
    with open("working_proxies.txt", "w") as file:
        for p in working_proxies:
            file.write(p + "\n")
