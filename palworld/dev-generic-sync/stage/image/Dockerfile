FROM palworld-pufferpanel:steamcmd-xdg

USER root

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3-minimal \
    && rm -rf /var/lib/apt/lists/*

COPY palworld_settings_sync.py /usr/local/bin/palworld-settings-sync
COPY palworld-start-wrapper.sh /usr/local/bin/palworld-start-wrapper

RUN chmod 0755 \
    /usr/local/bin/palworld-settings-sync \
    /usr/local/bin/palworld-start-wrapper
