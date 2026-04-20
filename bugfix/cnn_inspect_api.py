"""
Inspect struktur JSON dari API search CNN Indonesia
Jalankan: py cnn_inspect_api.py
"""
import requests
import json

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://www.cnnindonesia.com/",
}

# Test 1: query dasar
print("=== TEST 1: Query dasar ===")
r = requests.get("https://www.cnnindonesia.com/api/search?query=iran", headers=headers, timeout=15)
data = r.json()
print(f"Top-level keys: {list(data.keys())}")
print(f"Jumlah item di 'data': {len(data.get('data', []))}")

# Tampilkan struktur satu item
if data.get("data"):
    item = data["data"][0]
    print(f"\nKey di setiap artikel:")
    for k, v in item.items():
        val_preview = str(v)[:80].replace('\n', ' ')
        print(f"  {k!r:30s} = {val_preview!r}")

print()

# Test 2: dengan filter tanggal - coba berbagai nama parameter
print("=== TEST 2: Coba parameter tanggal ===")
date_param_candidates = [
    {"fromdate": "18/04/2026", "todate": "18/04/2026"},
    {"from": "18/04/2026", "to": "18/04/2026"},
    {"tanggaldari": "18/04/2026", "tanggalsampai": "18/04/2026"},
    {"date_from": "2026-04-18", "date_to": "2026-04-18"},
    {"start_date": "18/04/2026", "end_date": "18/04/2026"},
]
for params in date_param_candidates:
    params["query"] = "iran"
    r = requests.get("https://www.cnnindonesia.com/api/search", params=params, headers=headers, timeout=15)
    items = r.json().get("data", [])
    print(f"  {list(params.keys())[1]}/{list(params.keys())[2]}: {len(items)} hasil - ", end="")
    if items:
        # Cek apakah tanggal artikel sesuai filter
        sample_date = items[0].get("dtmpublisdate") or items[0].get("strtgl") or items[0].get("dtmcreate") or "?"
        print(f"sample tgl={sample_date!r}")
    else:
        print("kosong")

print()

# Test 3: parameter pagination
print("=== TEST 3: Coba parameter pagination ===")
page_candidates = [
    {"page": 2},
    {"p": 2},
    {"offset": 10},
    {"start": 10},
]
base = {"query": "iran"}
for pp in page_candidates:
    params = {**base, **pp}
    r = requests.get("https://www.cnnindonesia.com/api/search", params=params, headers=headers, timeout=15)
    items = r.json().get("data", [])
    first_id = items[0].get("intidberita") if items else None
    print(f"  {pp}: {len(items)} hasil, first_id={first_id}")

print()

# Test 4: parameter kanal
print("=== TEST 4: Coba parameter kanal ===")
kanal_candidates = [
    {"kanal": "nasional"},
    {"kanal": "3"},
    {"channel": "nasional"},
    {"idkanal": "3"},
]
for kp in kanal_candidates:
    params = {**base, **kp}
    r = requests.get("https://www.cnnindonesia.com/api/search", params=params, headers=headers, timeout=15)
    items = r.json().get("data", [])
    first_kanal = items[0].get("intidkanal") if items else None
    print(f"  {kp}: {len(items)} hasil, first_kanal={first_kanal}")

print()

# Dump full JSON response (pretty) ke file
print("=== Menyimpan full response ke api_response.json ===")
r = requests.get("https://www.cnnindonesia.com/api/search?query=iran", headers=headers, timeout=15)
with open("api_response.json", "w", encoding="utf-8") as f:
    json.dump(r.json(), f, ensure_ascii=False, indent=2)
print("Tersimpan di api_response.json")