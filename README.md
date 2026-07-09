# stl-print-prep

Reusable CLI for making an existing STL mesh more print-ready.

The input is always an STL. The tool voxelizes that mesh internally, closes
pores in millimetres, optionally reinforces thin geometry, remeshes, smooths,
decimates, and writes a new STL. Multi-part meshes are preserved; only connected
islands smaller than `--min-island-mm3` are removed.

## Install

```sh
make install-local
```

Then verify it works from anywhere:

```sh
stl-print-prep doctor
stl-print-prep presets
```

## Commands

```sh
stl-print-prep doctor
stl-print-prep --json doctor
stl-print-prep presets
stl-print-prep --json presets
stl-print-prep build --input model.stl --output model-print.stl
```

## Presets

| preset  | voxel mm | close mm | dilate mm | target faces | purpose                 |
| ------- | -------: | -------: | --------: | -----------: | ----------------------- |
| `fdm`   |    `0.4` |    `2.4` |     `1.2` |     `600000` | FDM print preparation   |
| `resin` |    `0.4` |    `1.6` |     `0.4` |     `600000` | resin print preparation |

`resin` is the default. Every preset value can be overridden:

```sh
stl-print-prep build \
  --input /path/to/model.stl \
  --output /path/to/model-print.stl \
  --preset fdm \
  --close-mm 1.2 \
  --dilate-mm 0.8 \
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
