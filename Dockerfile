FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    autoconf \
    automake \
    build-essential \
    cmake \
    git \
    libass-dev \
    libfreetype6-dev \
    libgnutls28-dev \
    libmp3lame-dev \
    libtool \
    libvorbis-dev \
    libvpx-dev \
    libx264-dev \
    libx265-dev \
    pkg-config \
    texinfo \
    wget \
    yasm \
    zlib1g-dev \
    libffi-dev \
    python3-dev \
    libmagic1 \
    && apt-get clean

RUN mkdir -v /ffmpeg_sources && \
    cd /ffmpeg_sources && \
    git clone --depth 1 --branch n6.0 https://git.ffmpeg.org/ffmpeg.git ffmpeg && \
    cd ffmpeg && \
    ./configure \
      --prefix=/usr/local \
      --pkg-config-flags="--static" \
      --enable-gpl \
      --enable-libx264 \
      --enable-libx265 \
      --enable-libvpx \
      --enable-libmp3lame \
      --enable-libass \
      --enable-libfreetype \
      --enable-nonfree \
      --enable-shared && \
    make -j"$(nproc)" && \
    make install && \
    hash -r

RUN echo "FFmpeg successfully installed:" && ffmpeg -version

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python3", "main.py"]
