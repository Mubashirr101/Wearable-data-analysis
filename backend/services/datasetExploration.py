import pandas as pd
import numpy as np
import os
import re
import json
from dotenv import load_dotenv
load_dotenv()

# Exploring Datasets (CSVs) and Understanding their Features
path = os.getenv("DATA_PATH")

# Listing all the Features in the CSVs 
# First removing timestamps from the filenames of CSV files
def remove_date_suffix(filename):
    return re.sub(r'\.\d{14}(?=\.csv)','',filename)

# Func to extract and save features of datasets (CSV files) in dict
def extract_csv_features(folderpath):
    features_summary={}

    for file in sorted(os.listdir(folderpath)):
        if file.endswith(".csv"):
            try:
                # removing timestamp
                cleaned_name = remove_date_suffix(file).replace('.csv','')
                
                with open(os.path.join(folderpath,file), 'r', encoding='utf-8') as f:
                     f.readline() # skipping metadata
                     header_line = f.readline().strip()
                     headers = header_line.split(',')

                features_summary[cleaned_name] = headers
            except Exception as e:
                print(f" Error reading {file}: {e}")
            
    return {"summary":features_summary}
                
# store the features of each csv file in a json file
def save_feat(dataset_path):
    summary_data = extract_csv_features(dataset_path)

    #saving features dict to json file
    with open("backend/services/features.json","w") as f:
        json.dump(summary_data,f,indent=4)

    print("Saved: features.json")


# Converting CSV into df
def cleanNconvert_CSV(path):
    from io import StringIO
    cleaned_lines = []
    with open(path, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            if i == 0:
                continue  # Skip metadata
            line = line.rstrip('\n').rstrip(',')  # Clean trailing comma
            cleaned_lines.append(line)
    return pd.read_csv(StringIO('\n'.join(cleaned_lines)))


######################################################################
## run script to save feature names
# save_feat(path)

## run script to convert a csv into df
# csv_path = os.getenv("CSV_PATH")
# df = cleanNconvert_CSV(csv_path)
# print(f"Dataframe of '{csv_path}'")
# print(df.head())