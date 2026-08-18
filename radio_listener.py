import socket
import time
from urllib.parse import urlparse
from multiprocessing import Process
import random
import os
import base64

# Глобальные настройки потоков
RADIOS = [
    *(['https://listen7.myradio24.com/sintezi'] * 20),
    *(['https://listen7.myradio24.com/rockataka'] * 5), 
    *(['https://listen7.myradio24.com/iridium'] * 3),
    *(['https://listen7.myradio24.com/nevermind'] * 5)
]
REFERER_URL = "https://radio.art-test-1.store"
SESSION_DURATION_MIN = 100   
SESSION_DURATION_MAX = 1600  
READ_TIMEOUT_SEC = 5        

#### НАСТРОЙКИ РЕАЛИСТИЧНЫХ USER-AGENT'ОВ (для рандомных 50%) ###
PLATFORM_WEIGHTS = [
    {"os": "Android", "version": str(random.randint(10, 15)), "weight": 0.4},
    {"os": "iPhone", "version": f"{random.randint(14, 18)}_{random.randint(0, 9)}", "model": f"iPhone{random.randint(10, 15)},2", "weight": 0.35},
    {"os": "Windows", "version": f"NT {random.randint(10, 11)}.0; Win64; x64", "weight": 0.1},
    {"os": "Mac OS X", "version": f"{random.randint(10, 15)}_{random.randint(9, 15)}_{random.randint(5, 9)}", "weight": 0.07},
    {"os": "Linux", "version": "x86_64", "weight": 0.05},
    {"os": "X11", "version": f"Ubuntu; Linux x86_64", "weight": 0.03}
]

BROWSER_WEIGHTS = [
    {"name": "Chrome", "version": f"{random.randint(110, 130)}.0.{random.randint(100, 999)}.0", "weight": 0.6},
    {"name": "Firefox", "version": f"{random.randint(100, 120)}.0", "weight": 0.2},
    {"name": "Safari", "version": f"605.1.{random.randint(10, 20)}", "weight": 0.1},
    {"name": "Edge", "version": f"1{random.randint(0,3)}0.0.{random.randint(100, 999)}", "weight": 0.05},
    {"name": "Opera", "version": f"{random.randint(95, 105)}.0.0.{random.randint(10, 99)}", "weight": 0.05}
]

APP_WEIGHTS = [
    {"type": "android_app", "name": "com.pcradio.player", "version": f"{random.randint(7, 9)}.{random.randint(0, 9)}", "weight": 0.15},
    {"type": "android_app", "name": "tunein.player", "version": f"{random.randint(25, 35)}.{random.randint(0, 9)}", "weight": 0.12},
    {"type": "android_app", "name": "ru.yandex.music", "version": f"{random.randint(2023, 2026)}.{random.randint(10, 50)}", "weight": 0.10},
    {"type": "ios_app", "name": "PCRadio", "bundle": "com.pcradio.player.ios", "version": f"{random.randint(3, 6)}.{random.randint(0, 9)}", "weight": 0.15},
    {"type": "ios_app", "name": "TuneIn", "bundle": "com.tunesoft.tunein", "version": f"{random.randint(25, 35)}.{random.randint(0, 9)}", "weight": 0.12},
    {"type": "ios_app", "name": "Yandex Music", "bundle": "ru.yandex.music", "version": f"{random.randint(2023, 2026)}.{random.randint(10, 50)}", "weight": 0.10},
    {"type": "browser", "weight": 0.13}
]

# ВАША СТАТИСТИКА (для реальных 50%) — веса увеличены на 1
CLIENT_STATS = [
    {"ua": "Android ExoPlayer", "weight": 17},
    {"ua": "RadioGarden", "weight": 12},
    {"ua": "Android Dalvik", "weight": 11},
    {"ua": "Windows Chrome", "weight": 11},
    {"ua": "Android Chrome", "weight": 11},
    {"ua": "Lavf", "weight": 10},
    {"ua": "Go-http-client", "weight": 5},
    {"ua": "unknown", "weight": 5},
    {"ua": "iPhone Safari", "weight": 3},
    {"ua": "iPhone AppleCoreMedia", "weight": 3},
    {"ua": "Winamp", "weight": 3},
    {"ua": "okhttp", "weight": 3},
    {"ua": "RadioBot", "weight": 2},
    {"ua": "LenoRadio", "weight": 2},
    {"ua": "Android Firefox", "weight": 2},
    {"ua": "Windows Firefox", "weight": 2},
    {"ua": "Android Myradio24", "weight": 2},
    {"ua": "Mac OS Darwin", "weight": 2},
    {"ua": "TARV-RadioDiscovery", "weight": 2},
    {"ua": "Python", "weight": 2},
    {"ua": "Mozilla", "weight": 2},
    {"ua": "StreamHealth", "weight": 2},
    {"ua": "PCRADIO-RadioStreamMetadataBot", "weight": 1},
    {"ua": "Linux Chrome", "weight": 1},
    {"ua": "python", "weight": 1},
    {"ua": "Mac OS Chrome", "weight": 1},
    {"ua": "SimpleRadioFree", "weight": 1},
    {"ua": "BASS", "weight": 1},
    {"ua": "Mac OS Safari", "weight": 1},
    {"ua": "Android Radio", "weight": 1},
    {"ua": "ExoPlayer", "weight": 1},
    {"ua": "ZENE-RadioDiscovery", "weight": 1},
    {"ua": "Icecast", "weight": 1},
    {"ua": "FMODStudio", "weight": 1},
    {"ua": "VLC", "weight": 1},
    {"ua": "audio", "weight": 1},
    {"ua": "Myradio24", "weight": 1},
    {"ua": "Music", "weight": 1},
    {"ua": "GlobradioHarvester", "weight": 1},
    {"ua": "Airtune-Healthcheck", "weight": 1},
    {"ua": "Chrome", "weight": 1},
    {"ua": "Linux Firefox", "weight": 1}
]

