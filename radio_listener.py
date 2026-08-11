def keep_radio_alive():
    print(f"[{time.strftime('%H:%M:%S')}] Starting listener for {RADIO_URL}...")
    
    headers = {
        'User-Agent': (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
        ),
        'Icy-MetaData': '1'
    }

    try:
        with requests.get(RADIO_URL, stream=True, timeout=20, headers=headers) as response:
            #### МИНИМАЛЬНОЕ ИЗМЕНЕНИЕ ####
            # Добавляем начало отсчёта времени для каждой новой сессии
            start_time = time.time() 

            if not response.ok or 'location' in response.headers:
                raise Exception(
                    f"HTTP Error {response.status_code}: {response.reason}. "
                    f"\nURL: {RADIO_URL}"
                    f"\nHeaders sent by server: {dict(response.headers)}"
                )
            
            player = subprocess.Popen([
                'mpv', '--no-video', '--quiet', '-'],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

            buffer_size = 65536  
            
            #### КЛЮЧЕВАЯ ПРАВКА ###
            # Внутри основного цикла мы проверяем длительность текущей сессии
            for chunk in response.iter_content(chunk_size=buffer_size):
                elapsed = int(time.time() - start_time)
                
                # Завершаем сессию после SESSION_DURATION_SECONDS
                if elapsed >= SESSION_DURATION_SECONDS:
                    print(f"[{datetime.now():%H:%M:%S}] Session ended after {elapsed} seconds.")
                    break # Выход из цикла -> конец сессии

                # Если сервер закрыл соединение раньше времени
                if not chunk:
                    print(f"[{datetime.now():%H:%M:%S}] Stream closed by server after {elapsed} seconds.")
                    break

                player.stdin.write(chunk)
                player.stdin.flush()

                # Дополнительная проверка: если mpv завершился сам
                if player.poll() is not None:
                    break

    except requests.exceptions.RequestException as e:
        print(f"[{datetime.now():%H:%M:%S}] Connection error: {e}. Reconnecting immediately...")
        
    finally:
        # Завершаем процесс плеера
        if 'player' in locals() and player.poll() is None:
            player.terminate()
            try:
                player.wait(timeout=5)
            except subprocess.TimeoutExpired:
                player.kill()
