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
skullmesh-prep build --field field_union_0p4.nrrd --output skull.stl --preset resin-1p6
```

`build` reads a fractional occupancy NRRD field, thresholds it at `0.5`, applies
the selected cleanup, keeps the largest component, meshes it, and writes an STL.

## Presets

| preset                 | close mm | dilate mm | target faces | purpose                                          |
| ---------------------- | -------: | --------: | -----------: | ------------------------------------------------ |
| `clean`                |    `0.0` |     `0.0` |     `600000` | regular merged skull, not print-modified         |
| `resin-0p8`            |    `0.8` |     `0.4` |     `600000` | resin print with light pore closing              |
| `resin-1p6`            |    `1.6` |     `0.4` |     `600000` | current preferred resin print baseline           |
| `manual-orbit-maxilla` |    `1.6` |     `0.4` |     `600000` | resin baseline plus targeted orbit/maxilla patch |

Every preset value can be overridden:

```sh
skullmesh-prep build \
  --field /home/david/Downloads/skullmerge/field_union_0p4.nrrd \
  --output /home/david/Downloads/custom.stl \
  --preset resin-1p6 \
  --close-mm 1.2 \
  --target-faces 600000
```

Manual local closing accepts an LPS physical-coordinate ROI:

```sh
skullmesh-prep build \
  --field /home/david/Downloads/skullmerge/field_union_0p4.nrrd \
  --output /home/david/Downloads/manual.stl \
  --preset resin-1p6 \
  --manual-roi=-78,78,-252,-128,-650,-515 \
  --manual-close-mm 4.8
```

The ROI order is `x_min,x_max,y_min,y_max,z_min,z_max` in millimetres.

## JSON

Use `--json` for machine-readable output. Successful commands return:

```json
{"ok": true, "command": "doctor"}
```

Errors return:

```json
{"ok": false, "error": "message"}
```

## Manual Hole Closing On Linux

For manual editing, the easiest path is Blender:

1. Import the STL.
2. Add simple patch shapes over unwanted holes, usually flattened UV spheres or
   ellipsoids.
3. Use `Boolean > Union` to merge each patch into the skull.
4. Run `Voxel Remesh` at a small voxel size, then smooth locally.
5. Export STL and validate with `skullmesh-prep doctor` plus
   `dicom-surface validate`.

Do not use Blender's normal "Fill Holes" for these skull openings. The STL is
already watertight; these are anatomical openings/tunnels, so they need added
material or a local remesh/boolean patch.

## License

MIT
