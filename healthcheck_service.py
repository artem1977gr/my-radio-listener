import requests
import time
import random
import shutil

# Используйте тот же пул соединений и настройки сертификатов
pool_manager = PoolManager(num_pools=10, maxsize=50, retries=Retry(total=3), ca_certs=certifi.where())
user_agent_player = 'VLC/3.0.16 LibVLC/3.0.16'

def is_alive(proxy_url):
    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=50)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    session.headers.update({'User-Agent': user_agent_player})

    try:
        # Короткий пинг для быстрой проверки
        response = session.get("https://httpbin.org/ip", timeout=(3, 5))
        if response.status_code != 200:
            return False

        # Проверка тела ответа
        data = response.json()
        origin = data.get('origin')
        if not isinstance(origin, str):
            return False

        # Проверка потока (очень короткий таймаут)
        response = session.get("https://listen7.myradio24.com/iridium", stream=True, timeout=(5, 10))
        data_chunk = response.raw.read(1024)  # Достаточно небольшого кусочка
        return bool(data_chunk)
    except Exception:
        return False

def main():
    while True:
        try:
            # Загружаем текущий список
            current_proxies = []
            with open("working_proxies.txt", "r") as file:
                for line in file:
                    parts = line.strip().split('|')
                    url = parts[0].strip()
                    current_proxies.append(url)

            # Загружаем резерв
            reserve_proxies = []
            with open("reserve_proxies.txt", "r") as file:
                for line in file:
                    parts = line.strip().split('|')
                    url = parts[0].strip()
                    reserve_proxies.append(url)

            # Проверяем каждый узел
            dead_nodes = []
            for i, url in enumerate(current_proxies):
                alive = is_alive(url)
                if not alive:
                    print(f"[HEALTHCHECK] Node {i+1}/{len(current_proxies)}: {url} is DEAD.")
                    dead_nodes.append(i)
                else:
                    print(f"[HEALTHCHECK] Node {i+1}/{len(current_proxies)}: {url} is OK.")

            # Удаляем мёртвые узлы и добавляем замену из резерва
            if dead_nodes:
                # Копируем резервный список, чтобы случайно не исчерпать его
                replacement_pool = reserve_proxies.copy()
                random.shuffle(replacement_pool)  # Случайный порядок замены

                # Открываем файл на перезапись
                with open("working_proxies.txt", "w") as file:
                    index = 0
                    for i in range(len(current_proxies)):
                        if i in dead_nodes:
                            # Добавляем замену, если она есть
                            if replacement_pool:
                                repl_url = replacement_pool.pop(0)
                                print(f"[HEALTHCHECK] Replacing {current_proxies[i]} with {repl_url}.")
                                file.write(f"{repl_url} | UNKNOWN | UNKNOWN\n")
                            else:
                                # Нет замены, оставляем пустую строку
                                print(f"[HEALTHCHECK] No replacements left for {current_proxies[i]}.")
                                file.write("\n")
                        else:
                            # Просто переписываем живую строку
                            file.write(linecache.getline("working_proxies.txt", i + 1))

                # Делаем бэкап старого рабочего файла
                shutil.copyfile("working_proxies.txt", "working_proxies_backup.txt")

                print("[HEALTHCHECK] Working proxies updated.")

        except Exception as e:
            print(f"[ERROR] Healthcheck error: {e}")

        # Балансировка нагрузки: Sleep 2–3 минуты
        sleep(random.randint(120, 180))

if __name__ == "__main__":
    main()
