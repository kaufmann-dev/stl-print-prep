---
name: skullmesh-prep
description: Use when Codex needs to generate, adjust, or validate skull STL files from the merged skull field, including resin-printable variants, pore-closing changes, target-face changes, and smoothing changes. Always use the installed skullmesh-prep CLI instead of creating one-off scripts for these skull mesh preparation tasks.
---

# Skullmesh Prep

Use the installed `skullmesh-prep` command for skull mesh variants. Do not
create new throwaway Python scripts unless the CLI is missing or the user asks
to change the tool itself.

## First Checks

Verify the command and dependencies:

```sh
command -v skullmesh-prep
skullmesh-prep --json doctor
skullmesh-prep --json presets
```

Use the current merged field by default:

```text
/home/david/Downloads/skullmerge/field_union_0p4.nrrd
```

## Build

Default resin-prepared STL:

```sh
skullmesh-prep build \
  --field /home/david/Downloads/skullmerge/field_union_0p4.nrrd \
  --output /home/david/Downloads/Skull_full_merged_2_resin_print.stl
```

Adjust values with flags rather than making new presets:

```sh
skullmesh-prep build \
  --field /home/david/Downloads/skullmerge/field_union_0p4.nrrd \
  --output /home/david/Downloads/custom.stl \
  --close-mm 0.8 \
  --dilate-mm 0.4 \
  --target-faces 600000 \
  --smooth-iters 20 \
  --post-smooth-iters 25 \
  --passband 0.1
```

## Validate

After building, run:

```sh
/home/david/Projects/dicom-surface/.venv/bin/python -m dicom_surface validate /path/to/output.stl
```

Render with the existing VTK helper if visual confirmation is needed:

```sh
/home/david/Projects/dicom-surface/.venv/bin/python \
  /home/david/Downloads/repair_results/render.py \
  /path/to/output.stl \
  /path/to/output.png
```
