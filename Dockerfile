FROM python:slim

WORKDIR /app

COPY requirements.txt .

RUN apt-get update && apt-get install -y \
    ffmpeg git \
    build-essential libffi-dev python3-dev \
    libmagic1 \  # Ajout de libmagic
    && echo "FFmpeg installed successfully. Version:" \
    && ffmpeg -version \
    && rm -rf /var/lib/apt/lists/*

# Alternative pour python-magic (si nécessaire)
RUN pip install --no-cache-dir python-magic-bin==0.4.14; exit 0
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python3", "main.py"]