import asyncio
import aiohttp
import random
import time


# Глобальные настройки
RADIOS = [
    # Твой оригинальный список с нужными пропорциями слушателей
    *(['https://listen7.myradio24.com/sintezi'] * 4),
    *(['https://listen7.myradio24.com/sintezi_128'] * 2),
    *(['https://listen7.myradio24.com/rockataka'] * 4),  
    *(['https://listen7.myradio24.com/rockataka_128'] * 2),
    *(['https://listen7.myradio24.com/iridium'] * 2),
    *(['https://listen7.myradio24.com/nevermind'] * 2)
]

REFERER_URL = "https://radio.art-test-1.store"
SESSION_DURATION_MIN = 300  # Минимум 5 минут
SESSION_DURATION_MAX = 400  # Максимум ~6 минут 40 сек

async def keep_radio_alive(session, url):
    """Асинхронно поддерживает подключение к радиостанции."""
    
    headers = {
        'User-Agent': (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/129 Safari/537.36"
        ),
        'Referer': REFERER_URL,
        'Icy-MetaData': '1'  # Для получения названий треков из метаданных потока
    }

    while True:  # Бесконечный цикл для перезапуска после окончания сессии
        session_duration = random.randint(SESSION_DURATION_MIN, SESSION_DURATION_MAX)
        
        try:
            async with session.get(url, timeout=20, headers=headers) as response:
                if response.status != 200:
                    print(f"[{time.strftime('%H:%M:%S')}] Error {response.status} for {url}")
                    await asyncio.sleep(10)  # Подождать перед повторной попыткой
                    continue

                start_time = time.time()
                
                # Поддерживаем соединение активным ровно заданную сессию
                buffer_size = 65536  
                async for chunk in response.content.iter_chunked(buffer_size): 
                    elapsed = int(time.time() - start_time)
                    
                    # Пауза на оставшееся время сессии (~5-6 мин). Экономим ресурсы!
                    await asyncio.sleep(max(0, session_duration - elapsed))

                    # Если мы вышли за пределы времени, прерываем чтение данных
                    if elapsed >= session_duration:
                        break

        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] Connection error: {e}. Reconnecting immediately...")
        
        finally:
            print(f"[{time.strftime('%H:%M:%S')}] Listener for {url} terminated after {session_duration}s.")

async def main():
    async with aiohttp.ClientSession() as session:
        tasks = [asyncio.create_task(keep_radio_alive(session, radio_url)) for radio_url in RADIOS]
        # Все слушатели стартуют ОДНОВРЕМЕННО в фоне
        await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())
