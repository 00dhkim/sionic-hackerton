import csv
import urllib.request
import urllib.parse
import re
import os
import time
import html
import sys

input_file = 'data/seoul_youth_allowance_others.csv'
output_file = 'data/seoul_youth_allowance_others_updated.csv'
attachment_dir = 'docs/attachments'

if not os.path.exists(attachment_dir):
    os.makedirs(attachment_dir)

# Regex patterns
dept_pattern = re.compile(r'<th[^>]*>부서명</th>\s*<td[^>]*>(.*?)</td>', re.IGNORECASE | re.DOTALL)
author_pattern = re.compile(r'<th[^>]*>작성자.*?</th>\s*<td[^>]*>(.*?)</td>', re.IGNORECASE | re.DOTALL)
# Match the "Original" download link (contains "원문")
original_link_pattern = re.compile(r'<a[^>]+href="([^"]+)"[^>]*class="[^"]*btn-original[^"]*"[^>]*>.*?원문.*?</a>', re.IGNORECASE | re.DOTALL)
# Match the "PDF" download link (contains "PDF") - simplistic check if href has params
pdf_link_pattern = re.compile(r'<a[^>]+href="([^"]+)"[^>]*class="[^"]*btn-original[^"]*"[^>]*>.*?PDF.*?</a>', re.IGNORECASE | re.DOTALL)

def clean_text(text):
    if not text:
        return ""
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    return html.unescape(text).strip()

def sanitize_filename(name):
    # Keep alphanumeric, dot, underscore, hyphen. Remove others.
    # Also handle korean characters if needed, but simple sanitization is safer for FS
    # But usually just removing illegal chars for linux/windows is enough
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

for row in rows:
    url = row['URL']
    idx = row['Index']
    title = row['Document Name']
    print(f"[{processed_count+1}/{len(rows)}] Processing Index {idx}: {title}")
    
    dept = ""
    author = ""
    original_path = ""
    pdf_path = ""
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/35.0.1916.47 Safari/537.36'
    }

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
            # Pattern: <a ... class="...btn-original..." ...> ... </a>
            # We capture the whole tag content to check for "원문"
            # Regex to match an anchor tag with btn-original class
            # We match <a followed by anything until class="...btn-original..." followed by anything until > then content then </a>
            # This is complex with regex alone.
            # Simpler: Find all <a ...>...</a> and filter.
            
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
                    # Always download again to fix corrupted files
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
                except Exception as e:
                    print(f"  Failed to download original: {e}")
            else:
                print("  No 'Original' attachment link found.")

            # Attempt PDF Link (Usually relies on JS, so strict href check might fail or return empty)
            m_pdf = pdf_link_pattern.search(content)
            if m_pdf:
                pdf_href = html.unescape(m_pdf.group(1))
                # Only try if it looks like a real download link with params or specific path
                if 'download.php' in pdf_href and ('?' in pdf_href or 'rid' in pdf_href):
                     if pdf_href.startswith('/'):
                        pdf_url = "https://opengov.seoul.go.kr" + pdf_href
                     else:
                        pdf_url = pdf_href
                     
                     filename_pdf = f"{idx}.pdf"
                     save_path_pdf = os.path.join(attachment_dir, filename_pdf)
                     
                     try:
                        if not os.path.exists(save_path_pdf):
                             print(f"  Downloading PDF to {save_path_pdf}...")
                             req_pdf = urllib.request.Request(pdf_url, headers=headers)
                             with urllib.request.urlopen(req_pdf) as pdf_resp:
                                with open(save_path_pdf, 'wb') as f_pdf:
                                    f_pdf.write(pdf_resp.read())
                        pdf_path = save_path_pdf
                     except Exception as e:
                         print(f"  Failed to download PDF: {e}")
                else:
                    # Often the PDF button is just a trigger for viewer and not a direct download
                    pass

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