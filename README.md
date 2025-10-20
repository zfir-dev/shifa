# shifa

## Development

To run Odoo locally with live-reload of the `addons/` folder, an override compose file is provided.

Usage (development):

```bash
# default docker-compose picks up docker-compose.override.yaml automatically
docker-compose up
```

Usage (production):

Build the image (Dockerfile copies `./addons` into the image) and run without the local bind mount:

```bash
docker-compose build --no-cache
docker-compose up -d
```

