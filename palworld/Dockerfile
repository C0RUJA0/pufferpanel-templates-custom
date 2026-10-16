FROM steamcmd/steamcmd:latest

USER root

RUN apt-get update \
    && apt-get install -y --no-install-recommends xdg-user-dirs \
    && rm -rf /var/lib/apt/lists/*
