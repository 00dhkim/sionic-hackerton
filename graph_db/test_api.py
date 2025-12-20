import time
import requests
import subprocess
import sys
import os

def test_server():
    print("--- Starting Server ---")
    # Start server as a subprocess
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "api_server:app", "--port", "8002"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={**os.environ, "PYTHONUNBUFFERED": "1"}
    )

    try:
        # Wait for server to be ready
        print("Waiting for startup...")
        time.sleep(15) # Give it plenty of time
        
        # Health Check
        try:
            print("Checking Health...")
            resp = requests.get("http://localhost:8002/health")
            print(f"Health Check: {resp.status_code} - {resp.json()}")
        except Exception as e:
            print(f"Health Check Failed: {e}")
            
        # Search Query
        print("Sending Query...")
        payload = {"query": "보안 관련 문서를 쓴 사람은?"}
        try:
            resp = requests.post("http://localhost:8002/api/search", json=payload)
            
            if resp.status_code == 200:
                data = resp.json()
                print("\n[SUCCESS] Answer:")
                print(data['answer'])
                print("\n[Sources]:")
                for src in data['sources']:
                    print(f" - {src['title']}")
            else:
                print(f"[ERROR] {resp.status_code}: {resp.text}")
        except Exception as e:
            print(f"Query Request Failed: {e}")

    finally:
        print("\n--- Stopping Server ---")
        process.terminate()
        try:
            outs, errs = process.communicate(timeout=5)
            print("Server Output:")
            print(outs)
            print("Server Errors:")
            print(errs)
        except:
            process.kill()

if __name__ == "__main__":
    test_server()