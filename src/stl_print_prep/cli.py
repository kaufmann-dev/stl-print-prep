from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
from dataclasses import asdict, dataclass, replace
from pathlib import Path

import numpy as np
import pymeshlab
from scipy import ndimage
import vtk
from vtk.util import numpy_support


@dataclass(frozen=True)
class Preset:
    voxel_mm: float = 0.4
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


def read_stl(path: Path) -> vtk.vtkPolyData:
    reader = vtk.vtkSTLReader()
    reader.SetFileName(str(path))
    reader.Update()

    tri = vtk.vtkTriangleFilter()
    tri.SetInputConnection(reader.GetOutputPort())
    tri.Update()

    clean = vtk.vtkCleanPolyData()
    clean.SetInputConnection(tri.GetOutputPort())
    clean.Update()
    poly = clean.GetOutput()
    if poly.GetNumberOfPoints() == 0 or poly.GetNumberOfPolys() == 0:
        raise ValueError(f"{path} did not contain a readable triangle mesh")
    return poly


def voxelize(poly: vtk.vtkPolyData, voxel_mm: float, margin_mm: float) -> tuple[np.ndarray, tuple[float, float, float], float]:
    if voxel_mm <= 0:
        raise ValueError("--voxel-mm must be positive")

    bounds = poly.GetBounds()
    origin = (
        bounds[0] - margin_mm,
        bounds[2] - margin_mm,
        bounds[4] - margin_mm,
    )
    dims = (
        int(math.ceil((bounds[1] - bounds[0] + 2 * margin_mm) / voxel_mm)) + 1,
        int(math.ceil((bounds[3] - bounds[2] + 2 * margin_mm) / voxel_mm)) + 1,
        int(math.ceil((bounds[5] - bounds[4] + 2 * margin_mm) / voxel_mm)) + 1,
    )

    image = vtk.vtkImageData()
    image.SetSpacing(voxel_mm, voxel_mm, voxel_mm)
    image.SetOrigin(*origin)
    image.SetDimensions(*dims)
    image.SetExtent(0, dims[0] - 1, 0, dims[1] - 1, 0, dims[2] - 1)
    image.AllocateScalars(vtk.VTK_UNSIGNED_CHAR, 1)
    scalars = numpy_support.vtk_to_numpy(image.GetPointData().GetScalars())
    scalars.fill(1)

    stencil = vtk.vtkPolyDataToImageStencil()
    stencil.SetInputData(poly)
    stencil.SetOutputOrigin(*origin)
    stencil.SetOutputSpacing(voxel_mm, voxel_mm, voxel_mm)
    stencil.SetOutputWholeExtent(image.GetExtent())
    stencil.Update()

    image_stencil = vtk.vtkImageStencil()
    image_stencil.SetInputData(image)
    image_stencil.SetStencilConnection(stencil.GetOutputPort())
    image_stencil.ReverseStencilOff()
    image_stencil.SetBackgroundValue(0)
    image_stencil.Update()

    arr = numpy_support.vtk_to_numpy(
        image_stencil.GetOutput().GetPointData().GetScalars()
    ).reshape((dims[2], dims[1], dims[0]))
    return arr.astype(bool), origin, voxel_mm


def ball(radius_voxels: int) -> np.ndarray | None:
    if radius_voxels <= 0:
        return None
    z, y, x = np.ogrid[
        -radius_voxels: radius_voxels + 1,
        -radius_voxels: radius_voxels + 1,
        -radius_voxels: radius_voxels + 1,
    ]
    return (x * x + y * y + z * z) <= radius_voxels * radius_voxels


def radius_voxels(mm: float, voxel_mm: float) -> int:
    if mm <= 0:
        return 0
    return max(1, int(math.ceil(mm / voxel_mm)))


def remove_small_islands(mask: np.ndarray, voxel_mm: float, min_island_mm3: float) -> np.ndarray:
    labels, count = ndimage.label(mask)
    if count == 0:
        raise ValueError("voxelization produced no solid foreground")
    if min_island_mm3 <= 0:
        return mask
    sizes = np.bincount(labels.ravel())
    sizes[0] = 0
    min_voxels = max(1, int(round(min_island_mm3 / (voxel_mm ** 3))))
    keep = sizes >= min_voxels
    keep[0] = False
    if not keep.any():
        raise ValueError("no connected component survived --min-island-mm3")
    return keep[labels]


