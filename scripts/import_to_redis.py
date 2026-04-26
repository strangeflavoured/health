"""Import Apple Health Export Data to Redis."""

from src.connection import redis_connect
from src.importer import HealthDataImporter

if __name__ == "__main__":
    r = redis_connect(tls=True)
    if r.ping():
        HealthDataImporter(connection=r).etl(write_feather=True)
