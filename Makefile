PYTHON ?= python3
SOURCES = phototidy tests photo_tidy.py setup.py

.PHONY: all test lint clean install

all: lint test

test:
	$(PYTHON) -m pytest

lint:
	$(PYTHON) -m pycodestyle --max-line-length=100 $(SOURCES)

install:
	$(PYTHON) -m pip install .

clean:
	rm -rf build dist *.egg-info .pytest_cache
	find . -name '__pycache__' -prune -exec rm -rf {} +
	find . -name '*.pyc' -delete
