---
name: skullmesh-prep
description: Use when Codex needs to make an existing skull STL print-ready, including resin/FDM variants, pore-closing changes, reinforcement changes, target-face changes, and smoothing changes. Always use the installed skullmesh-prep CLI instead of creating one-off scripts for STL print preparation.
---

# Skullmesh Prep

Use the installed `skullmesh-prep` command for skull STL print-prep variants.
Do not create new throwaway Python scripts unless the CLI is missing or the user
asks to change the tool itself.

## First Checks

Verify the command and dependencies:

```sh
command -v skullmesh-prep
skullmesh-prep --json doctor
skullmesh-prep --json presets
```

## Build

Default resin-prepared STL:

```sh
skullmesh-prep build \
  --input /home/david/Downloads/Skull_full_merged_2.stl \
  --output /home/david/Downloads/Skull_full_merged_2_resin_print.stl
```

FDM-prepared STL:

```sh
skullmesh-prep build \
  --input /home/david/Downloads/Skull_full_merged_2.stl \
  --output /home/david/Downloads/Skull_full_merged_2_fdm_print.stl \
  --preset fdm
```

Adjust values with flags rather than making new presets:

```sh
skullmesh-prep build \
  --input /home/david/Downloads/Skull_full_merged_2.stl \
  --output /home/david/Downloads/custom-print.stl \
  --close-mm 0.8 \
  --dilate-mm 0.4 \
  --target-faces 600000 \
  --smooth-iters 20 \
  --post-smooth-iters 25 \
  --passband 0.1
```
