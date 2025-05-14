FROM python:slim

WORKDIR /app

# Installer les dépendances minimales
RUN apt-get update && apt-get install -y \
    wget \
    tar \
    xz-utils && \
    rm -rf /var/lib/apt/lists/*

# Télécharger et installer FFmpeg 6.1
RUN wget https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz && \
    tar xf ffmpeg-release-amd64-static.tar.xz && \
    mv ffmpeg-*-amd64-static/ffmpeg /usr/local/bin/ && \
    mv ffmpeg-*-amd64-static/ffprobe /usr/local/bin/ && \
    rm -rf ffmpeg-*

# Vérifier l'installation
RUN ffmpeg -version

# Installer les autres dépendances
RUN apt-get update && apt-get install -y \
    git \
    build-essential \
    libffi-dev \
    python3-dev \
    libmagic1 && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python3", "main.py"]