import os
import sys
import logging
from dotenv import load_dotenv

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

# ---------------------- PATH SETUP -------------------------- #
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)
sys.path.append(PARENT_DIR)

# ---------------------- IMPORTS ----------------------------- #
from backend.services.datasetFiltering import savebackups, findnewfiles
from backend.services.datasetExploration import save_feat
from createDB import run_etl
from database import getEntryCount

# ---------------------- CONFIG ------------------------------ #
ENV_PATH = ".env"
ENV_VARIABLE = "DATA_PATH"
DATA_ROOT_FOLDER = r"data\raw\Samsung Health"
FILENAMES_JSON = r"backend\services\filenames.json"
TABLE_NAMES_JSON = r"database\tableNamesList.json"
BACKUP_PATH = os.getenv("BACKUP_PATH")

# ---------------------- FUNCTIONS --------------------------- #
def update_env_with_latest_folder(env_path: str, variable: str, target_folder: str):
    """
    Update .env file with the path of the latest folder in the target directory.
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

        # latest_folder = max(all_folders, key=os.path.getctime)
        ## hardcoding a latest file incase a file's eltl flow was skipped
        latest_folder = "data\raw\Samsung Health\samsunghealth_shaikhmubashir197_20250810194089"
        escaped_path = latest_folder.replace("\\", "\\\\")

        updated_lines = []
        variable_found = False

        if os.path.exists(env_path):
            with open(env_path, 'r') as file:
                for line in file:
                    if line.strip().startswith(variable + " ="):
                        updated_lines.append(f'{variable} = "{escaped_path}"\n')
                        variable_found = True
                    else:
                        updated_lines.append(line)

        if not variable_found:
            updated_lines.append(f'{variable} = "{escaped_path}"\n')

        with open(env_path, "w") as file:
            file.writelines(updated_lines)

        logging.info("Updated %s with latest folder: %s", variable, latest_folder)
    except Exception as e:
        logging.exception("Failed to update .env with latest folder path")

def run_flow():
    """
    Orchestrates the entire ETL and processing flow.
    """
    try:
        logging.info("Starting ETL flow...")

        update_env_with_latest_folder(ENV_PATH, ENV_VARIABLE, DATA_ROOT_FOLDER)

        data_path = os.getenv("DATA_PATH")
        if not data_path:
            logging.error("DATA_PATH not set in .env")
            return

        savebackups(BACKUP_PATH)
        findnewfiles(FILENAMES_JSON)
        save_feat(data_path)
        run_etl(data_path)
        getEntryCount(TABLE_NAMES_JSON)

        logging.info("Data pipeline completed successfully.")

    except Exception as e:
        logging.exception("ETL flow failed with an exception.")

# ---------------------- MAIN ------------------------------- #
if __name__ == "__main__":
    run_flow()