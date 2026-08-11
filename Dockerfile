# Используем минималистичный образ Python 3.11 с системой Debian Bookworm.
FROM python:3.11-slim-bookworm AS base

# Устанавливаем системные пакеты:
# - mpv — медиаплеер для воспроизведения потока;
# - ffmpeg — библиотека для работы с аудио/видео внутри mpv;
# - libgomp1 — обязательная зависимость FFmpeg в этом образе Python;
# - curl и ca-certificates — для корректной работы HTTPS-запросов.
RUN apt-get update && \
    apt-get install --no-install-recommends -y mpv ffmpeg libgomp1 curl ca-certificates && \
    rm -rf /var/lib/apt/lists/* # Очищаем кэш пакетов после установки.

# Создаём рабочую директорию и копируем туда наш проект.
WORKDIR /app
COPY . .

# Устанавливаем Python-зависимости из файла requirements.txt.
# Если у вас нет этого файла или он пустой, можно закомментировать эту строку.
# RUN pip install --no-cache-dir -r requirements.txt

# Запускаем приложение.
CMD ["python", "radio_listener.py"]
