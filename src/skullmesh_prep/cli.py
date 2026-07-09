from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
from dataclasses import asdict, dataclass, replace
from pathlib import Path

import SimpleITK as sitk

from dicom_surface import segment, surface


@dataclass(frozen=True)
class Preset:
    close_mm: float = 1.6
    dilate_mm: float = 0.4
    target_faces: int = 600_000
    smooth_iters: int = 20
    post_smooth_iters: int = 25
    passband: float = 0.1
    min_island_mm3: float = 100.0


PRESETS: dict[str, Preset] = {
    "resin": Preset(),
    "fdm": Preset(close_mm=2.4, dilate_mm=1.2),
}


def emit_json(payload: dict, ok: bool = True) -> int:
    payload = {"ok": ok, **payload}
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if ok else 1


def log(message: str, enabled: bool) -> None:
    if enabled:
        print(message, file=sys.stderr, flush=True)


def radius_voxels(mm: float, image: sitk.Image) -> list[int]:
    if mm <= 0:
        return [0] * image.GetDimension()
    return [max(1, int(math.ceil(mm / spacing))) for spacing in image.GetSpacing()]


def apply_cleanup(mask: sitk.Image, preset: Preset, verbose: bool) -> sitk.Image:
    if preset.close_mm > 0:
        r = radius_voxels(preset.close_mm, mask)
        log(f"closing {preset.close_mm:.2f} mm -> {r} voxels", verbose)
        mask = sitk.BinaryMorphologicalClosing(
            mask,
            kernelRadius=r,
            kernelType=sitk.sitkBall,
            foregroundValue=1,
            safeBorder=True,
        )

    if preset.dilate_mm > 0:
        r = radius_voxels(preset.dilate_mm, mask)
        log(f"dilate {preset.dilate_mm:.2f} mm -> {r} voxels", verbose)
        mask = sitk.BinaryDilate(
            mask,
            kernelRadius=r,
            kernelType=sitk.sitkBall,
            foregroundValue=1,
            backgroundValue=0,
        )

    return mask


def mesh(mask: sitk.Image, preset: Preset, output: Path, verbose: bool) -> dict:
    affine = surface.index_to_physical(mask)
    poly = surface.marching_cubes(surface.to_vtk_image(mask), 0.5)
    raw = int(poly.GetNumberOfPolys())
    log(f"raw triangles {raw:,}", verbose)
    poly = surface.smooth(poly, preset.smooth_iters, preset.passband)
    poly, shells = surface.largest_component(poly)
    kept = int(poly.GetNumberOfPolys())
    log(f"shells {shells} (kept 1) -> {kept:,} tris", verbose)
    poly = surface.decimate(poly, preset.target_faces)
    poly = surface.smooth(poly, preset.post_smooth_iters, preset.passband)
    poly = surface.transform(poly, affine)
    poly = surface.compute_normals(poly)
    boundary, nonmanifold = surface.count_defects(poly)
    surface.write(poly, str(output))
    bounds = poly.GetBounds()
    return {
        "output": str(output),
        "triangles": int(poly.GetNumberOfPolys()),
        "raw_triangles": raw,
        "shells": int(shells),
        "boundary_edges": int(boundary),
        "non_manifold_edges": int(nonmanifold),
        "extents_mm": [bounds[1] - bounds[0], bounds[3] - bounds[2], bounds[5] - bounds[4]],
    }


def command_doctor(args: argparse.Namespace) -> int:
    modules = {
        "numpy": importlib.util.find_spec("numpy") is not None,
        "SimpleITK": importlib.util.find_spec("SimpleITK") is not None,
        "dicom_surface": importlib.util.find_spec("dicom_surface") is not None,
        "vtk": importlib.util.find_spec("vtk") is not None,
        "pymeshlab": importlib.util.find_spec("pymeshlab") is not None,
    }
    ok = all(modules.values())
    if args.json:
        return emit_json({"command": "doctor", "modules": modules}, ok=ok)
    for name, present in modules.items():
        print(f"{name:14} {'ok' if present else 'missing'}")
    return 0 if ok else 1


def command_presets(args: argparse.Namespace) -> int:
    data = {name: asdict(preset) for name, preset in PRESETS.items()}
    if args.json:
        return emit_json({"command": "presets", "presets": data})
    for name, preset in data.items():
        print(name)
        for key, value in preset.items():
            print(f"  {key}: {value}")
    return 0


def command_build(args: argparse.Namespace) -> int:
    preset = PRESETS[args.preset]
    overrides = {}
    for attr in (
        "close_mm",
        "dilate_mm",
        "target_faces",
        "smooth_iters",
        "post_smooth_iters",
        "passband",
        "min_island_mm3",
    ):
        value = getattr(args, attr)
        if value is not None:
            overrides[attr] = value
    preset = replace(preset, **overrides)

    try:
        field = sitk.ReadImage(str(args.field))
        mask = sitk.BinaryThreshold(
            field,
            lowerThreshold=0.5,
            upperThreshold=1e9,
            insideValue=1,
            outsideValue=0,
        )
        mask = sitk.Cast(mask, sitk.sitkUInt8)
        mask = apply_cleanup(mask, preset, verbose=not args.json)
        mask = segment.islands(
            mask,
            True,
            preset.min_island_mm3,
            log=(lambda msg: log(msg, not args.json)),
        )
        mask = segment.pad(mask, 1)
        if args.mask_out:
            sitk.WriteImage(mask, str(args.mask_out), True)
        result = mesh(mask, preset, args.output, verbose=not args.json)
    except Exception as exc:
        if args.json:
            return emit_json({"error": str(exc)}, ok=False)
        raise

    if args.json:
        return emit_json({"command": "build", "preset": args.preset, "settings": asdict(preset), **result})
    print(f"wrote {result['output']}  tris={result['triangles']:,}")
    print(f"defects boundary={result['boundary_edges']} non_manifold={result['non_manifold_edges']}")
    print("extents %.1f x %.1f x %.1f mm" % tuple(result["extents_mm"]))
    return 0


def build_parser() -> argparse.ArgumentParser:
    json_parent = argparse.ArgumentParser(add_help=False)
    json_parent.add_argument("--json", action="store_true", default=argparse.SUPPRESS)

    parser = argparse.ArgumentParser(prog="skullmesh-prep", parents=[json_parent])
    sub = parser.add_subparsers(dest="command", required=True)

    doctor = sub.add_parser("doctor", help="verify local dependencies", parents=[json_parent])
    doctor.set_defaults(func=command_doctor)

    presets = sub.add_parser("presets", help="list available presets", parents=[json_parent])
    presets.set_defaults(func=command_presets)

    build = sub.add_parser("build", help="build an STL from a merged fractional field", parents=[json_parent])
    build.add_argument("--field", type=Path, required=True, help="input fractional occupancy NRRD")
    build.add_argument("--output", type=Path, required=True, help="output STL path")
    build.add_argument("--mask-out", type=Path, help="optional cleaned mask output NRRD")
    build.add_argument("--preset", choices=sorted(PRESETS), default="resin")
    build.add_argument("--close-mm", type=float)
    build.add_argument("--dilate-mm", type=float)
    build.add_argument("--target-faces", type=int)
    build.add_argument("--smooth-iters", type=int)
    build.add_argument("--post-smooth-iters", type=int)
    build.add_argument("--passband", type=float)
    build.add_argument("--min-island-mm3", type=float)
    build.set_defaults(func=command_build)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "json"):
        args.json = False
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
