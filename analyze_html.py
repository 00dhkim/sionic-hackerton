import re

with open('detail_page.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Extract Document Info Table
doc_info_pattern = re.compile(r'<h4>문서 정보</h4>(.*?)</table>', re.DOTALL)
doc_info_match = doc_info_pattern.search(content)

if doc_info_match:
    table_content = doc_info_match.group(1)
    # Remove HTML tags for easier reading or parse with regex
    print("Found Document Info Table Content")
    print(table_content) # Debugging
    
    # Simple regex to find Dept and Author
    # Looking for table rows. Structure might be: <th>부서명</th><td>...</td>
    
    dept_match = re.search(r'부서명.*?<td[^>]*>(.*?)</td>', table_content, re.DOTALL)
    if dept_match:
        print(f"Dept: {dept_match.group(1).strip()}")
    else:
        print("Dept not found in table")
        
    author_match = re.search(r'작성자.*?<td[^>]*>(.*?)</td>', table_content, re.DOTALL)
    if author_match:
        print(f"Author: {author_match.group(1).strip()}")
    else:
        print("Author not found in table")
else:
    print("Document Info Table not found")

# Extract Attachments
# Looking for <ul class="list-attachment"> ... </ul>
attachment_pattern = re.compile(r'<ul class="list-attachment">(.*?)</ul>', re.DOTALL)
att_match = attachment_pattern.search(content)

if att_match:
    att_content = att_match.group(1)
    # Find links with specific classes or text
    # "PDF" link usually has class "btn-download" and text "PDF" inside or icon
    # <a data-rid="..." href="..." class="btn btn-download btn-original">... PDF...</a>
    # <a ... >... 원문...</a>
    
    print("\nAttachment Content:")
    print(att_content)
else:
    print("Attachments list not found")
