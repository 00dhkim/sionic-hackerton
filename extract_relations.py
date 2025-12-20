import os
import re
import csv
import glob

# Configuration
ATTACHMENT_DIR = 'attachments'
OUTPUT_CSV = 'citation_relations.csv'

# Regex patterns
# Pattern to find the document number. 
# Matches: Hangul words (possibly with spaces) + Hyphen + Digits
# Example: 청년사업담당관-11290
DOC_NUM_PATTERN = re.compile(r'([가-힣]+(?:[ ][가-힣]+)*-\d+)')

def get_file_index(filename):
    """Extracts the numeric index from the filename (e.g., '12_parsed.md' -> '12')"""
    match = re.search(r'^(\d+)_', filename)
    if match:
        return match.group(1)
    return None

def extract_own_doc_number(content):
    """
    Attempts to find the document's own number.
    Usually appears near '문서번호' at the beginning of the file.
    """
    # Look for the pattern specifically after "문서번호"
    # This regex looks for "문서번호" followed by loose matching until the pattern
    match = re.search(r'문서번호\s*[:|]?\s*([가-힣]+(?:[ ][가-힣]+)*-\d+)', content[:1000]) # Scan first 1000 chars
    if match:
        return match.group(1)
    
    # Fallback: Find the first occurrence of the pattern in the first 500 chars 
    # (assuming the header contains it)
    match = DOC_NUM_PATTERN.search(content[:500])
    if match:
        return match.group(1)
    
    return None

def extract_relations():
    doc_map = {} # Mapping: DocNumber -> FileIndex
    file_contents = {} # Cache content to avoid re-reading: FileIndex -> Content

    print("Phase 1: Indexing Document Numbers...")
    files = glob.glob(os.path.join(ATTACHMENT_DIR, '*_parsed.md'))
    
    for file_path in files:
        filename = os.path.basename(file_path)
        idx = get_file_index(filename)
        if not idx:
            continue

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                file_contents[idx] = content
                
                doc_num = extract_own_doc_number(content)
                if doc_num:
                    # Normalize: Remove spaces in the key for better matching (optional, but safer)
                    # Actually, let's keep it exact first, but maybe strip whitespace
                    clean_doc_num = doc_num.strip()
                    doc_map[clean_doc_num] = idx
                    # print(f"  [{idx}] Identified as {clean_doc_num}")
        except Exception as e:
            print(f"Error reading {filename}: {e}")

    print(f"Total documents with identified numbers: {len(doc_map)}")

    print("Phase 2: Finding Citations...")
    relations = []

    for source_idx, content in file_contents.items():
        # Find all document number patterns in the text
        # We iterate through all unique matches
        for match in set(DOC_NUM_PATTERN.findall(content)):
            cited_doc_num = match.strip()
            
            # Check if this cited number exists in our map
            if cited_doc_num in doc_map:
                target_idx = doc_map[cited_doc_num]
                
                # 1. Self-reference check: Don't record if finding its own number
                if source_idx == target_idx:
                    continue
                
                # 2. Extract Context (Citation Text)
                # Find the location of the match to extract context
                # We simply find the first occurrence for the snippet
                text_match = re.search(re.escape(cited_doc_num), content)
                context_snippet = ""
                if text_match:
                    start = max(0, text_match.start() - 50)
                    end = min(len(content), text_match.end() + 50)
                    context_snippet = content[start:end].replace('\n', ' ').strip()
                    # Add ellipsis
                    context_snippet = f"...{context_snippet}..."

                relations.append({
                    'Source_Doc_Index': source_idx,
                    'Target_Doc_Index': target_idx,
                    'Target_Doc_Number': cited_doc_num,
                    'Citation_Text': context_snippet
                })

    print(f"Total relations found: {len(relations)}")

    # Write to CSV
    with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['Source_Doc_Index', 'Target_Doc_Index', 'Target_Doc_Number', 'Citation_Text'])
        writer.writeheader()
        writer.writerows(relations)
    
    print(f"Relations saved to {OUTPUT_CSV}")

if __name__ == "__main__":
    extract_relations()
