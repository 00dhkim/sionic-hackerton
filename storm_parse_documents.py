import os
import json
import time
import subprocess
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configuration
API_URL_UPLOAD = "https://storm-apis.sionic.im/parse-router/api/v2/parse/by-file"
API_URL_JOB = "https://storm-apis.sionic.im/parse-router/api/v2/parse/job/{}"
TOKEN = "basi_01KCK7NGJF4DPYY6W8BZ954JHE"
TARGET_DIRS = ["attachments", "attachments_complaints"]
ERROR_LOG_FILE = "parse_errors.log"
MAX_WORKERS = 20

def log_error(file_id, filename, message):
    with open(ERROR_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - ID: {file_id} - File: {filename} - {message}\n")

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
        return None
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON from upload response for {file_path}: {e}")
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

def process_file(directory, filename):
    file_path = os.path.join(directory, filename)
    
    # Determine output filename and ID
    match = re.match(r"(\d+)_original", filename)
    if match:
        file_id = match.group(1)
        output_filename = f"{file_id}_parsed.md"
    else:
        file_id = "unknown"
        base_name = os.path.splitext(filename)[0]
        output_filename = f"{base_name}_parsed.md"
        
    output_path = os.path.join(directory, output_filename)
    
    # Skip if already parsed
    if os.path.exists(output_path):
        return None # Return None to indicate skip
        
    print(f"Processing ID {file_id}: {filename}...")
    
    # 1. Upload
    job_id = upload_file(file_path)
    if not job_id:
        log_error(file_id, filename, "Failed to get jobId (Upload failed)")
        return f"ID {file_id}: Upload failed"
        
    # 2. Poll Status
    retries = 0
    max_retries = 24 # 24 * 5s = 120s timeout
    
    while retries < max_retries:
        status_data = check_job_status(job_id)
        
        if not status_data:
            time.sleep(5)
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
            
            return f"ID {file_id}: Completed"
            
        elif state in ["FAILED", "ERRORED"]:
            msg = status_data.get('errorMessage', 'Unknown error')
            log_error(file_id, filename, f"Job state {state}: {msg}")
            return f"ID {file_id}: Failed ({state})"
            
        elif state in ["REQUESTED", "PROCESSING", "PENDING", "ACCEPTED"]:
            # Valid intermediate states
            pass
        else:
            log_error(file_id, filename, f"Unknown state: {state}")
        
        time.sleep(5)
        retries += 1
    
    log_error(file_id, filename, "Timed out")
    return f"ID {file_id}: Timed out"

def process_directory(directory):
    print(f"Scanning directory: {directory}")
    if not os.path.exists(directory):
        print(f"Directory not found: {directory}")
        return

    files = [f for f in os.listdir(directory) if "_original" in f and not f.endswith(".md")]
    files.sort() 
    
    # Filter unparsed
    unparsed_files = []
    for f in files:
        match = re.match(r"(\d+)_original", f)
        if match:
            out_name = f"{match.group(1)}_parsed.md"
        else:
            out_name = f"{os.path.splitext(f)[0]}_parsed.md"
        
        if not os.path.exists(os.path.join(directory, out_name)):
            unparsed_files.append(f)
            
    total_files = len(unparsed_files)
    print(f"Found {total_files} unparsed files in {directory}.")
    
    if total_files == 0:
        return

    failed_ids = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_file = {executor.submit(process_file, directory, f): f for f in unparsed_files}
        
        for future in as_completed(future_to_file):
            f = future_to_file[future]
            try:
                result = future.result()
                if result:
                    print(result)
                    if "Failed" in result or "Timed out" in result:
                         # Extract ID for summary
                         match = re.match(r"(\d+)_original", f)
                         if match:
                             failed_ids.append(match.group(1))
            except Exception as exc:
                print(f"{f} generated an exception: {exc}")
                log_error("unknown", f, f"Exception: {exc}")

    if failed_ids:
        print(f"Failed Document IDs in {directory}: {', '.join(failed_ids)}")

if __name__ == "__main__":
    print(f"Starting parallel processing with {MAX_WORKERS} workers...")
    for d in TARGET_DIRS:
        process_directory(d)