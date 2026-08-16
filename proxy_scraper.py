import requests
from time import sleep, time as get_current_time
import datetime
import os  # Для переименования файла под workflow

# ⚡️ НАИБОЛЕЕ НАДЁЖНЫЕ ИСТОЧНИКИ — ВНАЧАЛЕ СПИСКА!
sources = [
    "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=10000&country=all",  # API HTTP(S)
    "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/http.txt",
    
    # Остальные источники идут после них
    "https://api.proxyscrape.com/v2/?request=getproxies&protocol=socks4&timeout=10000&country=all",
    "https://api.proxyscrape.com/v2/?request=getproxies&protocol=socks5&timeout=10000&country=all",
    "https://www.proxy-list.download/api/v1/get?type=http&anon=elite",  # Только элитные анонимные
    "https://www.proxy-list.download/api/v1/get?type=socks4",
    "https://www.proxy-list.download/api/v1/get?type=socks5",

    # Текстовые файлы с GitHub
    "https://raw.githubusercontent.com/Hitsounds/proxy-scraper/main/proxies/free_proxies.txt",
    "https://raw.githubusercontent.com/Hitsounds/proxy-scraper/main/proxies/premium_proxies.txt",
    "https://raw.githubusercontent.com/RichardLitt/awesome-proxies/master/proxies.json",  # JSON-файл, но скрипт умеет парсить текст
    "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt",
    "https://raw.githubusercontent.com/hendrikbgr/Free-Proxy-Repo/master/proxy_list.txt",
    "https://raw.githubusercontent.com/shiftytr/proxy-list/master/proxy.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies_http.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies_socks4.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies_socks5.txt",
    "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/http.txt",
    "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/socks4.txt",
    "https://https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/socks5.txt",
    "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/proxy.txt",
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
        
        # ✅ Правильная сборка полного URL для прокси
        full_proxy_url = f"{protocol}://{proxy_str}"
        proxies = {
            "http": full_proxy_url,
            "https": full_proxy_url
        }
        session.proxies.update(proxies)

        try:
            # Проверяем доступность через httpbin.org/ip (более безопасный способ)
            response = session.get("https://httpbin.org/ip", timeout=(5, 10))
            
            # Метрика успеха №1: Статус-код 200 AND есть тело ответа
            if response.status_code != 200 or len(response.text.strip()) < 10:
                continue  # Следующий протокол
        except Exception as e:
            print(f"[FAIL] {full_proxy_url} - Connection error:", str(e))
            continue

        # Тест нашего конкретного аудио-потока
        # Мы проверяем реальное получение данных из потока
        try:
            # Проверим возможность получить данные из потока
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
            # Для комфортного стриминга нужно больше,
            # но мы можем снизить порог до 15–16 KB/s при необходимости.
            if speed_kbps < 20:
                print(f"[FAIL] {full_proxy_url} - Speed too low ({speed_kbps:.2f} KB/s)")
                return False

            # Сохраняем кортеж: (скорость, готовый URL)
            working_proxies.append((speed_kbps, full_proxy_url))
            print(f"[OK] {full_proxy_url} - Latency: {latency} ms | Speed: {speed_kbps:.2f} KB/s")
            return True
        except Exception as e:
            print(f"[FAIL] {full_proxy_url} - Audio test failed:", str(e))
            break


if __name__ == "__main__":
    # Запускаем таймер перед циклом парсинга
    start_script_time = datetime.datetime.now()
    MAX_WORK_TIME_MINUTES = 25  # Увеличенный лимит времени
    TARGET_PROXY_COUNT = 30  # Цель — найти именно столько

    found_count = 0

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
            if elapsed_minutes >= MAX_WORK_TIME_MINUTES or found_count >= TARGET_PROXY_COUNT:
                print("[WARNING] Script has reached the target number of proxies or time limit.")
                break

            sleep(0.1)
            result = check_proxy(proxy.strip())
            if result:
                found_count += 1

    # ✅ СОРТИРУЕМ ПО СКОРОСТИ ОТ БОЛЬШЕЙ К МЕНЬШЕЙ
    sorted_proxies = sorted(working_proxies, key=lambda x: x[0], reverse=True)

    # СРАЗУ СОХРАНЯЕМ В ФАЙЛ, КОТОРЫЙ ЖДЁТ GITHUB ACTIONS
    with open("working_proxies.txt", "w") as file:
        for _, p in sorted_proxies[:TARGET_PROXY_COUNT]:  # Берём первые 30 самых быстрых
            file.write(p + "\n")
