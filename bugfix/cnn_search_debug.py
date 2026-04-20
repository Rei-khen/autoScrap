"""
Debug helper: dump raw HTML dari halaman search CNN Indonesia
untuk diagnosa kenapa artikel tidak terdeteksi.
"""
import requests
from bs4 import BeautifulSoup
import re

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "id-ID,id;q=0.9",
    "Referer": "https://www.cnnindonesia.com",
}

url = "https://www.cnnindonesia.com/search?query=iran&fromdate=18%2F04%2F2026&todate=18%2F04%2F2026"
print(f"Fetching: {url}\n")

r = requests.get(url, headers=headers, timeout=15)
print(f"Status: {r.status_code}")
print(f"Final URL: {r.url}")
print(f"Content-Type: {r.headers.get('content-type')}")
print()

soup = BeautifulSoup(r.text, "html.parser")

# Cek apakah ada artikel dengan pola URL
ARTICLE_PATTERN = re.compile(r"/[\w-]+/\d{14}-\d+-\d+/[\w-]+")
all_links = [(a["href"], a.get_text(strip=True)[:60]) for a in soup.find_all("a", href=True)]
article_links = [(h, t) for h, t in all_links if ARTICLE_PATTERN.search(h)]

print(f"Total <a> di halaman: {len(all_links)}")
print(f"Link artikel (pola timestamp): {len(article_links)}")
if article_links:
    print("Contoh link artikel:")
    for h, t in article_links[:5]:
        print(f"  {h}  |  {t}")
print()

# Dump 200 char pertama dari setiap <a>
print("=== 20 link pertama dari halaman ===")
for h, t in all_links[:20]:
    print(f"  href={h!r}  text={t!r}")
print()

# Cek apakah ada JSON embedded di halaman (Next.js / SSR)
scripts = soup.find_all("script")
print(f"Total <script> tag: {len(scripts)}")
for i, sc in enumerate(scripts):
    content = sc.string or ""
    if "query" in content.lower() and len(content) > 100:
        print(f"\n--- script[{i}] (pertama 300 char) ---")
        print(content[:300])

# Dump 2000 char pertama dari body teks
print("\n=== Body text (500 char pertama) ===")
print(soup.get_text(" ", strip=True)[:500])