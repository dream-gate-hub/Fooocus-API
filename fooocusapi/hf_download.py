import os
import shutil
from tqdm import tqdm
from huggingface_hub import login, hf_hub_download, list_repo_files

def format_size(bytes):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes < 1024:
            return f"{bytes:.2f} {unit}"
        bytes /= 1024

def download_repo_files(token, repo_id, download_directory, repo_type="dataset"):
    # Authenticate with Hugging Face if a token is provided
    if token:
        login(token=token)

    # Ensure the download directory exists
    os.makedirs(download_directory, exist_ok=True)

    # Get the list of all files in the repository
    file_list = list_repo_files(repo_id, repo_type=repo_type)

    # Download files with progress bar
    with tqdm(total=len(file_list), unit="file") as pbar:
        for file in file_list:
            try:
                # Download the file
                file_path = hf_hub_download(repo_id, file, repo_type=repo_type)
                destination_path = os.path.join(download_directory, file)
                os.makedirs(os.path.dirname(destination_path), exist_ok=True)
                shutil.move(file_path, destination_path)

                # Get file size
                file_size = os.path.getsize(destination_path)

                # Update progress bar with file size
                pbar.set_postfix({"File Size": format_size(file_size)})
                pbar.update(1)
                print(f"Downloaded {file} to {destination_path}")
            except Exception as e:
                print(f"Error downloading {file}: {e}")
                pbar.update(1)

    print("All files downloaded successfully!")
