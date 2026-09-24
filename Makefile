.PHONY: all setup server webcam test benchmark app pi-deploy clean

PYTHON311 ?= $(shell which python3.11 2>/dev/null || which python3)
FLUTTER ?= flutter

all: setup

setup:
	@echo "==> Setting up Python 3.11 virtual environments..."
	@mkdir -p server/data model/checkpoints model/weights brand
	@if [ ! -d "model/.venv" ]; then \
		$(PYTHON311) -m venv model/.venv; \
		model/.venv/bin/pip install --upgrade pip setuptools wheel; \
		model/.venv/bin/pip install -r model/requirements.txt; \
	fi
	@if [ ! -d "server/.venv" ]; then \
		$(PYTHON311) -m venv server/.venv; \
		server/.venv/bin/pip install --upgrade pip setuptools wheel; \
		server/.venv/bin/pip install -r server/requirements.txt; \
	fi
	@if [ ! -f "brand/nonap_icon_1024.png" ]; then \
		echo "==> Rasterizing brand/nonap_icon.svg -> brand/nonap_icon_1024.png"; \
		qlmanage -t -s 1024 -o brand brand/nonap_icon.svg >/dev/null 2>&1; \
		if [ -f "brand/nonap_icon.svg.png" ]; then mv brand/nonap_icon.svg.png brand/nonap_icon_1024.png; fi; \
	fi
	@if [ -d "app" ]; then \
		echo "==> Fetching Flutter dependencies..."; \
		cd app && $(FLUTTER) pub get; \
	fi
	@echo "==> Setup completed successfully!"

server:
	@echo "==> Starting NoNap FastAPI server on http://0.0.0.0:8000..."
	@PYTHONPATH=".:model" server/.venv/bin/python -m uvicorn server.app.main:app --host 0.0.0.0 --port 8000 --reload

webcam:
	@echo "==> Running standalone webcam demo with live overlay..."
	@PYTHONPATH=".:model" model/.venv/bin/python -m nonap_model.demo

test:
	@echo "==> Running model tests..."
	@PYTHONPATH=".:model" model/.venv/bin/pytest model/tests -v || true
	@echo "==> Running server tests..."
	@PYTHONPATH=".:model:server" server/.venv/bin/pytest server/tests -v

benchmark:
	@echo "==> Running latency benchmark on Mac M4..."
	@PYTHONPATH=".:model" model/.venv/bin/python scripts/benchmark.py

app:
	@echo "==> Launching Flutter app..."
	@cd app && $(FLUTTER) run

pi-deploy:
	@if [ -z "$(PI_HOST)" ]; then \
		echo "Usage: make pi-deploy PI_HOST=pi@nonap.local"; \
		exit 1; \
	fi
	@echo "==> Deploying pi-client to $(PI_HOST):~/nonap..."
	@rsync -avz --exclude '__pycache__' --exclude '*.pyc' pi-client/ $(PI_HOST):~/nonap/
	@ssh $(PI_HOST) "chmod +x ~/nonap/*.sh ~/nonap/*.py && cd ~/nonap && ./install.sh"

clean:
	rm -rf model/.venv server/.venv app/build
	find . -type d -name "__pycache__" -exec rm -rf {} +
