"""Load seed CSV into Postgres dim_cartera_clientes.

Usage (via Airflow or locally):
    python src/seed/load_cartera.py data/seed_cartera.csv
    # Or via Airflow: psql command in a BashOperator
"""

import csv
import json
import sys
from pathlib import Path

import psycopg2


def parse_geom(geom_str: str):
    """Parse the bbox_geom GeoJSON Polygon string into a PostGIS geometry."""
    geom = json.loads(geom_str)
    # PostGIS expects GeoJSON format directly via ST_GeomFromGeoJSON
    return geom


def main(csv_path: str):
    csv_path = Path(csv_path)
    if not csv_path.exists():
        print(f"File not found: {csv_path}")
        sys.exit(1)

    conn = psycopg2.connect(
        host="localhost",
        dbname="agro",
        user="postgres",
        password="postgres",
    )
    conn.autocommit = False
    cur = conn.cursor()

    # Ensure extension and table
    cur.execute("CREATE EXTENSION IF NOT EXISTS postgis;")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS dim_cartera_clientes (
            cuit            TEXT PRIMARY KEY,
            nombre_razon_social TEXT NOT NULL,
            rubro           TEXT,
            hectareas_totales NUMERIC(10,2),
            crop            TEXT CHECK (crop IN ('soja','maíz','trigo')),
            geometry        geometry(Polygon, 4326),
            created_at      TIMESTAMPTZ DEFAULT NOW()
        );
    """)
    conn.commit()

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cuit = row["cuit"]
            nombre = row["nombre_razon_social"]
            rubro = row.get("rubro", "")
            hectareas = float(row.get("hectareas_totales", 0) or 0)
            crop = row.get("crop", "soja")
            geom = parse_geom(row["bbox_geom"])

            cur.execute(
                """INSERT INTO dim_cartera_clientes
                   (cuit, nombre_razon_social, rubro, hectareas_totales, crop, geometry)
                   VALUES (%s, %s, %s, %s, %s, ST_GeomFromGeoJSON(%s))
                   ON CONFLICT (cuit) DO UPDATE
                   SET nombre_razon_social=EXCLUDED.nombre_razon_social,
                       rubro=EXCLUDED.rubro,
                       hectareas_totales=EXCLUDED.hectareas_totales,
                       crop=EXCLUDED.crop,
                       geometry=EXCLUDED.geometry,
                       created_at=NOW();""",
                (cuit, nombre, rubro, hectareas, crop, json.dumps(geom)),
            )
    conn.commit()
    cur.close()
    conn.close()
    print(f"Loaded {csv_path} into dim_cartera_clientes")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python load_cartera.py <path_to_seed_csv>")
        sys.exit(1)
    main(sys.argv[1])