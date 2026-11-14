
import sys
import rasterio
import numpy as np
mask = np.fromfile("global_ti_msk_day_2007.img", dtype=np.uint8).reshape(3600, 7200)
valid_fraction = mask[r0:r1, c0:c1].mean()   # share of real pixels in a window

def inspect_dem(file_path):
    with rasterio.open(file_path) as dem:
        print("Width:", dem.width)
        print("Height:", dem.height)
        print("CRS:", dem.crs)
        print("Pixel resolution:", dem.res)
        print("Bounds:", dem.bounds)
        print("NoData:", dem.nodata)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python prep/mars_prep.py <dem_file>")
        sys.exit(1)

    inspect_dem(sys.argv[1])
