.PHONY: all setup server server-webcam webcam test benchmark app pi-deploy simulate-pi latency-report sounds clean

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
	@echo "==> Starting NoNap FastAPI server on http://0.0.0.0:8000 (VIDEO_SOURCE=$${VIDEO_SOURCE:-pi})..."
	@PYTHONPATH=".:model" server/.venv/bin/python -m uvicorn server.app.main:app --host 0.0.0.0 --port 8000

server-webcam:
	@VIDEO_SOURCE=webcam $(MAKE) server

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
		echo "Usage: make pi-deploy PI_HOST=pi@192.168.2.2"; \
		exit 1; \
	fi
	@echo "==> Copying the camera streamer to $(PI_HOST):/boot/nonap ..."
	@scp pi_client/camera_stream.py pi_client/config.ini pi_client/nonap-camera.service $(PI_HOST):/tmp/
	@ssh -t $(PI_HOST) 'sudo mkdir -p /boot/nonap && sudo mv /tmp/camera_stream.py /tmp/config.ini /boot/nonap/ && sudo mv /tmp/nonap-camera.service /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl enable nonap-camera && sudo systemctl restart nonap-camera'
	@echo "Streaming. Log:  ssh $(PI_HOST) cat /boot/nonap/stream.log"

sounds:
	@python3 tools/make_sounds.py

simulate-pi:
	@model/.venv/bin/python tools/simulate_pi.py $(ARGS)

latency-report:
	@python3 tools/latency_report.py $(ARGS)
