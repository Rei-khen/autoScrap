"""
CNN Indonesia - Probe API Search Endpoint
==========================================
Script ini mencoba semua kemungkinan API endpoint search CNN Indonesia
untuk menemukan yang aktif dan mengembalikan data artikel.

Jalankan: py cnn_probe_api.py
"""
import requests
import json

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/html, */*",
    "Accept-Language": "id-ID,id;q=0.9",
    "Referer": "https://www.cnnindonesia.com/search?query=iran",
    "X-Requested-With": "XMLHttpRequest",
}

QUERY    = "iran"
FROMDATE = "18/04/2026"
TODATE   = "18/04/2026"

# Semua kemungkinan endpoint + parameter yang umum di Detik/CNN group
candidates = [
    # Format 1: endpoint /search/ajax berbagai variasi parameter
    f"https://www.cnnindonesia.com/search/ajax?q={QUERY}",
    f"https://www.cnnindonesia.com/search/ajax?query={QUERY}",
    f"https://www.cnnindonesia.com/search/ajax?query={QUERY}&fromdate={FROMDATE}&todate={TODATE}",

    # Format 2: /api/v1/search
    f"https://www.cnnindonesia.com/api/v1/search?query={QUERY}",
    f"https://www.cnnindonesia.com/api/search?query={QUERY}",

    # Format 3: parameter tanggal pakai nama berbeda (dari debug: tanggaldari/tanggalsampai)
    f"https://www.cnnindonesia.com/search?query={QUERY}&tanggaldari={FROMDATE}&tanggalsampai={TODATE}&format=json",
    f"https://www.cnnindonesia.com/search?query={QUERY}&tanggaldari={FROMDATE}&tanggalsampai={TODATE}&type=json",

    # Format 4: Detik search API (CNN Indonesia berbagi infrastruktur dengan Detik)
    f"https://www.cnnindonesia.com/search?q={QUERY}&site=cnnindonesia.com&from={FROMDATE}&to={TODATE}",

    # Format 5: endpoint search dengan Accept: application/json
    f"https://www.cnnindonesia.com/search?query={QUERY}&fromdate=18%2F04%2F2026&todate=18%2F04%2F2026",

    # Format 6: endpoint umum lain
    f"https://www.cnnindonesia.com/search/result?query={QUERY}",
    f"https://www.cnnindonesia.com/search/articles?query={QUERY}",
]

print(f"Mencoba {len(candidates)} endpoint kandidat...\n")

for url in candidates:
    try:
        r = requests.get(url, headers=headers, timeout=10)
        ct = r.headers.get("content-type", "")
        size = len(r.text)

        # Cek apakah response berisi data artikel
        has_json   = "json" in ct or r.text.strip().startswith("{") or r.text.strip().startswith("[")
        has_article = any(x in r.text for x in ['"judul"', '"title"', '"url"', '/20260418', '2026/04/18', 'cnnindonesia.com/'])

        status_icon = "✓" if (has_json or has_article) else "✗"
        print(f"{status_icon} [{r.status_code}] {url}")
        print(f"    Content-Type: {ct}  |  Size: {size} chars  |  JSON: {has_json}  |  HasArticle: {has_article}")

        if has_json and has_article:
            print("    *** KEMUNGKINAN ENDPOINT YANG BENAR! ***")
            print("    Preview response (500 char pertama):")
            print("   ", r.text[:500])

        print()

    except Exception as e:
        print(f"✗ ERROR: {url}")
        print(f"    {e}\n")