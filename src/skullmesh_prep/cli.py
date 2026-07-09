from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from dataclasses import asdict, dataclass, replace
from pathlib import Path

import numpy as np
import SimpleITK as sitk

from dicom_surface import segment, surface


@dataclass(frozen=True)
class Preset:
    close_mm: float = 0.0
    dilate_mm: float = 0.0
    target_faces: int = 600_000
    smooth_iters: int = 20
    post_smooth_iters: int = 25
    passband: float = 0.1
    min_island_mm3: float = 100.0
    manual_roi: tuple[float, float, float, float, float, float] | None = None
    manual_close_mm: float = 0.0


PRESETS: dict[str, Preset] = {
    "clean": Preset(),
    "resin-0p8": Preset(close_mm=0.8, dilate_mm=0.4),
    "resin-1p6": Preset(close_mm=1.6, dilate_mm=0.4),
    "manual-orbit-maxilla": Preset(
        close_mm=1.6,
        dilate_mm=0.4,
        manual_roi=(-78.0, 78.0, -252.0, -128.0, -650.0, -515.0),
        manual_close_mm=4.8,
    ),
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
    return [max(1, int(np.ceil(mm / spacing))) for spacing in image.GetSpacing()]


def parse_roi(text: str) -> tuple[float, float, float, float, float, float]:
    try:
        values = tuple(float(part) for part in text.split(","))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("ROI must contain six comma-separated numbers") from exc
    if len(values) != 6:
        raise argparse.ArgumentTypeError("ROI must be x_min,x_max,y_min,y_max,z_min,z_max")
    x0, x1, y0, y1, z0, z1 = values
    if not (x0 < x1 and y0 < y1 and z0 < z1):
        raise argparse.ArgumentTypeError("each ROI min must be smaller than its max")
    return values


def roi_mask(image: sitk.Image, roi: tuple[float, float, float, float, float, float]) -> sitk.Image:
    direction = np.asarray(image.GetDirection(), dtype=np.float64).reshape(3, 3)
    if not np.allclose(direction, np.eye(3), atol=1e-8):
        raise ValueError("manual ROI currently requires an axis-aligned field")

    size = np.asarray(image.GetSize(), dtype=int)
    spacing = np.asarray(image.GetSpacing(), dtype=np.float64)
    origin = np.asarray(image.GetOrigin(), dtype=np.float64)
    bounds = ((roi[0], roi[1]), (roi[2], roi[3]), (roi[4], roi[5]))
    spans: list[tuple[int, int]] = []
    for axis, (lo_mm, hi_mm) in enumerate(bounds):
        lo = int(np.floor((lo_mm - origin[axis]) / spacing[axis]))
        hi = int(np.ceil((hi_mm - origin[axis]) / spacing[axis]))
        spans.append((max(0, min(int(size[axis]), lo)), max(0, min(int(size[axis]), hi))))

    arr = np.zeros((size[2], size[1], size[0]), dtype=np.uint8)
    x, y, z = spans
    arr[z[0]:z[1], y[0]:y[1], x[0]:x[1]] = 1
    out = sitk.GetImageFromArray(arr)
    out.CopyInformation(image)
    return out


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

    if preset.manual_roi and preset.manual_close_mm > 0:
        r = radius_voxels(preset.manual_close_mm, mask)
        log(f"manual close {preset.manual_close_mm:.2f} mm -> {r} voxels", verbose)
        strong = sitk.BinaryMorphologicalClosing(
            mask,
            kernelRadius=r,
            kernelType=sitk.sitkBall,
            foregroundValue=1,
            safeBorder=True,
        )
        mask = sitk.Or(mask, sitk.And(strong, roi_mask(mask, preset.manual_roi)))

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
        "manual_roi",
        "manual_close_mm",
    ):
        value = getattr(args, attr)
        if value is not None:
            overrides[attr] = value
    preset = replace(preset, **overrides)

    try:
        field = sitk.ReadImage(str(args.field))
        mask = sitk.BinaryThreshold(field, 0.5, 1e9, 1, 0)
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
    build.add_argument("--preset", choices=sorted(PRESETS), default="resin-1p6")
    build.add_argument("--close-mm", type=float)
    build.add_argument("--dilate-mm", type=float)
    build.add_argument("--target-faces", type=int)
    build.add_argument("--smooth-iters", type=int)
    build.add_argument("--post-smooth-iters", type=int)
    build.add_argument("--passband", type=float)
    build.add_argument("--min-island-mm3", type=float)
    build.add_argument("--manual-roi", type=parse_roi)
    build.add_argument("--manual-close-mm", type=float)
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
