# Makefile for SHIFA module development
# Usage: make <target>
# Default variables (you can pass overrides on the command line):
#   make ODOO_DB=mydb ODOO_SERVICE=odoo

MODULE ?= shifa
ODOO_DB ?= odoo
ODOO_SERVICE ?= odoo
DOCKER_COMPOSE ?= docker-compose
DIST_DIR ?= dist

.PHONY: help build zip dev up down restart upgrade shell tests run-local clean

help:
	@echo "Available targets:"
	@echo "  make build        -> build artifacts (currently: zip)"
	@echo "  make zip          -> create dist/$(MODULE).zip for installation"
	@echo "  make dev          -> start the Odoo service via docker-compose (foreground)"
	@echo "  make up           -> start services (docker-compose up -d)"
	@echo "  make down         -> stop services (docker-compose down)"
	@echo "  make restart      -> restart Odoo service"
	@echo "  make upgrade      -> upgrade the $(MODULE) module in the running Odoo container"
	@echo "  make shell        -> open an Odoo shell inside the running container"
	@echo "  make tests        -> run module tests (uses docker-compose exec)"
	@echo "  make run-local    -> run odoo-bin locally (requires odoo-bin in PATH)"
	@echo "  make clean        -> remove dist artifacts"

build: zip

zip:
	@echo "Creating $(DIST_DIR)/$(MODULE).zip..."
	@mkdir -p $(DIST_DIR)
	# Create zip with module folder at the archive root (Odoo expects shifa/... inside the zip)
	@(cd addons && zip -r ../$(DIST_DIR)/$(MODULE).zip $(MODULE) -x "*/__pycache__/*" "*.pyc" "*/.git/*")
	@echo "Created $(DIST_DIR)/$(MODULE).zip (module is at top-level inside the archive)"

dev:
ifeq ($(wildcard docker-compose.yml),)
	@echo "docker-compose.yml not found in repository root — cannot start via make dev"
	@exit 1
else
	@echo "Starting $(ODOO_SERVICE) (foreground) using docker-compose..."
	$(DOCKER_COMPOSE) up --build $(ODOO_SERVICE)
endif

up:
ifeq ($(wildcard docker-compose.yml),)
	@echo "docker-compose.yml not found"
	@exit 1
else
	$(DOCKER_COMPOSE) up -d
	@echo "Services started"
endif

down:
ifeq ($(wildcard docker-compose.yml),)
	@echo "docker-compose.yml not found"
	@exit 1
else
	$(DOCKER_COMPOSE) down
	@echo "Services stopped"
endif

restart:
ifeq ($(wildcard docker-compose.yml),)
	@echo "docker-compose.yml not found"
	@exit 1
else
	$(DOCKER_COMPOSE) restart $(ODOO_SERVICE)
	@echo "Restarted $(ODOO_SERVICE)"
endif

upgrade:
ifeq ($(wildcard docker-compose.yml),)
	@echo "docker-compose.yml not found — cannot run upgrade via docker-compose"
	@exit 1
else
	@echo "Upgrading module $(MODULE) on DB $(ODOO_DB) inside service $(ODOO_SERVICE)"
	$(DOCKER_COMPOSE) exec -T $(ODOO_SERVICE) odoo -d $(ODOO_DB) -u $(MODULE) --stop-after-init
	@echo "Upgrade finished"
endif

shell:
ifeq ($(wildcard docker-compose.yml),)
	@echo "docker-compose.yml not found — cannot open shell via docker-compose"
	@exit 1
else
	$(DOCKER_COMPOSE) exec -T $(ODOO_SERVICE) odoo shell -d $(ODOO_DB)
endif

tests:
ifeq ($(wildcard docker-compose.yml),)
	@echo "docker-compose.yml not found — cannot run tests via docker-compose"
	@exit 1
else
	@echo "Running tests for module $(MODULE) on DB $(ODOO_DB)"
	$(DOCKER_COMPOSE) exec -T $(ODOO_SERVICE) odoo -d $(ODOO_DB) -i $(MODULE) --test-enable --stop-after-init
	@echo "Tests finished"
endif

run-local:
	@echo "Run odoo locally (requires odoo-bin and a config file). Example: make run-local ODOO_DB=mydb"
	@echo "This target will try to run: odoo-bin -d $(ODOO_DB) --dev=all"
	odoo-bin -d $(ODOO_DB) --dev=all

clean:
	rm -rf $(DIST_DIR)
	@echo "Cleaned $(DIST_DIR)"
