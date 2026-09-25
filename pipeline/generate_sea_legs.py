"""Generate the sea-only geometry between every consecutive pair of points on
each digital-twin shipping lane.

The lanes list the monitored corridors they pass through, but a straight line
between two of those can cut across a peninsula or an island chain. For each
consecutive pair of a lane's anchors (port approach points and waypoints) this
finds the shortest path that stays at sea over a rasterised Natural Earth 1:10m
land mask, simplifies it to the fewest turning points whose straight segments
stay clear of land, and writes them to backend/app/twin/sea_legs.py.

    pip install shapely pyshp numpy pillow networkx
    python pipeline/generate_sea_legs.py approach   # print sea approach point per port
    python pipeline/generate_sea_legs.py legs       # (re)write sea_legs.py

Port approach points (PORT_APPROACH_COORDINATES in coordinates.py) are reviewed
by hand; `approach` only proposes them. Verify the result with
pipeline/check_lane_land.py, which tests the drawn lanes against the exact
land polygons rather than this raster.
"""

import heapq
import sys
from math import cos, radians
from pathlib import Path

import numpy as np
import shapefile
from PIL import Image, ImageDraw, ImageFilter
from shapely.affinity import translate
from shapely.geometry import LineString, shape
from shapely.ops import unary_union
from shapely.prepared import prep

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from check_lane_land import land_geometry, land_shapefile, unwrapped  # noqa: E402

OUT = ROOT / "backend" / "app" / "twin" / "sea_legs.py"
FINE, COARSE = 0.05, 0.1  # degrees per raster cell
COARSE_ABOVE_DEG = 40.0   # legs spanning more than this are searched on the coarse grid
SEARCH_MARGIN_DEG = 8.0
CLEARANCE_DEG = 0.02
CANAL_SNAP_DEG = 0.15


def load_land():
    return [land_geometry(land_shapefile(None))]


def rasterize(geoms, res):
    width, height = int(round(360 / res)), int(round(180 / res))
    image = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(image)
    px = lambda ring: [((lon + 180) / res, (90 - lat) / res) for lon, lat in ring]
    for geom in geoms:
        for poly in getattr(geom, "geoms", [geom]):
            draw.polygon(px(poly.exterior.coords), fill=255)
            for hole in poly.interiors:
                draw.polygon(px(hole.coords), fill=0)
    return image


def blocked_grid(image, cells):
    dilated = image.filter(ImageFilter.MaxFilter(2 * cells + 1)) if cells else image
    return np.array(dilated) > 0


class Grid:
    def __init__(self, blocked, res):
        self.blocked, self.res = blocked, res
        self.height, self.width = blocked.shape

    def cell(self, lat, lon):
        return int((90 - lat) / self.res), int(round((lon + 180) / self.res))

    def point(self, row, col):
        return 90 - (row + 0.5) * self.res, col * self.res - 180 + self.res / 2

    def is_blocked(self, row, col):
        if row < 0 or row >= self.height:
            return True
        return bool(self.blocked[row, col % self.width])


def astar(grid, start, goal, lat_lo, lat_hi, col_lo, col_hi):
    """8-connected shortest sea path on the grid, weighting east-west steps by cos(latitude)."""
    r_lo, r_hi = grid.cell(lat_hi, 0)[0], grid.cell(lat_lo, 0)[0]
    r_lo, r_hi = max(r_lo, 0), min(r_hi, grid.height - 1)

    def heuristic(r, c):
        lat = grid.point(r, c)[0]
        dx = abs(c - goal[1]) * cos(radians(lat))
        dy = abs(r - goal[0])
        return (dx + dy) + (2 ** 0.5 - 2) * min(dx, dy)

    open_heap = [(heuristic(*start), 0.0, start)]
    best = {start: 0.0}
    parent = {}
    while open_heap:
        _, cost, node = heapq.heappop(open_heap)
        if node == goal:
            path = [node]
            while node in parent:
                node = parent[node]
                path.append(node)
            return path[::-1]
        if cost > best.get(node, float("inf")):
            continue
        r, c = node
        step_x = cos(radians(grid.point(r, c)[0]))
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr == 0 and dc == 0:
                    continue
                nr, nc = r + dr, c + dc
                if nr < r_lo or nr > r_hi or nc < col_lo or nc > col_hi or grid.is_blocked(nr, nc):
                    continue
                # Don't squeeze diagonally between two blocked corners.
                if dr and dc and grid.is_blocked(r + dr, c) and grid.is_blocked(r, c + dc):
                    continue
                new_cost = cost + ((dr * dr + (dc * step_x) ** 2) ** 0.5)
                if new_cost < best.get((nr, nc), float("inf")):
                    best[(nr, nc)] = new_cost
                    parent[(nr, nc)] = node
                    heapq.heappush(open_heap, (new_cost + heuristic(nr, nc), new_cost, (nr, nc)))
    return None


