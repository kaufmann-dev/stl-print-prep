---
name: stl-print-prep
description: Use when Codex needs to make an existing STL mesh print-ready, including resin/FDM variants, pore-closing changes, reinforcement changes, target-face changes, and smoothing changes. Always use the installed stl-print-prep CLI instead of creating one-off scripts for STL print preparation.
---

# STL Print Prep

Use the installed `stl-print-prep` command for STL print-prep variants.
Do not create new throwaway Python scripts unless the CLI is missing or the user
asks to change the tool itself.

## First Checks

Verify the command and dependencies:

```sh
command -v stl-print-prep
stl-print-prep --json doctor
stl-print-prep --json presets
```

## Build

Default resin-prepared STL:

```sh
stl-print-prep build \
  --input /path/to/model.stl \
  --output /path/to/model-resin-print.stl
```

FDM-prepared STL:

```sh
stl-print-prep build \
  --input /path/to/model.stl \
  --output /path/to/model-fdm-print.stl \
  --preset fdm
```

Adjust values with flags rather than making new presets:

```sh
stl-print-prep build \
  --input /path/to/model.stl \
  --output /path/to/custom-print.stl \
  --close-mm 0.8 \
  --dilate-mm 0.4 \
  --target-faces 600000 \
  --smooth-iters 20 \
  --post-smooth-iters 25 \
  --passband 0.1
```
