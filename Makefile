INFO=

all:
	@echo "cmd:"
	@echo "  venv     setup python virtual-env"
	@echo "  ureq     update requirements"
	@echo "  bash     join env with bash"
	@echo "  fish     join env with fish"
	@echo "  vrun     run app"

venv:
	$(shell python3 -m venv .)

bash:
	$(shell . ${PWD}/bin/active)

fish:
	$(shell . ${PWD}/bin/active.fish)

