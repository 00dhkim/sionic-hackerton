import urllib.request

url = "https://opengov.seoul.go.kr/og/com/download.php?nid=35027731&dtype=basic&rid=F0000116342709&fid=&uri=%2Ffiles%2Fdcdata%2F100001%2F20251217%2FF0000116342709.hwpx"
output = "test_python_agent.hwpx"

req = urllib.request.Request(
    url, 
    data=None, 
    headers={
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/35.0.1916.47 Safari/537.36'
    }
)

try:
    with urllib.request.urlopen(req) as response:
        with open(output, 'wb') as f:
            f.write(response.read())
    print("Download finished")
except Exception as e:
    print(e)
