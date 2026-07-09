.PHONY: install-local test

install-local:
	uv venv --python 3.12 .venv
	uv pip install --python .venv/bin/python -e .
	ln -sf $(PWD)/.venv/bin/skullmesh-prep $(HOME)/.local/bin/skullmesh-prep

test:
	.venv/bin/python -m unittest discover -s tests
