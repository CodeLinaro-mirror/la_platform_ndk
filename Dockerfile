# Fleet 24.04 Dockerfile
FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive

RUN echo "America/Los_Angeles" > /etc/timezone && \
    apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    git-core \
    rsync \
    zip \
    unzip \
    python3 \
    libncurses6 \
    lib32gcc-s1 \
    libc6-i386 \
    libxml2 \
    fontconfig \
    locales \
 && (locale-gen en_US.UTF-8 && export LANG=en_US.UTF-8) \
 && apt-get clean && rm -rf /var/lib/apt/lists/*