def generate_user_agent():
    """
    Гибридная модель: 
    50% - строго по вашей статистике CLIENT_STATS
    50% - случайно на основе весов PLATFORM/BROWSER/APP_WEIGHTS
    """
    
    if random.random() < 0.5:
        # --- БЛОК РЕАЛЬНОЙ СТАТИСТИКИ ---
        uas = [item["ua"] for item in CLIENT_STATS]
        weights = [item["weight"] for item in CLIENT_STATS]
        
        selected_ua = random.choices(uas, weights=weights, k=1)[0]

        if selected_ua == "Android Dalvik":
            return f"Dalvik/2.1.0 (Linux; U; Android {random.randint(9, 15)}; Build/{''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ', k=7))})"
        elif selected_ua == "Lavf":
            return f"Lavf/{random.randint(58, 60)}.{random.randint(10, 99)}.100"
        elif selected_ua == "Go-http-client":
            return f"Go-http-client/{random.randint(1, 2)}.0"
        elif selected_ua == "okhttp":
            return f"okhttp/{random.randint(3, 5)}.{random.randint(0, 14)}.{random.randint(0, 4)}"
        elif selected_ua == "Python":
            return f"Python-urllib/{random.randint(3, 4)}.{random.randint(8, 12)}"
        elif selected_ua == "Mozilla":
            return "Mozilla/5.0 (compatible; MSIE 10.0; Windows NT 6.1; Trident/6.0)"
        elif selected_ua == "unknown" or selected_ua == "-":
            return "-"
        else:
            return selected_ua
            
    else:
        # --- БЛОК СЛУЧАЙНЫХ ПРОФИЛЕЙ ---
        total_weight_platforms = sum(item["weight"] for item in PLATFORM_WEIGHTS)
        choice = random.uniform(0, total_weight_platforms)
        current_weight = 0
        for plat in PLATFORM_WEIGHTS:
            current_weight += plat["weight"]
            if choice < current_weight:
                platform_data = plat
                break

        total_weight_apps = sum(item["weight"] for item in APP_WEIGHTS)
        choice = random.uniform(0, total_weight_apps)
        current_weight = 0
        app_data = None
        for app in APP_WEIGHTS:
            current_weight += app["weight"]
            if choice < current_weight:
                app_data = app
                break

        if app_data.get("type") != "browser":
            if app_data["type"].startswith("android"):
                return (
                    f"Dalvik/2.1.0 (Linux; U; Android {platform_data['version']}; "
                    f"{platform_data.get('arch', 'Pixel 7')} Build/{''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ', k=7))}) "
                    f"{app_data['name']}/{app_data['version']} (Linux; Android {platform_data['version']})"
                )
            if app_data["type"].startswith("ios"):
                apple_component = random.choice(["AppleCoreMedia", "VLC", "CFNetwork"])
                version_comp = random.randint(1300, 1500)
                return (
                    f"{apple_component}/{version_comp}.0.0 com.apple.{apple_component.lower()}/1.0 "
                    f"({platform_data['model']}; CPU OS {platform_data['version'].replace('_', '.')} like Mac OS X) "
                    f"{app_data['bundle']}/{app_data['version']} (iOS; N; Scale/3.00)"
                )
                
        browser_choice_total = sum(item["weight"] for item in BROWSER_WEIGHTS)
        b_choice = random.uniform(0, browser_choice_total)
        b_current = 0
        browser_data = None
        for brw in BROWSER_WEIGHTS:
            b_current += brw["weight"]
            if b_choice < b_current:
                browser_data = brw
                break

        if browser_data["name"] == "Safari" and platform_data["os"] == "iPhone":
            ua_template = (
                f"Mozilla/5.0 ({platform_data['model']}; CPU {platform_data['os']} {platform_data['version'].replace('_', '.')} like Mac OS X) "
                f"AppleWebKit/{random.randint(605, 615)}.{random.randint(1, 45)} (KHTML, like Gecko) "
                f"Version/{platform_data['version'].split('_')[0]}.0 Mobile/{random.randint(14, 16)}E{random.randint(140, 250)} Safari/604.1"
            )
        else:
            mobile_token = ""
            if platform_data["os"] in ["Android", "iPhone"]:
                mobile_token = "Mobile "
                
            ua_template = (
                f"Mozilla/5.0 ({platform_data['os']} {platform_data.get('version', '')}; {platform_data.get('arch', '')} {platform_data.get('model', '')}) "
                f"AppleWebKit/{random.randint(537, 605)}.{random.randint(1, 36)} (KHTML, like Gecko) "
                f"{mobile_token}{browser_data['name']}/{browser_data['version']} Safari/537.{random.randint(30, 40)}"
            )

        return ua_template.strip()

