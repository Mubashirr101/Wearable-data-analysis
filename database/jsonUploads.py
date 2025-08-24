from supabase import create_client, Client
import os
from dotenv import load_dotenv
load_dotenv()

url = os.getenv("url")
key = os.getenv("key")
supabase: Client = create_client(url,key)
json_dir = os.getenv("JSON_PATH")
bucket_name = "json-bucket"

def run_json_sync(json_dir):
    for root,_,files in os.walk(json_dir):
        for file in files:
            if file.endswith(".json"):
                local_path = os.path.join(root,file)
                relative_path = os.path.relpath(local_path,json_dir)
                # ensuring forward slashed for supabase
                relative_path = relative_path.replace("\\","/")
                with open(local_path,"rb") as f:
                    try:
                        # update to replace existing file
                        supabase.storage.from_(bucket_name).update(relative_path,f)
                        print(f"Updated {relative_path}")
                    except Exception as e:
                        # if file doest exist -> upload as new
                        with open(local_path,"rb") as f2:
                            supabase.storage.from_(bucket_name).upload(relative_path,f2)
                        print(f"Uploaded {relative_path}")


run_json_sync(json_dir)