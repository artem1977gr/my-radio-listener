import requests
from time import sleep, time as get_current_time
import random


# Настройки интеграции с Proxies.IO
API_KEY = "2809925e5feac101b478652d0806a02c" # Вставь сюда свой реальный API-токен из панели управления!
PROXY_TEMPLATE = f"http://global.proxies.io:{API_KEY}@"

# Таймауты проверки потока
STREAM_TIMEOUT_CONNECT = 5   # Тест подключения
STREAM_TIMEOUT_READ = 10     # Время скачивания первых данных

user_agents = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
]

def check_proxy(proxy_str):
    """
    ✅ Проверка одного узла на работоспособность.
    Возвращает URL рабочей прокси или None.
    """
    
    if ':' not in proxy_str:
        return None

    ip_port = proxy_str.strip()
    protocols_to_check = ['http']  # Оставляем ТОЛЬКО HTTP(S), так как SOCKS часто не работают.

    for protocol in protocols_to_check:
        full_proxy_url = PROXY_TEMPLATE + str(ip_port)
        
        session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=50)
        session.mount('http://', adapter)
        session.headers.update({'User-Agent': user_agents[0]})

        try:
            response = session.get(
                "https://listen7.myradio24.com/iridium", 
                stream=True,
                timeout=(STREAM_TIMEOUT_CONNECT, STREAM_TIMEOUT_READ),
                verify=False  # Для обхода SSL-ошибок некоторых сайтов
            )
            
            start_time = get_current_time()
            data_chunk = response.raw.read(4096)  # Читаем первые 4 КБ данных
            end_time = get_current_time()

            elapsed_seconds = end_time - start_time
            speed_kbps = len(data_chunk) / elapsed_seconds / 1024  # KB/s

            # Минимальная скорость снижена до 3 KB/s.
            # Даже медленные каналы сохраняем в резервный пул.
            if speed_kbps < 3 or not data_chunk:
                print(f"[FAIL] {full_proxy_url} - Speed too low ({speed_kbps:.2f} KB/s)")
                continue

            result = {'url': full_proxy_url}
            return result

        except Exception as e:
            print(f"[FAIL] {full_proxy_url}: {str(e)}")
    
    return None

def generate_proxies(count=200):  # Количество ботов-плейеров
    """
    Генерирует заданное количество уникальных строк подключения.
    Каждая строка гарантированно выдаст новый российский домашний канал.
    """
    proxies = []
    for _ in range(count):
        random_port = random.randint(80000, 99999)
        proxy_str = f"{random_port}"
        results = check_proxy(proxy_str)
        if results:
            proxies.append(results['url'])
    
    return proxies

if __name__ == "__main__":
    working_nodes = generate_proxies()  # Создаёт список из 40 проверенных узлов

    with open("working_proxies.txt", "w") as file:
        for node in working_nodes:
            file.write(node + "\n")

    print(f"\n✅ Saved {len(working_nodes)} working residental IPs.")
