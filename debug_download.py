import csv
import urllib.request
import re
import os
import html

input_file = 'seoul_youth_allowance_others.csv'
attachment_dir = 'attachments'
headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/35.0.1916.47 Safari/537.36'
}

# Regex patterns
original_link_pattern = re.compile(r'<a[^>]+href="([^"]+)"[^>]*class="[^"]*btn-original[^"]*"[^>]*>.*?원문.*?</a>', re.IGNORECASE | re.DOTALL)

with open(input_file, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    first_row = next(reader)

url = first_row['URL']
print(f"URL: {url}")

req_page = urllib.request.Request(url, headers=headers)
with urllib.request.urlopen(req_page) as response:
    content = response.read().decode('utf-8')
    m_link = original_link_pattern.search(content)
    if m_link:
        raw_href = m_link.group(1)
        print(f"Raw Href: {raw_href}")
        download_href = html.unescape(raw_href)
        print(f"Unescaped Href: {download_href}")
        
        if download_href.startswith('/'):
            download_url = "https://opengov.seoul.go.kr" + download_href
        else:
            download_url = download_href
            
        print(f"Download URL: {download_url}")
        
        req_dl = urllib.request.Request(download_url, headers=headers)
        with urllib.request.urlopen(req_dl) as dl_response:
            data = dl_response.read()
            print(f"Downloaded bytes: {len(data)}")
            print(f"First 100 chars: {data[:100]}")
