PY ?= python3

.PHONY: help check refresh evidence verify build test clean

help:
	@echo "make check     - tests + verify committed evidence + build the site"
	@echo "make refresh   - re-collect evidence from GitHub, then verify and build"
	@echo "make evidence  - collect repository evidence into evidence/"
	@echo "make verify    - validate every claim against the recorded evidence"
	@echo "make build     - render build/*.md, build/index.html, build/projects.json"
	@echo "make test      - run the validator's own test suite"

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

clean:
	rm -rf build
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
