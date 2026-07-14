"""DIGIPIN encoder ported from the India Post reference implementation.

Reference: https://github.com/INDIAPOST-gov/digipin
Copyright Department of Posts, licensed under Apache-2.0.
The port preserves the official 10-character continuous format and grid bounds.
"""

from __future__ import annotations

DIGIPIN_GRID = (
    ("F", "C", "9", "8"),
    ("J", "3", "2", "7"),
    ("K", "4", "5", "6"),
    ("L", "M", "P", "T"),
)

MIN_LAT, MAX_LAT = 2.5, 38.5
MIN_LON, MAX_LON = 63.5, 99.5


def encode(latitude: float, longitude: float) -> str:
    if not MIN_LAT <= latitude <= MAX_LAT:
        raise ValueError("Latitude out of range")
    if not MIN_LON <= longitude <= MAX_LON:
        raise ValueError("Longitude out of range")

    min_lat, max_lat = MIN_LAT, MAX_LAT
    min_lon, max_lon = MIN_LON, MAX_LON
    characters: list[str] = []

    for _ in range(10):
        lat_div = (max_lat - min_lat) / 4
        lon_div = (max_lon - min_lon) / 4
        row = 3 - int((latitude - min_lat) // lat_div)
        col = int((longitude - min_lon) // lon_div)
        row = max(0, min(row, 3))
        col = max(0, min(col, 3))
        characters.append(DIGIPIN_GRID[row][col])

        max_lat = min_lat + lat_div * (4 - row)
        min_lat = min_lat + lat_div * (3 - row)
        min_lon = min_lon + lon_div * col
        max_lon = min_lon + lon_div

    return "".join(characters)


def decode(digipin: str) -> tuple[float, float]:
    pin = digipin.strip().upper()
    valid = {char for row in DIGIPIN_GRID for char in row}
    if len(pin) != 10 or any(char not in valid for char in pin):
        raise ValueError("Invalid DIGIPIN")

    min_lat, max_lat = MIN_LAT, MAX_LAT
    min_lon, max_lon = MIN_LON, MAX_LON
    lookup = {char: (row, col) for row, values in enumerate(DIGIPIN_GRID) for col, char in enumerate(values)}

    for char in pin:
        row, col = lookup[char]
        lat_div = (max_lat - min_lat) / 4
        lon_div = (max_lon - min_lon) / 4
        lat1 = max_lat - lat_div * (row + 1)
        lat2 = max_lat - lat_div * row
        lon1 = min_lon + lon_div * col
        lon2 = min_lon + lon_div * (col + 1)
        min_lat, max_lat = lat1, lat2
        min_lon, max_lon = lon1, lon2

    return round((min_lat + max_lat) / 2, 6), round((min_lon + max_lon) / 2, 6)
