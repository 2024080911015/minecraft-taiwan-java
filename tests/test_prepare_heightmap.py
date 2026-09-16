from pathlib import Path
from types import SimpleNamespace

import numpy as np
import rasterio
from PIL import Image
from rasterio.transform import from_bounds

from prepare_heightmap import (
    build_world_heights,
    derive_output_grid,
    run,
    world_y_to_u16,
)


def test_projected_grid_uses_square_pixels():
    grid = derive_output_grid((0.0, 0.0, 100_000.0, 250_000.0), 1000)
    assert grid.width == 1000
    assert grid.height == 2500
    assert grid.metres_per_block == 100.0


def test_world_y_encoding_uses_full_16_bit_range():
    y = np.array([[-64.0, 319.0]], dtype=np.float32)
    encoded = world_y_to_u16(y, -64, 320)
    assert encoded.dtype == np.uint16
    assert encoded.tolist() == [[0, 65535]]


def test_real_scale_height_mapping():
    dem = np.array([[0.0, 1000.0, np.nan]], dtype=np.float32)
    world_y, land = build_world_heights(
        dem,
        metres_per_block=100.0,
        sea_level=62,
        ocean_floor=45,
        land_threshold=0.5,
        vertical_exaggeration=2.0,
        elevation_unit_scale=1.0,
        max_elevation=4200.0,
        upper_build_limit=320,
    )
    assert land.tolist() == [[False, True, False]]
    assert world_y.tolist() == [[45.0, 82.0, 45.0]]


def test_end_to_end_with_geographic_dem(tmp_path: Path):
    dem_path = tmp_path / "synthetic.tif"
    data = np.zeros((30, 12), dtype=np.float32)
    data[4:27, 3:9] = np.linspace(1, 3952, 23)[:, None]
    transform = from_bounds(120.0, 21.5, 122.0, 25.5, data.shape[1], data.shape[0])
    with rasterio.open(
        dem_path,
        "w",
        driver="GTiff",
        width=data.shape[1],
        height=data.shape[0],
        count=1,
        dtype="float32",
        crs="EPSG:4326",
        transform=transform,
        nodata=-9999.0,
    ) as dst:
        dst.write(data, 1)

    output_dir = tmp_path / "output"
    metadata = run(
        SimpleNamespace(
            input=dem_path,
            output_dir=output_dir,
            target_width=200,
            target_crs="EPSG:3826",
            sea_level=62,
            ocean_floor=45,
            land_threshold=0.5,
            vertical_exaggeration=2.0,
            elevation_unit_scale=1.0,
            max_elevation=4200.0,
            lower_build_limit=-64,
            upper_build_limit=320,
        )
    )

    heightmap = Image.open(output_dir / "taiwan_height_16bit.png")
    assert heightmap.size[0] == 200
    assert heightmap.size[1] > heightmap.size[0]
    assert np.asarray(heightmap).max() > np.asarray(heightmap).min()
    assert metadata["target_crs"] == "EPSG:3826"
