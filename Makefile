.PHONY: install-local test

install-local:
	uv pip install --python /home/david/Projects/dicom-surface/.venv/bin/python -e .
	ln -sf /home/david/Projects/dicom-surface/.venv/bin/skullmesh-prep $(HOME)/.local/bin/skullmesh-prep

test:
	python3 -m unittest discover -s tests
