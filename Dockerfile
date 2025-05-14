FROM python:3.11-slim

# Définir le répertoire de travail
WORKDIR /app

# Copie des dépendances
COPY requirements.txt .

# Installation des dépendances système et ffmpeg
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    software-properties-common \
    gnupg2 \
    wget \
    git \
    build-essential \
    libffi-dev \
    python3-dev \
    libmagic1 \
    ca-certificates \
    && wget -O - https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-64bit-static.tar.xz | tar xJ && \
    mv ffmpeg-*-static/ffmpeg /usr/local/bin/ && \
    mv ffmpeg-*-static/ffprobe /usr/local/bin/ && \
    chmod +x /usr/local/bin/ffmpeg /usr/local/bin/ffprobe && \
    echo "FFmpeg installed successfully. Version:" && \
    ffmpeg -version && \
    apt-get remove --purge -y software-properties-common wget && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/* ffmpeg-*-static

# Installer les dépendances Python
RUN pip install --no-cache-dir -r requirements.txt

# Copier le reste du projet
COPY . .

# Commande de démarrage
CMD ["python3", "main.py"]
