import psycopg2
import os
from dotenv import load_dotenv
import pandas as pd
from psycopg2 import sql
import glob
import re
import json
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()
# path = os.getenv("DATA_PATH")
from backend.services.logger_setup import setup_logging
logger = setup_logging()

# Creating new database
def createNewDB():
    # connecting with the adminDB to create new db since Postgre doesnt allow connecting to non existing DB
    conn = psycopg2.connect(
            dbname=os.getenv("PGADMIN_DB"),
            user = os.getenv("PGUSER"),
            password = os.getenv("PGPASSWORD"),
            host = os.getenv("PGHOST"),
            port = os.getenv("PGPORT")
        )
    conn.autocommit = True
    cursor = conn.cursor()
    new_db_name = os.getenv("PGDATABASE")
    cursor.execute(f"SELECT 1 FROM pg_database WHERE datname = '{new_db_name}'")
    exists = cursor.fetchone()

    if not exists:
        cursor.execute(f"CREATE DATABASE {new_db_name}")
        print(f"Database '{new_db_name}' created.")
    else:
        print(f"Database '{new_db_name}' already exists.")

    cursor.close()
    conn.close()
    
def get_connection():
    # USER = os.getenv("user")
    # PASSWORD = os.getenv("password")
    # HOST = os.getenv("host")
    # PORT = os.getenv("port")
    # DBNAME = os.getenv("dbname")
    return psycopg2.connect(
        # database= DBNAME,
        # user = USER,
        # password = PASSWORD,
        # host = HOST,
        # port = PORT      
        database=os.getenv("PGDATABASE"),
        user = os.getenv("PGUSER"),
        password = os.getenv("PGPASSWORD"),
        host = os.getenv("PGHOST"),
        port = os.getenv("PGPORT")   
    )

def infer_sql_type(dtype,series=None):
    if pd.api.types.is_integer_dtype(dtype):
        if series is not None and series.max() > 2_147_483_647:
            return "BIGINT"
        return "INTEGER"
    elif pd.api.types.is_float_dtype(dtype):
        return "FLOAT"
    elif pd.api.types.is_datetime64_any_dtype(dtype):
        return "TIMESTAMP"
    else:
        return "TEXT"
     
def create_table(cursor,table_name,df):
    cols = []
    df = df.where(pd.notnull(df), None)  # ensure NaT/NaN won't break SQL inserts
    unique_col = None  # ensure it's defined

    # build safe column names + types
    safe_cols = []
    for col in df.columns:
        sql_type = infer_sql_type(df[col], df[col])
        col_safe = col.strip().lower().replace(" ", "_")
        col_safe = re.sub(r'^com\.samsung\.s?health\.', '', col_safe).replace(".", "_")
        safe_cols.append((col, col_safe, sql_type))
        if col_safe.endswith("datauuid"):
            unique_col = col_safe

    # construct CREATE TABLE statement using safe names
    col_defs = [f"{sql.SQL('%s').as_string(cursor).strip()}" for _ in safe_cols]  # placeholder, replaced below
    # build readable col string
    col_parts = [f"{c_safe} {c_type}" for (_, c_safe, c_type) in safe_cols]

    if unique_col:
        col_parts.append(f"UNIQUE ({unique_col})")

    col_string = ", ".join(col_parts)
    # Use identifier for table name
    cursor.execute(sql.SQL(f"CREATE TABLE IF NOT EXISTS {sql.Identifier(table_name).as_string(cursor)} ({col_string});"))
    return unique_col

def insert_data(cursor,table_name,df,uniquekey):
    # normalize cols
    cols = []
    for col in df.columns:
        col_safe = col.strip().lower().replace(" ", "_")
        # Remove leading com.samsung.health.* (any depth)
        col_safe = re.sub(r'^com\.samsung\.s?health\.', '', col_safe)

        # Remove leading com.samsung.shealth.* (any depth)
        # col_safe = re.sub(r'^com\.samsung\.shealth\.', '', col_safe)

        # Replace any leftover dots
        col_safe = col_safe.replace(".", "_")
        cols.append(col_safe)        
        print(table_name,':',col_safe)    

    df = df.where(pd.notnull(df), None)
    placeholders = ", ".join(["%s"] * len(cols))
    col_list = ", ".join(cols)

    if uniquekey:
        insert_query = sql.SQL(f"INSERT INTO {sql.Identifier(table_name).as_string(cursor)} ({col_list}) VALUES ({placeholders}) ON CONFLICT ({sql.Identifier(uniquekey).as_string(cursor)}) DO NOTHING;")
    else:
        insert_query = sql.SQL(f"INSERT INTO {sql.Identifier(table_name).as_string(cursor)} ({col_list}) VALUES ({placeholders});")

    for row in df.itertuples(index=False, name=None):
        cursor.execute(insert_query, row)

