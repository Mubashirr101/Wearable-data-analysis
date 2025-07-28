import psycopg2
import os
from dotenv import load_dotenv
import pandas as pd
from psycopg2 import sql
import json
load_dotenv()

def get_connection():
    return psycopg2.connect(
        database=os.getenv("PGDATABASE"),
        user = os.getenv("PGUSER"),
        password = os.getenv("PGPASSWORD"),
        host = os.getenv("PGHOST"),
        port = os.getenv("PGPORT")        
    )


def getEntryCount(tablename):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(f"SELECT COUNT(*)FROM {tablename};")
    count = cursor.fetchone()[0]
    print(f"Table: {tablename} has {count} rows.")

with open("database/tableNamesList.json","r") as f:
    tableNamesList = json.load(f)
for tables in sorted(tableNamesList):
    getEntryCount(tables)
