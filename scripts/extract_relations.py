import os
import re
import csv
import glob

# Configuration
ATTACHMENT_DIR = 'docs/attachments'
INPUT_CSV = 'data/seoul_youth_allowance_others_with_docnum.csv'
OUTPUT_CSV = 'data/citation_relations.csv'

# Regex pattern for document numbers: Hangul + Hyphen + Digits
# e.g., 청년사업담당관-11290
DOC_NUM_PATTERN = re.compile(r'([가-힣]+(?:[ ][가-힣]+)*-\d+)')

def clean_doc_num(text):
    """
    Cleans up the extracted document number string.
    Removes common prefixes like "문서 번호는 ", "접수 ", etc.
    """
    if not text: return None
    # Extract the core pattern
    match = DOC_NUM_PATTERN.search(text)
    if match:
        return match.group(1).strip()
    return None

def main():
    print("Step 1: Loading Document Map from CSV...")
    doc_map = {} # { "청년사업담당관-1234": "12" } 
    
    with open(INPUT_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            idx = row['Index']
            raw_doc_num = row.get('Doc_Number', '')
            
            clean_num = clean_doc_num(raw_doc_num)
            if clean_num:
                doc_map[clean_num] = idx
            # else:
            #     print(f"Skipping index {idx}: Invalid doc num '{raw_doc_num}'")

    print(f"Mapped {len(doc_map)} documents from CSV.")

    print("Step 2: Finding Citations in Parsed Files...")
    relations = []
    
    files = glob.glob(os.path.join(ATTACHMENT_DIR, '*_parsed.md'))
    
    for file_path in files:
        filename = os.path.basename(file_path)
        # Extract source index from filename (e.g. "12_parsed.md" -> "12")
        match = re.search(r'^(\d+)_', filename)
        if not match: continue
        source_idx = match.group(1)

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
                # Check for each known document number in this file's content
                for target_doc_num, target_idx in doc_map.items():
                    if source_idx == target_idx:
                        continue # Skip self-reference

                    # Use regex with negative lookahead to avoid partial matches
                    # e.g. "Doc-67" should not match "Doc-6798"
                    # Ensure the char after the number is NOT a digit or hyphen
                    # We also escape the doc num just in case
                    pattern = re.compile(re.escape(target_doc_num) + r'(?!\d|-)')
                    
                    match = pattern.search(content)
                    if match:
                        # Find context
                        start = max(0, match.start() - 50)
                        end = min(len(content), match.end() + 50)
                        context = content[start:end].replace('\n', ' ').strip()
                        
                        relations.append({
                            'Source_Index': source_idx,
                            'Target_Index': target_idx,
                            'Cited_Doc_Num': target_doc_num,
                            'Citation_Text': f"...{context}..."
                        })
 
        except Exception as e:
            print(f"Error reading {filename}: {e}")

    print(f"Found {len(relations)} relations.")

    print("Step 3: Saving to CSV...")
    with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['Source_Index', 'Target_Index', 'Cited_Doc_Num', 'Citation_Text'])
        writer.writeheader()
        writer.writerows(relations)
    
    print(f"Saved to {OUTPUT_CSV}")

if __name__ == "__main__":
    main()
