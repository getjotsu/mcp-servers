all: flake8 build
.PHONY: all

flake8:
	flake8 src/server.py
.PHONY: flake8

build:
	../scripts/build.sh
.PHONY: build

clean:
	rm -rf src/vendor
.PHONY: clean

clean-all: clean
	rm -rf .venv-pyodide
.PHONY: clean-all
