"""Check that no digital-twin shipping lane is drawn over land.

Each lane is the polyline port -> waypoints -> port, drawn as straight
segments on the map. This tests every segment against Natural Earth 1:10m
land polygons (public domain, https://www.naturalearthdata.com) and reports
how far, in nautical miles, each lane runs over land and where.

    pip install shapely pyshp
    python pipeline/check_lane_land.py            # report; exit 1 if any lane crosses land
    python pipeline/check_lane_land.py --land path/to/ne_10m_land.shp

The land file is downloaded once to pipeline/.cache/. Longitudes are
unwrapped so trans-Pacific lanes are tested the way they are drawn.
"""

import argparse
import io
import sys
import urllib.request
import zipfile
from pathlib import Path

import shapefile
from shapely.affinity import translate
from shapely.geometry import LineString, shape
from shapely.ops import unary_union
from shapely.prepared import prep

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))


LAND_URL = "https://naciscdn.org/naturalearth/10m/physical/ne_10m_land.zip"
CACHE = Path(__file__).resolve().parent / ".cache"
NM_PER_DEGREE = 60.0


def land_shapefile(explicit):
    if explicit:
        return Path(explicit)
    shp = CACHE / "ne_10m_land.shp"
    if not shp.exists():
        CACHE.mkdir(exist_ok=True)
        print(f"Downloading Natural Earth land to {CACHE} ...")
        with urllib.request.urlopen(LAND_URL) as response:
            zipfile.ZipFile(io.BytesIO(response.read())).extractall(CACHE)
    return shp


def land_geometry(path):
    """Natural Earth land, with the Suez Canal (missing from it) carved out."""
    from app.twin.coordinates import SUEZ_CANAL_CENTERLINE

    reader = shapefile.Reader(str(path))
    land = unary_union([shape(r.__geo_interface__) for r in reader.shapes()])
    canal = LineString([(lon, lat) for lat, lon in SUEZ_CANAL_CENTERLINE]).buffer(0.02)
    return land.difference(canal)


def unwrapped(points):
    """[(lat, lon)] -> [(lon, lat)] with each step taking the short way round."""
    out = [(points[0][1], points[0][0])]
    for lat, lon in points[1:]:
        prev = out[-1][0]
        while lon - prev > 180:
            lon -= 360
        while lon - prev < -180:
            lon += 360
        out.append((lon, lat))
    return out


def crossings(land, poly, land_geom):
    """[(segment start, segment end, nm over land)] for one lane."""
    hits = []
    pts = unwrapped(poly)
    for a, b in zip(pts, pts[1:]):
        segment = LineString([a, b])
        if land.intersects(segment):
            over = segment.intersection(land_geom).length * NM_PER_DEGREE
            hits.append((a, b, over))
    return hits


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--land")
    args = parser.parse_args()

    path = land_shapefile(args.land)
    land_geom = land_geometry(path)
    land_geom = unary_union([land_geom, translate(land_geom, xoff=360)])
    land = prep(land_geom)

    from app.fleet.geometry import lane_polyline
    from app.twin.digital_twin import get_digital_twin

    twin = get_digital_twin()
    bad = 0
    for _, _, attrs in sorted(twin.graph.edges(data=True), key=lambda e: e[2]["lane_id"]):
        hits = crossings(land, lane_polyline(attrs), land_geom)
        if hits:
            bad += 1
            total = sum(h[2] for h in hits)
            print(f"{attrs['lane_id']}: {total:,.0f} nm over land in {len(hits)} segment(s)")
            for (lon1, lat1), (lon2, lat2), over in hits:
                print(f"    ({lat1:.2f}, {lon1:.2f}) -> ({lat2:.2f}, {lon2:.2f})  {over:,.0f} nm")
    print(f"\n{bad} of {twin.graph.number_of_edges()} lanes cross land")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
