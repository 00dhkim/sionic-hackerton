import os
import json
import time
import subprocess
import re

# Configuration
API_URL_UPLOAD = "https://storm-apis.sionic.im/parse-router/api/v2/parse/by-file"
API_URL_JOB = "https://storm-apis.sionic.im/parse-router/api/v2/parse/job/{}"
TOKEN = "basi_01KCK7NGJF4DPYY6W8BZ954JHE"
TARGET_DIRS = ["attachments", "attachments_complaints"]

def upload_file(file_path):
    """Uploads file using curl and returns jobId"""
    cmd = [
        "curl", "--location", "--request", "POST", API_URL_UPLOAD,
        "--header", f"Authorization: Bearer {TOKEN}",
        "--form", f"file=@{file_path}",
        "--form", "language=\"ko\"",
        "--form", "deleteOriginFile=\"true\"",
        "-s" # Silent mode
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        response_data = json.loads(result.stdout)
        return response_data.get("jobId")
    except subprocess.CalledProcessError as e:
        print(f"Error uploading {file_path}: {e}")
        print(f"Stdout: {e.stdout}")
        print(f"Stderr: {e.stderr}")
        return None
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON from upload response for {file_path}: {e}")
        print(f"Raw output: {result.stdout}")
        return None

def check_job_status(job_id):
    """Checks job status using curl"""
    url = API_URL_JOB.format(job_id)
    cmd = [
        "curl", "--location", "--request", "GET", url,
        "--header", f"Authorization: Bearer {TOKEN}",
        "-s"
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return json.loads(result.stdout)
    except Exception as e:
        print(f"Error checking job {job_id}: {e}")
        return None

def process_directory(directory):
    print(f"Processing directory: {directory}")
    if not os.path.exists(directory):
        print(f"Directory not found: {directory}")
        return

    files = [f for f in os.listdir(directory) if "_original" in f and not f.endswith(".md")]
    files.sort() # Sort for consistent order
    
    total_files = len(files)
    print(f"Found {total_files} files to process.")

    for idx, filename in enumerate(files):
        file_path = os.path.join(directory, filename)
        
        # Determine output filename
        # Expected format: {id}_original.{ext} -> {id}_parsed.md
        match = re.match(r"(\d+)_original", filename)
        if match:
            file_id = match.group(1)
            output_filename = f"{file_id}_parsed.md"
        else:
            # Fallback if regex doesn't match (though my previous script named them this way)
            base_name = os.path.splitext(filename)[0]
            output_filename = f"{base_name}_parsed.md"
            
        output_path = os.path.join(directory, output_filename)
        
        if os.path.exists(output_path):
            print(f"[{idx+1}/{total_files}] Skipping {filename} (Already parsed)")
            continue
            
        print(f"[{idx+1}/{total_files}] Processing {filename}...")
        
        # 1. Upload
        job_id = upload_file(file_path)
        if not job_id:
            print("  Failed to get jobId. Skipping.")
            continue
            
        print(f"  Job ID: {job_id}. Waiting for completion...")
        
        # 2. Poll Status
        retries = 0
        max_retries = 60 # 60 * 2s = 120s timeout
        
        while retries < max_retries:
            status_data = check_job_status(job_id)
            
            if not status_data:
                time.sleep(2)
                retries += 1
                continue
                
            state = status_data.get("state")
            
            if state == "COMPLETED":
                # 3. Save Result
                pages = status_data.get("pages", [])
                full_content = ""
                for page in pages:
                    full_content += page.get("content", "") + "\n\n"
                
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(full_content)
                
                print(f"  Saved parsed content to {output_filename}")
                break
            elif state == "FAILED":
                print(f"  Job failed: {status_data.get('errorMessage')}")
                break
            elif state in ["REQUESTED", "PROCESSING", "PENDING"]:
                # print(f"  State: {state}...") # Verbose
                pass
            else:
                print(f"  Unknown state: {state}")
            
            time.sleep(2)
            retries += 1
        
        if retries >= max_retries:
            print("  Timed out waiting for job completion.")

if __name__ == "__main__":
    for d in TARGET_DIRS:
        process_directory(d)
