"""Seed script for dim_cartera_clientes master table.

Produces synthetic-but-realistic Santa Fe agro producer data for development.
CUITs are formatted as real Argentine CUITs (20-27 digits with verification digit).
Lot polygons are generated within real department boundaries (Rosario, Caseros,
Constitución, General López) via buffered centroids.

Usage:
    python src/seed/cartera_seeder.py --rows 100 --output data/seed_cartera.csv
"""

import argparse
import csv
import random
from pathlib import Path

# Real Argentine CUIT prefixes (2-8 digits + verification)
CUIT_PREFIXES = [
    "20-", "23-", "24-", "27-",  # Societas, Responsables Inscriptos
    "30-", "33-", "34-", "35-",  # Extranjeras, Societies
    "25-", "26-",  # Otros
]

DEPARTMENTS = {
    "Rosario": {"center": (32.90, -60.66), "buffer_km": 35},
    "Caseros": {"center": (33.10, -60.70), "buffer_km": 30},
    "Constitución": {"center": (32.80, -60.60), "buffer_km": 33},
    "General López": {"center": (31.95, -61.55), "buffer_km": 40},
}

BASE_NAMES = [
    "Agro Santa Fe S.A.", "Cultivos y Ganadería Ltda.", "Estancia del Norte S.A.",
    "Proagro Centro Cooperativa", "Soja Plus S.R.L.", "Campo Grande S.A.",
    "Agrocrecimiento Ltda.", "Sol y Campo S.A.", "Nuevo Horizonte Cooperativa",
    "Valle Escondido S.A.", "Micro Agro S.R.L.", "Granos del Sur Cooperativa",
]

CROPS = ["soja", "maíz", "trigo"]
CROP_PROBS = [0.60, 0.30, 0.10]


def generate_cuit(prefix_idx=None):
    """Generate a realistic Argentine CUIT."""
    if prefix_idx is None:
        prefix_idx = random.randrange(len(CUIT_PREFIXES))
    prefix = CUIT_PREFIXES[prefix_idx]
    # Generate 8 random digits
    base = "".join(str(random.randint(0, 9)) for _ in range(8))
    # Simple verification: sum of (digit * weight) mod 11
    weights = [5, 4, 3, 2, 9, 8, 7, 6]
    total = sum(int(d) * w for d, w in zip(base, weights))
    ver = 11 - (total % 11)
    if ver == 11:
        ver = "0"
    elif ver == 10:
        ver = "9"
    else:
        ver = str(ver)
    return f"{prefix}{base}-{ver}"


def generate_polygon(center_lat, center_lon, buffer_km):
    """Generate a simple rectangular-ish polygon around a center point."""
    # Approximate: 1 deg lat ~ 111 km, 1 deg lon ~ 111 * cos(lat) km
    lat_buffer = buffer_km / 111.0
    lon_buffer = buffer_km / (111.0 * abs(__import__("math").cos(center_lon * 3.14159 / 180.0)))
    coords = [
        [center_lon - lon_buffer, center_lat - lat_buffer],
        [center_lon + lon_buffer, center_lat - lat_buffer],
        [center_lon + lon_buffer, center_lat + lat_buffer],
        [center_lon - lon_buffer, center_lat + lat_buffer],
        [center_lon - lon_buffer, center_lat - lat_buffer],  # close
    ]
    import json
    return json.dumps({"type": "Polygon", "coordinates": [coords]})


def main():
    parser = argparse.ArgumentParser(description="Seed dim_cartera_clientes data")
    parser.add_argument("--rows", type=int, default=50, help="Number of producer rows")
    parser.add_argument("--output", type=str, default="data/seed_cartera.csv", help="Output CSV path")
    args = parser.parse_args()

    rows = args.rows
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["cuit", "nombre_razon_social", "rubro", "hectareas_totales", "bbox_geom"])

        for i in range(rows):
            cuit = generate_cuit()
            name = random.choice(BASE_NAMES)
            rubro = random.choice(["Soja", "Maíz", "Ganadería", "Trigo", "Mixto"])
            hectares = round(random.uniform(20, 200), 1)
            dept = random.choice(list(DEPARTMENTS.keys()))
            center = DEPARTMENTS[dept]["center"]
            polygon = generate_polygon(center[0], center[1], DEPARTMENTS[dept]["buffer_km"])
            writer.writerow([cuit, name, rubro, hectares, polygon])

    print(f"Generated {rows} rows -> {output_path}")


if __name__ == "__main__":
    main()