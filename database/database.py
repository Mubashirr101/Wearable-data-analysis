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

def getEntryCount(tablenames):
    conn = get_connection()
    cursor = conn.cursor()
    rowcountDict = {}
    timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    for table in sorted(tablenames):
        try:
            cursor.execute(sql.SQL("SELECT COUNT(*)FROM {}").format(sql.Identifier(table)))
            count = cursor.fetchone()[0]
            # print(f"Table: {table} has {count} rows.")
            rowcountDict[table] = count
        except Exception as e:
            rowcountDict[table] = f"Error: {str(e)}"
    cursor.close()
    conn.close()

    # reading any saved json file if available
    filepath = "database/RowCounts.json"
    if os.path.exists(filepath):
        with open(filepath,"r") as f:
            fulldata = json.load(f)
    else:
        fulldata = {}

    # Adding new rowcount entry
    fulldata[timestamp] = rowcountDict
    # saving it in json
    with open("database/RowCounts.json","w") as f:
        json.dump(fulldata,f,indent=4)

        

        

with open("database/tableNamesList.json","r") as f:
    tableNamesList = json.load(f)
getEntryCount(tableNamesList)