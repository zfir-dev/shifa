FROM odoo:18

USER root

RUN apt-get update && apt-get install -y \
    wkhtmltopdf \
    xfonts-75dpi \
    xfonts-base \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN wkhtmltopdf --version

COPY ./addons /mnt/extra-addons
RUN chown -R odoo:odoo /mnt/extra-addons

USER odoo