# clean csv by removing railing commas and metadata
def clean_samsung_csv(path):
    from io import StringIO
    cleaned_lines = []
    with open(path, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            if i == 0:
                continue  # Skip metadata
            line = line.rstrip('\n').rstrip(',')  # Clean trailing comma
            cleaned_lines.append(line)
    return pd.read_csv(StringIO('\n'.join(cleaned_lines)))

# removing suffixes and timestamps from the csv filenames
def clean_tbl_name(table_name):
    return re.sub(r'^com\.samsung\.s?health\.', '', re.sub(r'\.\d{14}$', '', table_name)).replace(".", "_")

def parse_datetime_custom(val):
    if pd.isnull(val):
        return pd.NaT
    
    val = str(val).strip()
    datetime_formats = [
        "%d-%m-%Y %I:%M:%S %p", # 17-07-2025 01:17:15 PM
        "%Y-%m-%d %H:%M:%S.%f",  #2025-07-17 01:17:15.715
        "%Y-%m-%d %H:%M:%S",   # fallback: 2025-07-17 01:17:15
    ]

    for fmt in datetime_formats:
        try:
            # Try parsing as datetime string
            return datetime.strptime(val,fmt)
        except Exception:
            continue

    try:
        # Try parsing as integer timestamp (in seconds)
        if val.isdigit():
            return pd.to_datetime(int(val), unit='s')
    except Exception as e:
        pass

    # returning val as string as fallback
    return val

def run_etl(data_folder,conn):
    cursor = conn.cursor()
    csv_files = glob.glob(os.path.join(data_folder,"*.csv"))
    tableNamesList = []

    for file_path in csv_files:
        try:
            table_name = os.path.splitext(os.path.basename(file_path))[0].lower()
            cleaned_tbl_name = clean_tbl_name(table_name)
            tableNamesList.append(cleaned_tbl_name)
            df = clean_samsung_csv(file_path)

            # parse and sanitize date/offset columns (existing code) ...
            for col in df.columns:
                col_lower = col.lower()
                if 'offset' in col_lower:
                    df[col] = df[col].astype(str)
                elif 'time' in col_lower or 'date' in col_lower:
                    def safe_parse(val):
                        try:
                            if isinstance(val, str) and len(val.strip()) < 40:
                                return parse_datetime_custom(val)
                        except Exception as e:
                            print(f"[DEBUG] Exception during safe parse: {val} -> {e}")
                        return val
                    df[col] = df[col].apply(safe_parse)

            uniqueKey = create_table(cursor,cleaned_tbl_name,df)

            try:
                # attempt bulk insert
                insert_data(cursor, cleaned_tbl_name, df, uniqueKey)
                conn.commit()   # commit per-file to avoid huge single transaction
                print(f"[INSERTED]: Table '{cleaned_tbl_name}' inserted successfully.")
            except Exception as insert_err:
                conn.rollback()
                print(f"[ERROR] Bulk insert failed for {cleaned_tbl_name}: {insert_err}")
                print("[INFO] Attempting row-by-row insert to find problem row...")

                # row-by-row insert with commit in chunks
                rows = list(df.itertuples(index=False, name=None))
                batch_size = 500
                for i in range(0, len(rows), batch_size):
                    batch = rows[i:i+batch_size]
                    try:
                        # prepare a small df for batch insertion
                        cols_df = df.iloc[:len(batch)].copy()
                        # execute row inserts for the batch
                        for row in batch:
                            cursor.execute(
                                sql.SQL(f"INSERT INTO {sql.Identifier(cleaned_tbl_name).as_string(cursor)} ({', '.join([c.strip().lower().replace(' ','_') for c in df.columns])}) VALUES ({', '.join(['%s']*len(df.columns))}) ON CONFLICT ({sql.Identifier(uniqueKey).as_string(cursor)}) DO NOTHING;") if uniqueKey else
                                sql.SQL(f"INSERT INTO {sql.Identifier(cleaned_tbl_name).as_string(cursor)} ({', '.join([c.strip().lower().replace(' ','_') for c in df.columns])}) VALUES ({', '.join(['%s']*len(df.columns))});"),
                                row
                            )
                        conn.commit()
                    except Exception as row_err:
                        conn.rollback()
                        print(f"[ ERROR] Failed in batch starting row {i+1}: {row_err}")
                        # optionally continue next batch or raise
                        raise row_err

        except Exception as e:
            print(f"Error processing {file_path}: {e}")
            conn.rollback()
    # end for files
    cursor.close()
    with open("database/tableNamesList.json","w") as f:
        json.dump(tableNamesList,f)
    print("[SAVED]: Names of tables uploaded/updated in this session saved in tableNamesList.json")
