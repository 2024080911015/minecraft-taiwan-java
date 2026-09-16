#!/usr/bin/env python3
"""Convert a Taiwan DEM GeoTIFF into a WorldPainter-ready 16-bit height map.

The input raster is reprojected to a metre-based CRS before resizing. This keeps
one output pixel square in the real world and avoids stretching latitude and
longitude degrees as if they had the same length.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image
from rasterio.crs import CRS
from rasterio.transform import from_origin
from rasterio.warp import Resampling, reproject, transform_bounds


@dataclass(frozen=True)
class OutputGrid:
    width: int
    height: int
    metres_per_block: float
    left: float
    bottom: float
    right: float
    top: float


def derive_output_grid(
    bounds: tuple[float, float, float, float], target_width: int
) -> OutputGrid:
    """Build a square-pixel grid from projected bounds."""
    left, bottom, right, top = bounds
    projected_width = right - left
    projected_height = top - bottom
    if target_width < 1:
        raise ValueError("target_width must be at least 1")
    if projected_width <= 0 or projected_height <= 0:
        raise ValueError("DEM bounds must have a positive width and height")

    metres_per_block = projected_width / target_width
    target_height = max(1, round(projected_height / metres_per_block))
    return OutputGrid(
        width=target_width,
        height=target_height,
        metres_per_block=metres_per_block,
        left=left,
        bottom=bottom,
        right=right,
        top=top,
    )


def world_y_to_u16(
    world_y: np.ndarray, lower_build_limit: int, upper_build_limit: int
) -> np.ndarray:
    """Linearly encode Minecraft Y coordinates into the full uint16 range."""
    highest_y = upper_build_limit - 1
    if highest_y <= lower_build_limit:
        raise ValueError("upper_build_limit must exceed lower_build_limit by 2+")
    clipped = np.clip(world_y, lower_build_limit, highest_y)
    normalized = (clipped - lower_build_limit) / (highest_y - lower_build_limit)
    return np.rint(normalized * 65535.0).astype(np.uint16)


def build_world_heights(
    dem: np.ndarray,
    *,
    metres_per_block: float,
    sea_level: int,
    ocean_floor: int,
    land_threshold: float,
    vertical_exaggeration: float,
    elevation_unit_scale: float,
    max_elevation: float,
    upper_build_limit: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Map elevation in metres to Minecraft Y coordinates."""
    valid = np.isfinite(dem)
    elevation_metres = dem * elevation_unit_scale
    land = valid & (elevation_metres > land_threshold)

    safe_elevation = np.nan_to_num(elevation_metres, nan=0.0)
    safe_elevation = np.clip(safe_elevation, 0.0, max_elevation)
    vertical_metres_per_block = metres_per_block / vertical_exaggeration

    world_y = np.full(dem.shape, float(ocean_floor), dtype=np.float32)
    land_y = sea_level + safe_elevation / vertical_metres_per_block
    world_y[land] = np.maximum(land_y[land], sea_level + 1)
    world_y = np.clip(world_y, -10_000, upper_build_limit - 1)
    return world_y, land


def make_preview(world_y: np.ndarray, land: np.ndarray, sea_level: int) -> Image.Image:
    """Create an RGB preview; this file is not imported into WorldPainter."""
    rgb = np.zeros((*world_y.shape, 3), dtype=np.uint8)
    rgb[:] = (31, 89, 140)

    relief = np.maximum(world_y - sea_level, 0)
    max_relief = max(float(relief[land].max()) if np.any(land) else 1.0, 1.0)
    t = np.clip(relief / max_relief, 0.0, 1.0)

    low = land & (t < 0.45)
    mid = land & (t >= 0.45) & (t < 0.78)
    high = land & (t >= 0.78)
    rgb[low] = np.stack(
        [55 + 80 * t[low], 130 + 60 * t[low], 55 + 40 * t[low]], axis=1
    ).astype(np.uint8)
    rgb[mid] = np.stack(
        [125 + 70 * t[mid], 115 - 35 * t[mid], 65 - 20 * t[mid]], axis=1
    ).astype(np.uint8)
    rgb[high] = np.stack(
        [165 + 90 * t[high], 150 + 105 * t[high], 135 + 120 * t[high]], axis=1
    ).astype(np.uint8)
    return Image.fromarray(rgb, mode="RGB")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="将台湾 DEM 转换为 WorldPainter 可导入的 16 位 PNG 高程图"
    )
    parser.add_argument("input", type=Path, help="输入 DEM GeoTIFF，例如 taiwan_dem.tif")
    parser.add_argument("--output-dir", type=Path, default=Path("output"))
    parser.add_argument("--target-width", type=int, default=2000, help="输出宽度（方块）")
    parser.add_argument(
        "--target-crs",
        default="EPSG:3826",
        help="米制投影；台湾默认使用 TWD97 / TM2 zone 121 (EPSG:3826)",
    )
    parser.add_argument("--sea-level", type=int, default=62)
    parser.add_argument("--ocean-floor", type=int, default=45)
    parser.add_argument("--land-threshold", type=float, default=0.5)
    parser.add_argument(
        "--vertical-exaggeration",
        type=float,
        default=2.0,
        help="垂直夸张倍数；1.0 为水平与垂直同比例",
    )
    parser.add_argument(
        "--elevation-unit-scale",
        type=float,
        default=1.0,
        help="输入高程换算到米的乘数；DEM 已是米时保持 1.0",
    )
    parser.add_argument("--max-elevation", type=float, default=4200.0)
    parser.add_argument("--lower-build-limit", type=int, default=-64)
    parser.add_argument("--upper-build-limit", type=int, default=320)
    return parser.parse_args()


