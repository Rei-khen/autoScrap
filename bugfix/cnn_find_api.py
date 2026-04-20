"""
CNN Indonesia - Debug Script untuk menemukan API endpoint search
Jalankan: py cnn_find_api.py
"""
import requests
from bs4 import BeautifulSoup
import re

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "id-ID,id;q=0.9",
}

url = "https://www.cnnindonesia.com/search?query=iran&fromdate=18%2F04%2F2026&todate=18%2F04%2F2026"
r = requests.get(url, headers=headers, timeout=15)
soup = BeautifulSoup(r.text, "html.parser")

print("=" * 60)
print("DUMP SEMUA SCRIPT TAG (konten inline)")
print("=" * 60)

for i, sc in enumerate(soup.find_all("script")):
    content = sc.string or ""
    src = sc.get("src", "")
    if content.strip():
        print(f"\n{'─'*50}")
        print(f"[script #{i}]")
        print(content)   # <-- dump FULL, tidak dipotong

print("\n" + "=" * 60)
print("SEMUA EXTERNAL SCRIPT src=")
print("=" * 60)
for sc in soup.find_all("script", src=True):
    print(sc["src"])