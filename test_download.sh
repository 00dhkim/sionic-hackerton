#!/bin/bash
# Test Original Download
url_original="https://opengov.seoul.go.kr/og/com/download.php?nid=35027731&dtype=basic&rid=F0000116342709&fid=&uri=%2Ffiles%2Fdcdata%2F100001%2F20251217%2FF0000116342709.hwpx"
echo "Downloading Original..."
curl -L -o "test_original.hwpx" "$url_original"
file test_original.hwpx

# Test PDF Download hypothesis
url_pdf="https://opengov.seoul.go.kr/og/com/download.php?nid=35027731&dtype=pdf&rid=F0000116342709"
echo "Downloading PDF..."
curl -L -o "test.pdf" "$url_pdf"
file test.pdf