def get_random_proxy():
    HYBRID_MODE = bool(os.getenv("USE_HYBRID_PROXIES"))
    default_moscow_ip = (
        "http://[user1234567890abcdefg:hijklmnopqrstuvwxyz]"
        "@listen7.myradio24.com:80"
    )

    if not HYBRID_MODE:
        proxy_list_file = os.getenv("PROXY_LIST_FILE", "./working_proxies.txt")
        try:
            with open(proxy_list_file) as f:
                proxies = [line.strip() for line in f if line.strip()]
                return random.choice(proxies)
        except Exception as e:
            print(f"[ERROR] Error loading proxy list: {e}")
            return default_moscow_ip
    else:
        use_custom_proxy = random.random() < 0.5
        if use_custom_proxy:
            try:
                with open("./working_proxies.txt") as f:
                    proxies = [line.strip() for line in f if line.strip()]
                    return random.choice(proxies)
            except FileNotFoundError:
                pass
        return default_moscow_ip

def keep_radio_alive(url):
    parsed_url = urlparse(url)
    stream_host = parsed_url.netloc.split(':')[0] 
    
    proxy_url = get_random_proxy()
    proxy_parsed = urlparse(proxy_url)
    proxy_host = proxy_parsed.hostname
    proxy_port = int(proxy_parsed.port or 80)

    user_agent_str = generate_user_agent()

    referer_to_send = REFERER_URL
    if user_agent_str.startswith("RadioGarden"):
        referer_to_send = "https://radio.garden/"
    elif user_agent_str.startswith("Android ExoPlayer") or user_agent_str.startswith("Dalvik") or user_agent_str.startswith("Lavf"):
        referer_to_send = "" 
    elif user_agent_str.startswith("Windows") or user_agent_str.startswith("Mac OS"):
        pass 
    else:
        if random.random() < 0.7:
            referer_to_send = ""

    headers = ""
    if parsed_url.scheme == "http":
        headers += f"GET {url} HTTP/1.1\r\n"
    else:
        headers += f"CONNECT {parsed_url.netloc} HTTP/1.1\r\n"

    headers += (
        f"Host: {stream_host}\r\n" \
        f"Icy-MetaData: 1\r\n" \
        f"User-Agent: {user_agent_str}\r\n" \
        f"Referer: {referer_to_send}\r\n" \
        f"Connection: Keep-Alive\r\n"
    )

    if proxy_parsed.password is not None:
        username_password = proxy_parsed.username + ":" + proxy_parsed.password
        base64_encoded_creds = base64.b64encode(username_password.encode()).decode()
        headers += f"Proxy-Authorization: Basic {base64_encoded_creds}\r\n"

    headers += "\r\n"

    while True:  
        session_duration = random.randint(SESSION_DURATION_MIN, SESSION_DURATION_MAX)
        
        try:
            with socket.create_connection((proxy_host, proxy_port)) as sock:
                sock.settimeout(READ_TIMEOUT_SEC)
                sock.sendall(headers.encode())
                
                response_headers = b""
                while True:
                    chunk = sock.recv(4096)
                    if not chunk or b"\r\n\r\n" in response_headers:
                        break
                    response_headers += chunk

                if parsed_url.scheme == "https":
                    status_line = response_headers.decode().split("\n")[0]
                    print(f"[DEBUG] Proxy response for {proxy_url}: {status_line}")
                    if not status_line.startswith("HTTP/1.1 2"):
                        raise Exception(f"Proxy refused connection: {status_line}")

                start_time = time.time()

                while int(time.time() - start_time) < session_duration:
                    try:
                        sock.recv(1024)
                    except socket.timeout:
                        pass
                    except Exception as e:
                        print(f"[{time.strftime('%H:%M:%S')}] Read error for {url}: {e}")
                        break

        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] Connection error for {url}: {e}. Reconnecting...")
        
        finally:
            elapsed = int(time.time() - start_time)
            print(f"[{elapsed//60}:{elapsed%60:02d}] Listener on {proxy_url} ended.")

if __name__ == "__main__":
    processes = []
    for radio_url in RADIOS:
        p = Process(target=keep_radio_alive, args=(radio_url,))
        p.start()
        time.sleep(0.1)
