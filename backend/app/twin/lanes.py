"""Curated shipping-lane topology for the digital twin.

Real major container trade lanes between the 20 ports in
port_congestion.csv, grouped by the trade they represent (trans-Pacific,
Asia-Europe, Middle East, intra-regional, ...). This is not an
exhaustive port-pair matrix -- it's the structure of actual documented
container shipping networks, curated by hand rather than derived from
any dataset in this repo.

Each lane names the monitored sea-state corridors (see
MONITORED_LOCATIONS in live_conditions_client.py) it passes through, in
order from origin to destination, so DigitalTwin can (a) sum real
great-circle segments through those waypoints for a more realistic
distance than a straight port-to-port line, and (b) pull each corridor's
live risk score onto the edges that actually cross it. A lane with no
waypoints doesn't cross any of the 8 monitored corridors -- its risk
comes from port congestion alone, not sea state.

Where a real alternative exists (Suez vs. the Cape of Good Hope bypass),
both are listed as distinct lanes with their own ids, not folded into
one "average" edge -- that choice is exactly what Slice 06's routing
agent needs to be able to make.
"""

from typing import List, NamedTuple


class Lane(NamedTuple):
    lane_id: str
    port_a: str
    port_b: str
    waypoints: List[str]  # MONITORED_LOCATIONS names, origin -> destination order


SHIPPING_LANES: List[Lane] = [
    # --- Trans-Pacific (Asia -> US West Coast): open ocean, no monitored chokepoint ---
    Lane("shanghai-losangeles", "Shanghai", "Los Angeles", []),
    Lane("shanghai-longbeach", "Shanghai", "Long Beach", []),
    Lane("ningbo-longbeach", "Ningbo", "Long Beach", []),
    Lane("busan-longbeach", "Busan", "Long Beach", []),
    Lane("shenzhen-losangeles", "Shenzhen", "Los Angeles", []),
    Lane("hongkong-losangeles", "Hong Kong", "Los Angeles", []),

    # --- Asia - Europe via Suez ---
    Lane("shanghai-rotterdam-suez", "Shanghai", "Rotterdam",
         ["Strait of Malacca", "Gulf of Aden", "Suez Canal (Gulf of Suez)"]),
    Lane("shanghai-hamburg-suez", "Shanghai", "Hamburg",
         ["Strait of Malacca", "Gulf of Aden", "Suez Canal (Gulf of Suez)"]),
    Lane("ningbo-rotterdam-suez", "Ningbo", "Rotterdam",
         ["Strait of Malacca", "Gulf of Aden", "Suez Canal (Gulf of Suez)"]),
    Lane("singapore-rotterdam-suez", "Singapore", "Rotterdam",
         ["Gulf of Aden", "Suez Canal (Gulf of Suez)"]),
    Lane("hongkong-felixstowe-suez", "Hong Kong", "Felixstowe",
         ["Strait of Malacca", "Gulf of Aden", "Suez Canal (Gulf of Suez)"]),

    # --- Asia - Europe via Cape of Good Hope (real alternative to Suez) ---
    Lane("shanghai-rotterdam-cape", "Shanghai", "Rotterdam",
         ["Strait of Malacca", "Cape of Good Hope"]),
    Lane("singapore-rotterdam-cape", "Singapore", "Rotterdam",
         ["Cape of Good Hope"]),

    # --- Middle East ---
    Lane("dubai-singapore", "Dubai (Jebel Ali)", "Singapore",
         ["Strait of Hormuz", "Arabian Sea"]),
    Lane("dubai-rotterdam", "Dubai (Jebel Ali)", "Rotterdam",
         ["Strait of Hormuz", "Gulf of Aden", "Suez Canal (Gulf of Suez)"]),
    Lane("dubai-colombo", "Dubai (Jebel Ali)", "Colombo",
         ["Strait of Hormuz", "Arabian Sea"]),

    # --- Asia - US East Coast via Suez ---
    Lane("shanghai-newyork-suez", "Shanghai", "New York",
         ["Strait of Malacca", "Gulf of Aden", "Suez Canal (Gulf of Suez)"]),
    Lane("ningbo-newyork-suez", "Ningbo", "New York",
         ["Strait of Malacca", "Gulf of Aden", "Suez Canal (Gulf of Suez)"]),

    # --- Intra-Southeast/South Asia ---
    Lane("singapore-colombo", "Singapore", "Colombo", []),
    Lane("singapore-tanjungpelepas", "Singapore", "Tanjung Pelepas", []),
    Lane("singapore-laemchabang", "Singapore", "Laem Chabang", []),
    Lane("singapore-tanjungpriok", "Singapore", "Tanjung Priok", []),
    Lane("singapore-hongkong", "Singapore", "Hong Kong", []),

    # --- Intra-East Asia ---
    Lane("hongkong-shanghai", "Hong Kong", "Shanghai", []),
    Lane("hongkong-shenzhen", "Hong Kong", "Shenzhen", []),
    Lane("shanghai-busan", "Shanghai", "Busan", []),
    Lane("shanghai-qingdao", "Shanghai", "Qingdao", []),
    Lane("qingdao-busan", "Qingdao", "Busan", []),
    Lane("guangzhou-shenzhen", "Guangzhou", "Shenzhen", []),
    Lane("guangzhou-hongkong", "Guangzhou", "Hong Kong", []),

    # --- Intra-North Europe ---
    Lane("rotterdam-hamburg", "Rotterdam", "Hamburg", []),
    Lane("rotterdam-antwerp", "Rotterdam", "Antwerp", []),
    Lane("rotterdam-felixstowe", "Rotterdam", "Felixstowe", ["English Channel (Dover)"]),
    Lane("hamburg-antwerp", "Hamburg", "Antwerp", []),
    Lane("antwerp-felixstowe", "Antwerp", "Felixstowe", ["English Channel (Dover)"]),
]
