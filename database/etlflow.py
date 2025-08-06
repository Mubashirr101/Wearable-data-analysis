import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ---------------------- PATH SETUP ---------------------- #
# Add parent directory to sys.path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)
sys.path.append(PARENT_DIR)

# ---------------------- IMPORTS ------------------------- #
from backend.services.datasetFiltering import savebackups, findnewfiles
from backend.services.datasetExploration import save_feat
from createDB import run_etl
from database import getEntryCount

# ---------------------- CONFIG -------------------------- #
ENV_PATH = ".env"
ENV_VARIABLE = "DATA_PATH"
DATA_ROOT_FOLDER = r"data\raw\Samsung Health"
FILENAMES_JSON = r"backend\services\filenames.json"
TABLE_NAMES_JSON = r"database\tableNamesList.json"
BACKUP_PATH = os.getenv("BACKUP_PATH")

# ---------------------- FUNCTIONS ----------------------- #
def update_env_with_latest_folder(env_path: str, variable: str, target_folder: str):
    """
    Update .env file with the path of the latest folder in the target directory.
    """
    all_folders = [
        os.path.join(target_folder, item)
        for item in os.listdir(target_folder)
        if os.path.isdir(os.path.join(target_folder, item))
    ]

    if not all_folders:
        print("[ERROR][update_env_with_latest_folder]: No folders found in the target directory.")
        return

    latest_folder = max(all_folders, key=os.path.getctime)
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

    print(f"[ENV UPDATED] → {variable} = {latest_folder}")

def run_flow():
    """
    Orchestrates the entire ETL and processing flow.
    """
    update_env_with_latest_folder(ENV_PATH, ENV_VARIABLE, DATA_ROOT_FOLDER)

    data_path = os.getenv("DATA_PATH")
    if not data_path:
        print("[ERROR][run_flow]: DATA_PATH not set in .env")
        return

    print("[INFO] Starting data processing pipeline...")
    savebackups(BACKUP_PATH)
    findnewfiles(FILENAMES_JSON)
    save_feat(data_path)
    run_etl(data_path)
    getEntryCount(TABLE_NAMES_JSON)
    print("[INFO] Data pipeline completed successfully.")

# ---------------------- MAIN ---------------------------- #
if __name__ == "__main__":
    run_flow()
