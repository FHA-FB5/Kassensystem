INFO=

all:
	@echo "cmd:"
	@echo "  install    creates a virtual pyenv and"
	@echo "             installs all necessary dependencies."
	@echo "  run        starts the app in a pyenv"
	@echo "  mrproper   remove pyenv"

install:
	( \
	virtualenv venv; \
	source ${PWD}/venv/bin/activate; \
	pip install -r req.txt; \
	)

run:
	( \
	source ${PWD}/venv/bin/activate; \
	python3 run.py; \
	)

mrproper:
	rm -rf ./venv/
