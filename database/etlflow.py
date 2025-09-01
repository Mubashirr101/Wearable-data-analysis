# ---------------------- IMPORTING LIBS ---------------------#
import os
import sys
import logging
from dotenv import load_dotenv
import psycopg2
# ---------------------- PATH SETUP -------------------------- #
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)
sys.path.append(PARENT_DIR)

# ---------------------- IMPORTING MODULES ----------------------------- #
from backend.services.datasetFiltering import savebackups, findnewfiles
from backend.services.datasetExploration import save_feat
from connectNsyncDB import run_etl
from dbCount import getEntryCount
from jsonUploads import run_json_sync
# ---------------------- LOGGING SETUP ----------------------- #
LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "etl.log")

os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    filename=LOG_FILE,
    filemode="a",
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.INFO
)

# Also log to console
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logging.getLogger().addHandler(console_handler)

# ---------------------- LOAD ENV ---------------------------- #
load_dotenv()



# ---------------------- CONFIG ------------------------------ #
ENV_PATH = ".env"
ENV_VARIABLE_DATA = "DATA_PATH"
ENV_VARIABLE_JSON = "JSON_PATH"
DATA_ROOT_FOLDER = r"data\raw\Samsung Health"
FILENAMES_JSON = r"backend\services\filenames.json"
TABLE_NAMES_JSON = r"database\tableNamesList.json"
BACKUP_PATH = os.getenv("BACKUP_PATH")

# ---------------------- FUNCTIONS --------------------------- #

def get_connection(type):
    try:
        if type == 'local':
            print(type)
            return psycopg2.connect(
                database=os.getenv("PGDATABASE"),
                user = os.getenv("PGUSER"),
                password = os.getenv("PGPASSWORD"),
                host = os.getenv("PGHOST"),
                port = os.getenv("PGPORT")   
            )
        elif type == 'supabase':
            print(type)
            return psycopg2.connect(
                database=os.getenv("dbname"),
                user = os.getenv("user"),
                password = os.getenv("password"),
                host = os.getenv("host"),
                port = os.getenv("post")  

            )
    except Exception as e:
        logging.exception("Could not make DB connection",e)


def update_env_with_latest_folder(env_path: str, variable1: str,variable2: str, target_folder: str):
    """
    Update .env file with the path of the latest folder of csv and json in the target directory.
    """
    try:
        all_folders = [
            os.path.join(target_folder, item)
            for item in os.listdir(target_folder)
            if os.path.isdir(os.path.join(target_folder, item))
        ]

        if not all_folders:
            logging.error("No folders found in the target directory: %s", target_folder)
            return

        latest_folder = max(all_folders, key=os.path.getctime)
        ## hardcoding a latest file incase a file's eltl flow was skipped
        # latest_folder = r"data\raw\Samsung Health\samsunghealth_shaikhmubashir197_20250818193149"
        escaped_path = latest_folder.replace("\\", "\\\\")

        updated_lines = []
        variable1found = False
        variable2found = False

        if os.path.exists(env_path):
            with open(env_path, 'r') as file:
                for line in file:
                    if line.strip().startswith(variable1 + " ="):
                        updated_lines.append(f'{variable1} = "{escaped_path}"\n')
                        variable1found = True
                    elif line.strip().startswith(variable2 + " ="):
                        updated_lines.append(f'{variable2} = "{escaped_path}\\\\jsons"\n')
                        variable2found = True
                    else:
                        updated_lines.append(line)

        if not variable1found:
            updated_lines.append(f'{variable1} = "{escaped_path}"\n')
        if not variable2found:
            print("json not found,printing new")
            updated_lines.append(f'{variable2} = "{escaped_path}\\\\jsons"\n')

        with open(env_path, "w") as file:
            file.writelines(updated_lines)

        logging.info("Updated %s and %s with latest folder: %s", variable1,variable2, latest_folder)
    except Exception as e:
        logging.exception("Failed to update .env with latest folder path")


def run_flow():
    """
    Orchestrates the entire ETL and processing flow.
    """
    try:
        logging.info("Starting ETL flow...")
        update_env_with_latest_folder(ENV_PATH,ENV_VARIABLE_DATA,ENV_VARIABLE_JSON, DATA_ROOT_FOLDER)
        load_dotenv(override=True)
        data_path = os.getenv("DATA_PATH")
        json_path = os.getenv("JSON_PATH")
        if not data_path:
            logging.error("DATA_PATH not set in .env")
            return
        if not json_path:
            logging.error("JSON_PATH not set in .env")
            return
        ## connect the DB, 2 options -> local OR supabase
        conn = get_connection("supabase")        
        ## run scripts
        savebackups(BACKUP_PATH)
        findnewfiles(FILENAMES_JSON)
        save_feat(data_path)
        run_etl(data_path,conn)
        run_json_sync(json_path)
        getEntryCount(TABLE_NAMES_JSON,conn)

        # closing the connection of DB
        conn.close()
        logging.info("Data pipeline completed successfully.")

    except Exception as e:
        logging.exception("ETL flow failed with an exception.")

# ---------------------- MAIN ------------------------------- #
if __name__ == "__main__":
    run_flow()