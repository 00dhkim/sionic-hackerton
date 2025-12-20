import urllib.request
import re
import csv
import time
import html

base_url = "https://opengov.seoul.go.kr"
list_url_template = "https://opengov.seoul.go.kr/policy/item?items_per_page=50&nid=32175351&multiViewer=on&mvNid-00=undefined&mvNid-01=undefined&page={}"

# Regex
# Capture 1: href
# Capture 2: Title
# Capture 3: Date
# Note: The grep output showed the title text is immediately after </strong> inside <a>
pattern = re.compile(
    r'<div class="title-area">\s*'
    r'<a href="([^"]+)">\s*<strong[^>]*>.*?</strong>(.*?)\s*</a>.*?'
    r'<span class="date">\s*<strong[^>]*>.*?</strong>\s*([0-9-]+)\s*</span>',
    re.DOTALL | re.IGNORECASE
)

data = []

for page in range(1, 8):
    url = list_url_template.format(page)
    print(f"Fetching page {page}...")
    try:
        with urllib.request.urlopen(url) as response:
            content = response.read().decode('utf-8')
            
            matches = pattern.findall(content)
            print(f"Found {len(matches)} items on page {page}")
            
            for href, title, date in matches:
                full_url = base_url + href
                clean_title = html.unescape(title.strip())
                data.append([clean_title, full_url, date])
                
        time.sleep(0.5)
    except Exception as e:
        print(f"Error fetching page {page}: {e}")

# Save to CSV
output_file = 'seoul_youth_allowance_docs.csv'
with open(output_file, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['Document Name', 'URL', 'Date'])
    writer.writerows(data)

print(f"Total items collected: {len(data)}")
print(f"Saved to {output_file}")
