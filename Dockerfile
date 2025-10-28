FROM odoo:18

USER root

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        chromium \
        chromium-driver \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

COPY ./addons /mnt/extra-addons
RUN chown -R odoo:odoo /mnt/extra-addons

USER odoo
