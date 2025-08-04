import sys, os
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
## add parent dir to sys.path
sys.path.append(parent_dir)
from backend.services.datasetFiltering import savebackups, findnewfiles
from backend.services.datasetExploration import save_feat
from createDB import run_etl
from database import getEntryCount
from dotenv import load_dotenv
load_dotenv()

def updateDataPath(env_path,env_variable,target_folder):
     """
      Finds the newest file in the target folder and updates the .env file with its path.

      Parameters:
        env_path (str): Path to the .env file.
        env_variable (str): Name of the environment variable to update.
        target_folder (str): Directory to search for the latest file.
     """
     ## 1 -  Getting all the subfodlers in the target folder     
     all_folders = []
     for item in os.listdir(target_folder):
          item_path = os.path.join(target_folder,item)
          if os.path.isdir(item_path):
               all_folders.append(item_path)
     
     ## 2 - finding the latest folder
     if len(all_folders) == 0:
          print("[ERROR][updatingENV]: No folders found the target dir")
          return
     latest_folder = all_folders[0]
     for folder_path in all_folders:
          if os.path.getctime(folder_path) > os.path.getctime(latest_folder):
               latest_folder = folder_path
     
     ## 3 - reading the existing env file
     updated_lines = []
     variable_found = False

     if os.path.exists(env_path):
          with open(env_path,'r') as file:
               for line in file:
                    if line.startswith(env_variable + " = "):
                         escaped_path = str(latest_folder).replace("\\", "\\\\")                                                 
                         updated_lines.append(env_variable + ' = "' + escaped_path + '"\n')
                         variable_found = True
                    else:
                         updated_lines.append(line)

     ## if var not found, make it 
     if not variable_found:
        escaped_path = str(latest_folder).replace("\\", "\\\\")                                                 
        updated_lines.append(env_variable + ' = "' + escaped_path + '"\n')

     ## write the updated line back to the env file
     with open(env_path, "w") as file:
        for line in updated_lines:
             file.write(line)

     print(f"[ENV UPDATED] Latest folder path : {latest_folder}")
          

def runFlow():
    main_folder_path = os.getenv("BACKUP_PATH")
    filenamesJSON = r"backend\services\filenames.json"
    tableNamesListJSON = r"database\tableNamesList.json"
    updateDataPath(env_path=r".env",env_variable="DATA_PATH",target_folder=r"data\raw\Samsung Health")
    dataPath = os.getenv("DATA_PATH")
    savebackups(main_folder_path)
    findnewfiles(filenamesJSON)
    save_feat(dataPath)
    run_etl(dataPath)
    getEntryCount(tableNamesListJSON)

runFlow()