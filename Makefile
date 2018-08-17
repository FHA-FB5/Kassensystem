INFO=

all:
	@echo "cmd:"
	@echo "  install    creates a virtual pyenv and"
	@echo "             installs all necessary dependencies."
	@echo "  run        starts the app in a pyenv"

install:
	( \
	python3 -m venv .; \
	source ${PWD}/bin/activate; \
	pip install -r req.txt; \
	)

run:
	( \
	. ${PWD}/bin/activate; \
	python3 run.py; \
	)
