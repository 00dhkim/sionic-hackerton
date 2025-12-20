import csv
import urllib.request
import urllib.parse
import re
import os
import time
import html
import sys

input_file = 'data/seoul_youth_allowance_complaints.csv'
output_file = 'data/seoul_youth_allowance_complaints_updated.csv'
attachment_dir = 'docs/attachments_complaints'

if not os.path.exists(attachment_dir):
    os.makedirs(attachment_dir)

# Regex patterns
dept_pattern = re.compile(r'<th[^>]*>부서명</th>\s*<td[^>]*>(.*?)</td>', re.IGNORECASE | re.DOTALL)
author_pattern = re.compile(r'<th[^>]*>작성자.*?</th>\s*<td[^>]*>(.*?)</td>', re.IGNORECASE | re.DOTALL)
# Match the "Original" download link (contains "원문")
# Iterating through tags is safer, implemented below.

def clean_text(text):
    if not text:
        return ""
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    return html.unescape(text).strip()

def sanitize_filename(name):
    return re.sub(r'[\\/*?:"><|]', "", name)

rows = []
with open(input_file, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    fieldnames = ['Index'] + reader.fieldnames + ['Department', 'Author', 'Original_File_Path', 'PDF_File_Path']
    for idx, row in enumerate(reader, start=1):
        row['Index'] = str(idx)
        rows.append(row)

print(f"Processing {len(rows)} documents...")

updated_rows = []
processed_count = 0

headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/35.0.1916.47 Safari/537.36'
}

for row in rows:
    url = row['URL']
    idx = row['Index']
    title = row['Document Name']
    print(f"[{processed_count+1}/{len(rows)}] Processing Index {idx}: {title}")
    
    dept = ""
    author = ""
    original_path = ""
    pdf_path = ""
    
    try:
        req_page = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req_page) as response:
            content = response.read().decode('utf-8')
            
            # Extract Dept
            m_dept = dept_pattern.search(content)
            if m_dept:
                dept = clean_text(m_dept.group(1))
            
            # Extract Author
            m_author = author_pattern.search(content)
            if m_author:
                author = clean_text(m_author.group(1))
            
            # Extract Original Download Link
            # Find all links with class "btn-original"
            all_links = re.finditer(r'<a([^>]+)>(.*?)</a>', content, re.DOTALL | re.IGNORECASE)
            
            download_url = None
            
            for link_match in all_links:
                attrs = link_match.group(1)
                text = link_match.group(2)
                
                if 'btn-original' in attrs and '원문' in text:
                    # Extract href from attrs
                    m_href = re.search(r'href="([^"]+)"', attrs)
                    if m_href:
                        download_href = html.unescape(m_href.group(1))
                        if download_href.startswith('/'):
                            download_url = "https://opengov.seoul.go.kr" + download_href
                        else:
                            download_url = download_href
                        break # Found it
            
            if download_url:
                # Determine extension
                parsed_url = urllib.parse.urlparse(download_url)
                params = urllib.parse.parse_qs(parsed_url.query)
                
                ext = ".hwpx" # Default
                if 'dname' in params:
                    dname = params['dname'][0]
                    _, ext = os.path.splitext(dname)
                elif 'uri' in params:
                    uri = params['uri'][0]
                    _, ext = os.path.splitext(uri)
                
                if not ext:
                    ext = ".hwpx"
                
                filename = f"{idx}_original{ext}"
                save_path = os.path.join(attachment_dir, filename)
                
                # Download file
                try:
                    if not os.path.exists(save_path):
                        print(f"  Downloading Original to {save_path}...")
                        req_dl = urllib.request.Request(download_url, headers=headers)
                        with urllib.request.urlopen(req_dl) as dl_response:
                            data = dl_response.read()
                            # Check if data looks like the error script
                            if b"<script>alert" in data and len(data) < 200:
                                 print(f"  Error: Downloaded file seems to be an error message.")
                            else:
                                with open(save_path, 'wb') as f_out:
                                    f_out.write(data)
                                original_path = save_path
                    else:
                        original_path = save_path
                except Exception as e:
                    print(f"  Failed to download original: {e}")
            else:
                print("  No 'Original' attachment link found.")

    except Exception as e:
        print(f"  Failed to fetch page: {e}")
    
    row['Department'] = dept
    row['Author'] = author
    row['Original_File_Path'] = original_path
    row['PDF_File_Path'] = pdf_path
    updated_rows.append(row)
    
    processed_count += 1
    # time.sleep(0.1)

# Write updated CSV
with open(output_file, 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(updated_rows)

print(f"Done. Updated CSV saved to {output_file}")
