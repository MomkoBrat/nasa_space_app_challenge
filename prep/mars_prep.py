
import sys
import rasterio

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
