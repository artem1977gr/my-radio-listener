FROM python:3.11-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends mpv curl ca-certificates ffmpeg && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY radio_listener.py ./

CMD ["python", "radio_listener.py"]