def apply_cleanup(mask: np.ndarray, preset: Preset, verbose: bool) -> np.ndarray:
    close_r = radius_voxels(preset.close_mm, preset.voxel_mm)
    if close_r:
        log(f"closing {preset.close_mm:.2f} mm -> {close_r} voxels", verbose)
        mask = ndimage.binary_closing(mask, structure=ball(close_r))

    dilate_r = radius_voxels(preset.dilate_mm, preset.voxel_mm)
    if dilate_r:
        log(f"dilate {preset.dilate_mm:.2f} mm -> {dilate_r} voxels", verbose)
        mask = ndimage.binary_dilation(mask, structure=ball(dilate_r))

    mask = remove_small_islands(mask, preset.voxel_mm, preset.min_island_mm3)
    return np.pad(mask, 1, constant_values=False)


def to_vtk_image(mask: np.ndarray, origin: tuple[float, float, float], voxel_mm: float) -> vtk.vtkImageData:
    shifted_origin = (origin[0] - voxel_mm, origin[1] - voxel_mm, origin[2] - voxel_mm)
    img = vtk.vtkImageData()
    img.SetDimensions(mask.shape[2], mask.shape[1], mask.shape[0])
    img.SetSpacing(voxel_mm, voxel_mm, voxel_mm)
    img.SetOrigin(*shifted_origin)
    scalars = numpy_support.numpy_to_vtk(
        np.ascontiguousarray(mask.astype(np.uint8)).ravel(order="C"),
        deep=True,
        array_type=vtk.VTK_UNSIGNED_CHAR,
    )
    img.GetPointData().SetScalars(scalars)
    return img


def marching_cubes(mask: np.ndarray, origin: tuple[float, float, float], voxel_mm: float) -> vtk.vtkPolyData:
    fe = vtk.vtkFlyingEdges3D()
    fe.SetInputData(to_vtk_image(mask, origin, voxel_mm))
    fe.SetValue(0, 0.5)
    fe.ComputeNormalsOff()
    fe.ComputeGradientsOff()
    fe.Update()
    return fe.GetOutput()


def smooth(poly: vtk.vtkPolyData, iterations: int, passband: float) -> vtk.vtkPolyData:
    if iterations <= 0:
        return poly
    filt = vtk.vtkWindowedSincPolyDataFilter()
    filt.SetInputData(poly)
    filt.SetNumberOfIterations(int(iterations))
    filt.SetPassBand(float(passband))
    filt.BoundarySmoothingOn()
    filt.NonManifoldSmoothingOn()
    filt.NormalizeCoordinatesOn()
    filt.FeatureEdgeSmoothingOff()
    filt.Update()
    return filt.GetOutput()


def count_components(poly: vtk.vtkPolyData) -> int:
    conn = vtk.vtkPolyDataConnectivityFilter()
    conn.SetInputData(poly)
    conn.SetExtractionModeToAllRegions()
    conn.Update()
    return int(conn.GetNumberOfExtractedRegions())


def vtk_arrays(poly: vtk.vtkPolyData) -> tuple[np.ndarray, np.ndarray]:
    tri = vtk.vtkTriangleFilter()
    tri.SetInputData(poly)
    tri.Update()
    poly = tri.GetOutput()
    verts = numpy_support.vtk_to_numpy(poly.GetPoints().GetData()).astype(np.float64)
    faces = numpy_support.vtk_to_numpy(poly.GetPolys().GetConnectivityArray()).reshape(-1, 3)
    return verts, faces.astype(np.int32)


def poly_from_arrays(verts: np.ndarray, faces: np.ndarray) -> vtk.vtkPolyData:
    points = vtk.vtkPoints()
    points.SetData(numpy_support.numpy_to_vtk(np.ascontiguousarray(verts, dtype=np.float64), deep=True))

    offsets = np.arange(0, 3 * (len(faces) + 1), 3, dtype=np.int64)
    cells = vtk.vtkCellArray()
    cells.SetData(
        numpy_support.numpy_to_vtkIdTypeArray(offsets, deep=True),
        numpy_support.numpy_to_vtkIdTypeArray(np.ascontiguousarray(faces, dtype=np.int64).ravel(), deep=True),
    )

    poly = vtk.vtkPolyData()
    poly.SetPoints(points)
    poly.SetPolys(cells)
    return poly


