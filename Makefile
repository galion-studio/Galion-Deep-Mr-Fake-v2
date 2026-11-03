# Developer tasks for the CPU-only web app.
# Details: docs/DEVELOPMENT.md

ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
PYTHON ?= python3
VENV ?= $(ROOT)/web/.venv
PORT ?= 8765
HOST ?= 127.0.0.1
MCP_PORT ?= 8766
IMAGE ?= galion-deep-mr-fake-web:local

.DEFAULT_GOAL := help
.PHONY: help install run mcp mcp-http lint format docker-build docker-run up down

help:
	@echo "Galion Deep Mr Fake v2 — developer tasks"
	@echo ""
	@echo "  make install        Create web/.venv and install runtime + dev tools"
	@echo "  make run            Serve the app at http://$(HOST):$(PORT)"
	@echo "  make mcp            MCP server on stdio (agents connect to this process)"
	@echo "  make mcp-http       MCP server at http://127.0.0.1:$(MCP_PORT)/mcp"
	@echo "  make lint           Ruff lint (see ruff.toml)"
	@echo "  make format         Ruff format, Black-compatible"
	@echo "  make docker-build   Build the CPU-only image ($(IMAGE))"
	@echo "  make docker-run     Run that image and publish port 8765"
	@echo "  make up             docker compose up --build"
	@echo "  make down           docker compose down"
	@echo ""
	@echo "Override Python with PYTHON=, the web port with PORT=, the MCP port with MCP_PORT=."
	@echo "Format check (no writes): CHECK=1 make format"
	@echo "Guide: docs/DEVELOPMENT.md"

install:
	PYTHON="$(PYTHON)" VENV="$(VENV)" "$(ROOT)/web/scripts/install.sh"

run:
	VENV="$(VENV)" HOST="$(HOST)" PORT="$(PORT)" "$(ROOT)/web/scripts/run.sh"

mcp:
	@test -x "$(VENV)/bin/python" || (echo "Run: make install" >&2; exit 1)
	cd "$(ROOT)/web" && exec "$(VENV)/bin/python" mcp_server.py

mcp-http:
	@test -x "$(VENV)/bin/python" || (echo "Run: make install" >&2; exit 1)
	cd "$(ROOT)/web" && exec "$(VENV)/bin/python" mcp_server.py --http --host 127.0.0.1 --port "$(MCP_PORT)"

lint:
	VENV="$(VENV)" "$(ROOT)/web/scripts/lint.sh"

format:
	VENV="$(VENV)" "$(ROOT)/web/scripts/format.sh"

docker-build:
	docker build -t "$(IMAGE)" "$(ROOT)"

docker-run: docker-build
	docker run --rm --name galion-deep-mr-fake-web -p 8765:8765 "$(IMAGE)"

up:
	docker compose -f "$(ROOT)/docker-compose.yml" up --build

down:
	docker compose -f "$(ROOT)/docker-compose.yml" down
