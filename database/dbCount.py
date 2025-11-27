import psycopg2
import os
from dotenv import load_dotenv
from datetime import datetime
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

def getEntryCount(tableNamesListPATH,conn):
    with open(tableNamesListPATH,"r") as f:
        tableNamesList = json.load(f)

    try:
        cursor = conn.cursor()
    except Exception as e:
        print(f"[ERROR] DB connection invalid in getEntryCount: {e}")
        try:
            conn = get_connection()
            cursor = conn.cursor()
        except Exception as e2:
            print(f"[ERROR] Could not reconnect: {e2}")
            return

    rowcountDict = {}
    timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    for table in sorted(tableNamesList):
        try:
            cursor.execute(sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(table)))
            count = cursor.fetchone()[0]
            print(f"Table: {table} has {count} rows.")
            rowcountDict[table] = count
        except Exception as e:
            rowcountDict[table] = f"Error: {str(e)}"
    try:
        cursor.close()
    except Exception:
        pass

    # write RowCounts JSON
    filepath = "database/RowCounts.json"
    if os.path.exists(filepath):
        with open(filepath,"r") as f:
            fulldata = json.load(f)
    else:
        fulldata = {}

    fulldata[timestamp] = rowcountDict
    with open("database/RowCounts.json","w") as f:
        json.dump(fulldata,f,indent=4)
    print("[SAVED]: No. of rows in this ETL session in RowCounts.json ")

