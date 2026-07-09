# skullmesh-prep

Reusable CLI for preparing skull STL files from an already merged DICOM-derived
fractional occupancy field.

The tool wraps the local `dicom-surface` meshing pipeline and replaces the
one-off scripts used during skull merge cleanup.

## Install

Install into the same Python environment that has `dicom-surface`, VTK,
PyMeshLab, and SimpleITK available:

```sh
uv pip install --python /home/david/Projects/dicom-surface/.venv/bin/python -e .
ln -sf /home/david/Projects/dicom-surface/.venv/bin/skullmesh-prep ~/.local/bin/skullmesh-prep
```

Then verify it works from anywhere:

```sh
skullmesh-prep doctor
skullmesh-prep presets
```

## Commands

```sh
skullmesh-prep doctor
skullmesh-prep --json doctor
skullmesh-prep presets
skullmesh-prep --json presets
skullmesh-prep build --field field_union_0p4.nrrd --output skull.stl
```

`build` reads a fractional occupancy NRRD field, thresholds it at `0.5`, applies
the selected cleanup, keeps the largest component, meshes it, and writes an STL.

## Presets

| preset  | close mm | dilate mm | target faces | purpose                 |
| ------- | -------: | --------: | -----------: | ----------------------- |
| `fdm`   |    `2.4` |     `1.2` |     `600000` | FDM print preparation   |
| `resin` |    `1.6` |     `0.4` |     `600000` | resin print preparation |

Every preset value can be overridden:

```sh
skullmesh-prep build \
  --field /home/david/Downloads/skullmerge/field_union_0p4.nrrd \
  --output /home/david/Downloads/custom.stl \
  --preset fdm \
  --close-mm 1.2 \
  --target-faces 600000
```

## JSON

Use `--json` for machine-readable output. Successful commands return:

```json
{"ok": true, "command": "doctor"}
```

Errors return:

```json
{"ok": false, "error": "message"}
```

## License

MIT
