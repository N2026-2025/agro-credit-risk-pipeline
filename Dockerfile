# Custom Airflow image with the pipeline dependencies (polars, rasterio, geopandas, pystac-client, minio, psycopg2).
FROM apache/airflow:2.9.1-python3.10

USER airflow

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

WORKDIR /opt/airflow