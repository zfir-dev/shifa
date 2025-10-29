FROM odoo:18

USER root

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    fonts-dejavu-core \
    fontconfig \
    libfreetype6 \
    libjpeg-turbo-progs \
    libpng16-16 \
    libx11-6 \
    libxext6 \
    libxrender1 \
    curl \
    gnupg \
 && rm -rf /var/lib/apt/lists/*

RUN curl -L -o /tmp/wkhtmltox.deb \
      https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6-1/wkhtmltox_0.12.6-1.bookworm_amd64.deb \
 && dpkg -i /tmp/wkhtmltox.deb || apt-get -f install -y \
 && rm /tmp/wkhtmltox.deb

RUN wkhtmltopdf --version

COPY ./addons /mnt/extra-addons
RUN chown -R odoo:odoo /mnt/extra-addons

RUN sed -i '/report.url/d' /etc/odoo/odoo.conf \
 && echo "report.url = http://127.0.0.1:8069" >> /etc/odoo/odoo.conf

USER odoo
