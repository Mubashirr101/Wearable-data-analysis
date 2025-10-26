import pandas as pd
import numpy as np
import os
import re
import json
from dotenv import load_dotenv
load_dotenv()

# Filtering and Understanding how the 
# data files are stored and updated in the SH app export


# Saving the list of file names from individual backups
# backup folders path
path = os.getenv("BACKUP_PATH")

# Cleaning: Removing dates/timestamp from filenames for normalization and ease of comparing
def remove_timestamp(filename):
    # This regex matches a dot, 14 digits, then .csv at the end
    return re.sub(r'\.\d{14}\.csv$','.csv',filename)

# normalizing file names (making sure all the same files across the backups have same names)
def normalise_filenames(non_normalised_files):
    norm_backup_csv = {}
    for backups in non_normalised_files:
        filelist = []
        for csv in non_normalised_files[backups]:
            filelist.append(remove_timestamp(csv))        
        norm_backup_csv[backups] = filelist
    # Listing total files in norm_backup_csv (norm), it matches the no. of files in backup_files (non norm)
    print("\n============= NORMALISED: No. of CSV files in each Backup: =============\n")
    for i in norm_backup_csv:
        print(f"\t{i}:{len(norm_backup_csv[i])}")
    return norm_backup_csv

# saving names of all the backups and the respective csv files in them in a json file
def savebackups(main_folder_path):
    backup_files = {}
    for backups in os.listdir(main_folder_path):
        backups_path = os.path.join(main_folder_path, backups)
        if os.path.isdir(backups_path):
            filelist =[]
            for file in os.listdir(backups_path):
                if file.lower().endswith('.csv'):
                    filelist.append(file)
            backup_files[backups] = filelist
    # Checking number of files in each backup
    print("\n============= RAW: Number of CSV files in each Backup: =============\n")
    for i in backup_files:
        print(f"\t{i} : {len(backup_files[i])}")

    # normalizing file names (removing timestamps) across the different backup versions
    normalisedFilelist = normalise_filenames(backup_files)
    # adding filenames in json
    with open("backend/services/filenames.json","w") as f:
        json.dump(normalisedFilelist,f,indent=4)
    print ("[SAVED]: Backup Filenames in filenames.json")


# Function to find newly added (UNIQUE) files in normalised file list
def findnewfiles(filenamesPATH):
    with open(filenamesPATH,"r") as f:
        normalised_files = json.load(f)
    seen_files = set()
    indexed_files ={}
    for backups in sorted(normalised_files):
        new_files =[]
        for files in sorted(normalised_files[backups]):
            if files not in seen_files:
                new_files.append(files)
                seen_files.add(files)   
                print(f"[NEW FILE]: {files}")                     
        # per folder index dict
        file_dict = {}
        for index,file in enumerate(new_files,start=1):
            # print(f"    {index}: {file}")
            file_dict[str(index)] = file
        if file_dict:
            indexed_files[backups] = file_dict        
    with open(r"backend\services\newfiles.json","w") as out:
        json.dump(indexed_files,out,indent=4)
    print("[SAVED]: Newly added filenames in newfiles.json")