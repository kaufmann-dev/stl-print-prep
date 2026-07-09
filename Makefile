.PHONY: install-local test

install-local:
	uv venv --python 3.12 --allow-existing .venv
	uv pip install --python .venv/bin/python -e .
	ln -sf $(PWD)/.venv/bin/stl-print-prep $(HOME)/.local/bin/stl-print-prep

test:
	.venv/bin/python -m unittest discover -s tests
