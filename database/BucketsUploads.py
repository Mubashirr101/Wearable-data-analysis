from supabase import create_client, Client
import os
from dotenv import load_dotenv
from storage3.exceptions import StorageApiError


def run_json_sync(json_dir):
    load_dotenv()
    url = os.getenv("url")
    key = os.getenv("key")
    supabase: Client = create_client(url, key)
    bucket_name = "json-bucket"
    for root, _, files in os.walk(json_dir):
        for file in files:
            if file.endswith(".json"):
                # skip lock file
                if file == "sync.ffs_lock":
                    continue
                local_path = os.path.join(root, file)
                relative_path = os.path.relpath(local_path, json_dir)
                # ensuring forward slashed for supabase
                relative_path = relative_path.replace("\\", "/")
                with open(local_path, "rb") as f:
                    try:
                        # update to replace existing file
                        supabase.storage.from_(bucket_name).update(relative_path, f)
                        print(f"Updated {relative_path}")
                    except Exception as e:
                        # if file doest exist -> upload as new
                        with open(local_path, "rb") as f2:
                            supabase.storage.from_(bucket_name).upload(
                                relative_path, f2
                            )
                            print(f"Uploaded {relative_path}")
    print("[SAVED]: Updated JSON files in Supabase Bucket")


def run_healthsync_sync(healthsync_dir):
    load_dotenv()
    url = os.getenv("url")
    key = os.getenv("key")
    supabase: Client = create_client(url, key)
    bucket_name = "healthsync-bucket"
    for root, _, files in os.walk(healthsync_dir):
        for file in files:
            # skip lock file
            if file == "sync.ffs_lock":
                continue
            local_path = os.path.join(root, file)
            relative_path = os.path.relpath(local_path, healthsync_dir)
            # ensuring forward slashed for supabase
            relative_path = relative_path.replace("\\", "/")
            with open(local_path, "rb") as f:
                try:
                    # update to replace existing file
                    supabase.storage.from_(bucket_name).update(relative_path, f)
                    print(f"Updated {relative_path}")
                except StorageApiError as e:
                    # If file does not exist, upload as new
                    if e.status_code == 400:  # Bad Request, probably file not found
                        with open(local_path, "rb") as f2:
                            try:
                                supabase.storage.from_(bucket_name).upload(
                                    relative_path, f2
                                )
                                print(f"Uploaded {relative_path}")
                            except StorageApiError as e2:
                                if e2.status_code == 409:
                                    print(f"Skipped (already exists): {relative_path}")
                                else:
                                    print(f"Upload error {relative_path}: {e2}")
                    elif e.status_code == 409:
                        print(f"Skipped (already exists): {relative_path}")
                    else:
                        print(f"Update error {relative_path}: {e}")
    print("[SAVED]: Updated HealthSync files in Supabase Bucket")