def decimate(poly: vtk.vtkPolyData, target_faces: int) -> vtk.vtkPolyData:
    current = int(poly.GetNumberOfPolys())
    if target_faces <= 0 or current <= target_faces:
        return poly
    verts, faces = vtk_arrays(poly)
    meshes = pymeshlab.MeshSet()
    meshes.add_mesh(pymeshlab.Mesh(vertex_matrix=verts, face_matrix=faces))
    meshes.apply_filter(
        "meshing_decimation_quadric_edge_collapse",
        targetfacenum=int(target_faces),
        preserveboundary=True,
        preservenormal=True,
        preservetopology=True,
        planarquadric=True,
        qualitythr=0.3,
    )
    mesh = meshes.current_mesh()
    return poly_from_arrays(mesh.vertex_matrix(), mesh.face_matrix())


def compute_normals(poly: vtk.vtkPolyData) -> vtk.vtkPolyData:
    normals = vtk.vtkPolyDataNormals()
    normals.SetInputData(poly)
    normals.ConsistencyOn()
    normals.SplittingOff()
    normals.AutoOrientNormalsOn()
    normals.Update()
    return normals.GetOutput()


def count_defects(poly: vtk.vtkPolyData) -> tuple[int, int]:
    counts = []
    for boundary, nonmanifold in ((True, False), (False, True)):
        edges = vtk.vtkFeatureEdges()
        edges.SetInputData(poly)
        edges.SetBoundaryEdges(boundary)
        edges.SetNonManifoldEdges(nonmanifold)
        edges.FeatureEdgesOff()
        edges.ManifoldEdgesOff()
        edges.Update()
        counts.append(int(edges.GetOutput().GetNumberOfCells()))
    return counts[0], counts[1]


def write_stl(poly: vtk.vtkPolyData, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    writer = vtk.vtkSTLWriter()
    writer.SetFileName(str(output))
    writer.SetInputData(poly)
    writer.SetFileTypeToBinary()
    if not writer.Write():
        raise OSError(f"failed to write {output}")


def build_mesh(input_path: Path, output: Path, preset: Preset, verbose: bool) -> dict:
    source = read_stl(input_path)
    margin = max(preset.close_mm, preset.dilate_mm, preset.voxel_mm) + 2 * preset.voxel_mm
    log("voxelizing STL", verbose)
    mask, origin, voxel_mm = voxelize(source, preset.voxel_mm, margin)
    log(f"voxel grid {mask.shape[2]}x{mask.shape[1]}x{mask.shape[0]} @ {voxel_mm:.3f} mm", verbose)
    mask = apply_cleanup(mask, preset, verbose)

    poly = marching_cubes(mask, origin, voxel_mm)
    raw = int(poly.GetNumberOfPolys())
    log(f"raw triangles {raw:,}", verbose)
    poly = smooth(poly, preset.smooth_iters, preset.passband)
    shells = count_components(poly)
    log(f"shells {shells} -> {poly.GetNumberOfPolys():,} tris", verbose)
    poly = decimate(poly, preset.target_faces)
    poly = smooth(poly, preset.post_smooth_iters, preset.passband)
    poly = compute_normals(poly)
    boundary, nonmanifold = count_defects(poly)
    write_stl(poly, output)
    bounds = poly.GetBounds()
    return {
        "input": str(input_path),
        "output": str(output),
        "triangles": int(poly.GetNumberOfPolys()),
        "raw_triangles": raw,
        "shells": int(shells),
        "boundary_edges": int(boundary),
        "non_manifold_edges": int(nonmanifold),
        "voxel_mm": voxel_mm,
        "extents_mm": [bounds[1] - bounds[0], bounds[3] - bounds[2], bounds[5] - bounds[4]],
    }


def command_doctor(args: argparse.Namespace) -> int:
    modules = {
        "numpy": importlib.util.find_spec("numpy") is not None,
        "scipy": importlib.util.find_spec("scipy") is not None,
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
        "voxel_mm",
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
        result = build_mesh(args.input, args.output, preset, verbose=not args.json)
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

    parser = argparse.ArgumentParser(prog="stl-print-prep", parents=[json_parent])
    sub = parser.add_subparsers(dest="command", required=True)

    doctor = sub.add_parser("doctor", help="verify local dependencies", parents=[json_parent])
    doctor.set_defaults(func=command_doctor)

    presets = sub.add_parser("presets", help="list available presets")
    presets.add_argument("--json", action="store_true", default=argparse.SUPPRESS)
    presets.set_defaults(func=command_presets)

    build = sub.add_parser("build", help="make an existing STL print-ready", parents=[json_parent])
    build.add_argument("--input", type=Path, required=True, help="input STL path")
    build.add_argument("--output", type=Path, required=True, help="output STL path")
    build.add_argument("--preset", choices=sorted(PRESETS), default="resin")
    build.add_argument("--voxel-mm", type=float)
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