class Router:
    def __init__(self):
        geoms = load_land()
        self.image = {res: rasterize(geoms, res) for res in (FINE, COARSE)}
        # The canal is narrower than a cell, so open it explicitly.
        from app.twin.coordinates import SUEZ_CANAL_CENTERLINE

        for res, image in self.image.items():
            ImageDraw.Draw(image).line(
                [((lon + 180) / res, (90 - lat) / res) for lat, lon in SUEZ_CANAL_CENTERLINE], fill=0, width=2
            )
        self.grids = {}
        from app.twin.coordinates import SUEZ_CANAL_CENTERLINE

        canal = LineString([(lon, lat) for lat, lon in SUEZ_CANAL_CENTERLINE]).buffer(0.05)
        merged = unary_union(geoms).difference(canal)
        self.land = prep(unary_union([merged, translate(merged, xoff=360), translate(merged, xoff=-360)]))

    def grid(self, res, cells):
        key = (res, cells)
        if key not in self.grids:
            self.grids[key] = Grid(blocked_grid(self.image[res], cells), res)
        return self.grids[key]

    def clear(self, a, b):
        # Keep CLEARANCE_DEG (~1.2 nm) off the coast so raster error can't put a segment on land.
        return not self.land.intersects(LineString([(a[1], a[0]), (b[1], b[0])]).buffer(CLEARANCE_DEG))

    def path_clear(self, a, points, b):
        pts = [a, *points, b]
        xy = unwrapped(pts)
        return all(
            not self.land.intersects(LineString([p, q]).buffer(CLEARANCE_DEG)) for p, q in zip(xy, xy[1:])
        )

    def nearest_open(self, lat, lon, cells=3, radius_deg=4.0):
        """The closest sea point at least `cells` fine cells from any coast."""
        grid = self.grid(FINE, cells)
        r0, c0 = grid.cell(lat, lon)
        best = None
        reach = int(radius_deg / FINE)
        for dr in range(-reach, reach + 1):
            for dc in range(-reach, reach + 1):
                if grid.is_blocked(r0 + dr, c0 + dc):
                    continue
                d = dr * dr + (dc * cos(radians(lat))) ** 2
                if best is None or d < best[0]:
                    best = (d, r0 + dr, c0 + dc)
        return None if best is None else grid.point(best[1], best[2])

    def leg(self, a, b):
        """Intermediate (lat, lon) points of a sea-only path from a to b; [] if the straight line is already clear."""
        lon_b = b[1]
        while lon_b - a[1] > 180:
            lon_b -= 360
        while lon_b - a[1] < -180:
            lon_b += 360
        b = (b[0], lon_b)
        if self.clear(a, b):
            return []
        span = max(abs(a[0] - b[0]), abs(a[1] - b[1]))
        res = COARSE if span > COARSE_ABOVE_DEG else FINE
        for margin in (SEARCH_MARGIN_DEG, 3 * SEARCH_MARGIN_DEG):
            for cells in (2, 1, 0):
                grid = self.grid(res, cells if res == FINE else cells // 2)
                start, goal = grid.cell(*a), (grid.cell(*b)[0], int(round((b[1] + 180) / res)))
                start = (start[0], int(round((a[1] + 180) / res)))
                if grid.is_blocked(*start) or grid.is_blocked(*goal):
                    continue
                lat_lo, lat_hi = min(a[0], b[0]) - margin, max(a[0], b[0]) + margin
                col_lo = int((min(a[1], b[1]) - margin + 180) / res)
                col_hi = int((max(a[1], b[1]) + margin + 180) / res)
                path = astar(grid, start, goal, lat_lo, lat_hi, col_lo, col_hi)
                if path:
                    return self.simplify(a, b, [grid.point(r, c) for r, c in path], grid)
        raise RuntimeError(f"no sea path from {a} to {b}")

    def through_canal(self, pts):
        """Replace the stretch of a raw path inside the Suez Canal with its centreline."""
        from app.twin.coordinates import SUEZ_CANAL_CENTERLINE

        def near(p):
            return any(abs(p[0] - la) < CANAL_SNAP_DEG and abs(p[1] - lo) < CANAL_SNAP_DEG for la, lo in SUEZ_CANAL_CENTERLINE)

        idx = [i for i, p in enumerate(pts) if near(p)]
        if not idx:
            return pts
        i0, i1 = idx[0], idx[-1]
        line = list(SUEZ_CANAL_CENTERLINE)
        if i0 > 0 and abs(pts[i0 - 1][0] - line[0][0]) > abs(pts[i0 - 1][0] - line[-1][0]):
            line.reverse()
        return pts[:i0] + line + pts[i1 + 1:]

    def simplify(self, a, b, cells, grid):
        pts = self.through_canal([a] + [(la, lo) for la, lo in cells[1:-1]] + [b])
        # Cell centres carry the column's unwrapped offset already (col may exceed width).
        out, i = [pts[0]], 0
        while i < len(pts) - 1:
            j = len(pts) - 1
            while j > i + 1 and not self.clear(pts[i], pts[j]):
                j -= 1
            out.append(pts[j])
            i = j
        return [(round(la, 2), round(lo, 2)) for la, lo in out[1:-1]]


def lane_anchor_pairs():
    from app.twin.coordinates import PORT_APPROACH_COORDINATES
    from app.twin.digital_twin import WAYPOINT_COORDINATES
    from app.twin.lanes import SHIPPING_LANES

    coords = {**WAYPOINT_COORDINATES, **PORT_APPROACH_COORDINATES}
    pairs = {}
    for lane in SHIPPING_LANES:
        names = [lane.port_a, *lane.waypoints, lane.port_b]
        for x, y in zip(names, names[1:]):
            key = (x, y) if (y, x) not in pairs else (y, x)
            pairs[key] = (coords[key[0]], coords[key[1]])
    return pairs


def main():
    command = sys.argv[1] if len(sys.argv) > 1 else "legs"
    router = Router()
    if command == "approach":
        from app.twin.coordinates import PORT_COORDINATES

        for name, (lat, lon) in PORT_COORDINATES.items():
            found = router.nearest_open(lat, lon)
            print(f'    "{name}": ({found[0]:.2f}, {found[1]:.2f}),' if found else f"    # {name}: none found")
        return
    import json

    cache_file = ROOT / "pipeline" / ".cache" / "legs.json"
    cache = json.loads(cache_file.read_text()) if cache_file.exists() else {}
    lines = []
    for (a, b), (pa, pb) in sorted(lane_anchor_pairs().items()):
        key = f"v2|{a}|{b}|{pa}|{pb}"
        if key not in cache and f"{a}|{b}|{pa}|{pb}" in cache:
            old = [tuple(p) for p in cache[f"{a}|{b}|{pa}|{pb}"]]
            from app.twin.coordinates import SUEZ_CANAL_CENTERLINE

            near_canal = any(abs(p[0] - la) < 1.0 and abs(p[1] - lo) < 1.0 for p in old for la, lo in SUEZ_CANAL_CENTERLINE)
            if not near_canal and router.path_clear(pa, old, pb):
                cache[key] = old  # verified against the new clearance rule
        if key not in cache:
            cache[key] = router.leg(pa, pb)
            cache_file.write_text(json.dumps(cache))
        points = [tuple(p) for p in cache[key]]
        print(f"{a} -> {b}: {len(points)} intermediate point(s)")
        lines.append(f'    ({a!r}, {b!r}): {points!r},')
    OUT.write_text(
        '"""Sea-only intermediate points between consecutive anchors of each lane.\n\n'
        "Generated by pipeline/generate_sea_legs.py -- do not edit by hand.\n"
        'An empty list means the straight line between the two anchors is already at sea."""\n\n'
        "from typing import Dict, List, Tuple\n\n"
        "SEA_LEGS: Dict[Tuple[str, str], List[Tuple[float, float]]] = {\n" + "\n".join(lines) + "\n}\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