def run(args: argparse.Namespace) -> dict[str, object]:
    if not args.input.exists():
        raise FileNotFoundError(f"找不到 DEM 文件：{args.input}")
    if args.vertical_exaggeration <= 0:
        raise ValueError("--vertical-exaggeration 必须大于 0")
    if args.ocean_floor >= args.sea_level:
        raise ValueError("--ocean-floor 必须低于 --sea-level")

    target_crs = CRS.from_user_input(args.target_crs)
    if not target_crs.is_projected:
        raise ValueError("--target-crs 必须是米制投影坐标系，不能直接使用经纬度")

    with rasterio.open(args.input) as src:
        if src.crs is None:
            raise ValueError("输入 DEM 没有 CRS 信息，无法保证真实比例")

        projected_bounds = transform_bounds(
            src.crs, target_crs, *src.bounds, densify_pts=21
        )
        grid = derive_output_grid(projected_bounds, args.target_width)
        destination = np.full((grid.height, grid.width), np.nan, dtype=np.float32)
        dst_transform = from_origin(
            grid.left, grid.top, grid.metres_per_block, grid.metres_per_block
        )
        reproject(
            source=rasterio.band(src, 1),
            destination=destination,
            src_transform=src.transform,
            src_crs=src.crs,
            src_nodata=src.nodata,
            dst_transform=dst_transform,
            dst_crs=target_crs,
            dst_nodata=np.nan,
            resampling=Resampling.bilinear,
        )
        source_info = {
            "path": str(args.input),
            "crs": str(src.crs),
            "width": src.width,
            "height": src.height,
            "nodata": src.nodata,
        }

    world_y, land = build_world_heights(
        destination,
        metres_per_block=grid.metres_per_block,
        sea_level=args.sea_level,
        ocean_floor=args.ocean_floor,
        land_threshold=args.land_threshold,
        vertical_exaggeration=args.vertical_exaggeration,
        elevation_unit_scale=args.elevation_unit_scale,
        max_elevation=args.max_elevation,
        upper_build_limit=args.upper_build_limit,
    )
    encoded = world_y_to_u16(
        world_y, args.lower_build_limit, args.upper_build_limit
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    height_path = args.output_dir / "taiwan_height_16bit.png"
    preview_path = args.output_dir / "taiwan_preview.png"
    mask_path = args.output_dir / "taiwan_mask.png"
    settings_path = args.output_dir / "worldpainter_settings.json"

    Image.fromarray(encoded).save(height_path)
    make_preview(world_y, land, args.sea_level).save(preview_path)
    Image.fromarray(land.astype(np.uint8) * 255).save(mask_path)

    finite_dem = destination[np.isfinite(destination)]
    metadata: dict[str, object] = {
        "source": source_info,
        "target_crs": str(target_crs),
        "grid": asdict(grid),
        "vertical_exaggeration": args.vertical_exaggeration,
        "vertical_metres_per_block": grid.metres_per_block
        / args.vertical_exaggeration,
        "dem_min": float(finite_dem.min()) if finite_dem.size else None,
        "dem_max": float(finite_dem.max()) if finite_dem.size else None,
        "generated_peak_y": float(world_y[land].max()) if np.any(land) else None,
        "land_percent": float(land.mean() * 100.0),
        "worldpainter": {
            "image_low": 0,
            "image_high": 65535,
            "world_low": args.lower_build_limit,
            "world_high": args.upper_build_limit - 1,
            "water_level": args.sea_level,
        },
        "files": {
            "heightmap": height_path.name,
            "preview": preview_path.name,
            "mask": mask_path.name,
        },
    }
    settings_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"完成：{height_path} ({grid.width} x {grid.height}, 16-bit 灰度)")
    print(f"水平比例：1 方块 = {grid.metres_per_block:.2f} 米")
    print(
        "垂直比例：1 方块 = "
        f"{grid.metres_per_block / args.vertical_exaggeration:.2f} 米"
    )
    if np.any(land):
        print(f"生成最高点：Y={world_y[land].max():.1f}")
    print(f"WorldPainter 参数：见 {settings_path}")
    return metadata


def main() -> None:
    run(parse_args())


if __name__ == "__main__":
    main()
