PY ?= python3

# Deployment target. The image rebuilds the site from cases/ + evidence/, so a
# bad citation fails the build rather than reaching the deployed page.
PROJECT ?= machine-learning-study-481717
REGION  ?= us-central1
SERVICE ?= prova
REV     := $(shell git rev-parse --short HEAD 2>/dev/null || echo dev)
IMAGE   := $(REGION)-docker.pkg.dev/$(PROJECT)/prova/site:$(REV)

.PHONY: help check refresh evidence verify build test clean deploy

help:
	@echo "make check     - tests + verify committed evidence + build the site"
	@echo "make refresh   - re-collect evidence from GitHub, then verify and build"
	@echo "make evidence  - collect repository evidence into evidence/"
	@echo "make verify    - validate every claim against the recorded evidence"
	@echo "make build     - render build/*.md, build/index.html, catalog/projects.json"
	@echo "make test      - run the validator's own test suite"
	@echo "make deploy    - check, build the image and deploy to Cloud Run"

check: test verify build

refresh: evidence verify build

evidence:
	$(PY) tool/collect.py

verify:
	$(PY) tool/validate.py

build:
	$(PY) tool/render.py

test:
	$(PY) -m unittest discover -s tests -v

deploy: check
	docker build -f deploy/Dockerfile -t $(IMAGE) .
	PATH="$$HOME/.local/share/google-cloud-sdk/bin:$$PATH" docker push $(IMAGE)
	gcloud run deploy $(SERVICE) --image $(IMAGE) --region $(REGION) \
		--allow-unauthenticated --port 8080 --min-instances 0 \
		--max-instances 2 --memory 128Mi --cpu 1 --quiet

clean:
	rm -rf build
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
