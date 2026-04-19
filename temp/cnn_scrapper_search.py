"""
CNN Indonesia Scraper - Mode SEARCH
=====================================
Mengambil berita dari halaman hasil pencarian CNN Indonesia.

Contoh URL yang didukung:
  - https://www.cnnindonesia.com/search?query=iran
  - https://www.cnnindonesia.com/search?query=iran&kanal=nasional
  - https://www.cnnindonesia.com/search?query=iran&kanal=internasional
  - https://www.cnnindonesia.com/search?query=iran&fromdate=18%2F04%2F2026&todate=18%2F04%2F2026
  - https://www.cnnindonesia.com/search?query=iran&kanal=nasional&fromdate=12%2F04%2F2026&todate=19%2F04%2F2026
  - https://www.cnnindonesia.com/search?query=iran&fromdate=18%2F04%2F2026&todate=18%2F04%2F2026&page=2

Penggunaan:
  python cnn_scraper_search.py

Output: cnn_search_result.json
"""

import requests
from bs4 import BeautifulSoup
import json
import time
import re
import logging
from datetime import datetime
from urllib.parse import urljoin, urlparse, parse_qs, urlencode, urlunparse, quote

# ─────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────
CONFIG = {
    # Daftar query pencarian. Setiap item adalah dict dengan key:
    #   query     : kata kunci (wajib)
    #   kanal     : nasional | internasional | ekonomi | olahraga |
    #               teknologi | otomotif | edukasi | hiburan | gaya-hidup | tv
    #               (kosongkan / hapus untuk semua kanal)
    #   fromdate  : DD/MM/YYYY  (opsional)
    #   todate    : DD/MM/YYYY  (opsional)
    "searches": [
        {
            "query":    "iran",
            "kanal":    "nasional",
            "fromdate": "18/04/2026",
            "todate":   "18/04/2026",
        },
        # Contoh lain (hapus tanda # untuk aktifkan):
        # {"query": "ekonomi", "fromdate": "18/04/2026", "todate": "18/04/2026"},
        # {"query": "bola"},
    ],

    # Batas maksimal halaman per query (None = semua halaman)
    "max_halaman": None,

    # Jeda antar request (detik)
    "delay_halaman":  1.5,
    "delay_artikel":  1.0,

    # File output
    "output_file": "./result/cnn_search_result.json",
}
# ─────────────────────────────────────────────────────────────

BASE_URL    = "https://www.cnnindonesia.com"
SEARCH_BASE = f"{BASE_URL}/search"
MEDIA_NAME  = "CNN Indonesia"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "id-ID,id;q=0.9",
    "Referer": BASE_URL,
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)

ARTICLE_PATTERN = re.compile(r"/[\w-]+/\d{14}-\d+-\d+/[\w-]+")


# ──────────────────────────────────────────────────────────────
# HTTP helper
# ──────────────────────────────────────────────────────────────

def get_soup(url: str, retries: int = 3):
    for attempt in range(1, retries + 1):
        try:
            r = SESSION.get(url, timeout=15)
            r.raise_for_status()
            return BeautifulSoup(r.text, "html.parser")
        except requests.RequestException as e:
            log.warning(f"[{attempt}/{retries}] {url} → {e}")
            if attempt < retries:
                time.sleep(3)
    log.error(f"Gagal: {url}")
    return None


# ──────────────────────────────────────────────────────────────
# URL builder untuk halaman search
# ──────────────────────────────────────────────────────────────

def build_search_url(query: str, kanal: str = "", fromdate: str = "",
                     todate: str = "", page: int = 1) -> str:
    """
    Bangun URL search CNN Indonesia.
    fromdate / todate format: DD/MM/YYYY → di-encode jadi DD%2FMM%2FYYYY
    """
    params = {"query": query}
    if kanal:
        params["kanal"] = kanal
    if fromdate:
        params["fromdate"] = fromdate   # requests akan encode otomatis
    if todate:
        params["todate"] = todate
    if page > 1:
        params["page"] = str(page)

    return f"{SEARCH_BASE}?{urlencode(params, safe='/')}"


# ──────────────────────────────────────────────────────────────
# Pagination helper
# ──────────────────────────────────────────────────────────────

def get_max_page(soup: BeautifulSoup) -> int:
    """Deteksi total halaman dari link pagination."""
    max_p = 1
    for a in soup.find_all("a", href=True):
        m = re.search(r"[?&]page=(\d+)", a["href"])
        if m:
            max_p = max(max_p, int(m.group(1)))
    # Coba juga teks angka dalam elemen pagination
    for sel in ["div.pagination", "ul.pagination", "nav[class*='page']"]:
        pag = soup.select_one(sel)
        if pag:
            for txt in pag.stripped_strings:
                if txt.isdigit():
                    max_p = max(max_p, int(txt))
    return max_p


# ──────────────────────────────────────────────────────────────
# Parse hasil search → daftar URL artikel
# ──────────────────────────────────────────────────────────────

def parse_search_links(soup: BeautifulSoup) -> list:
    """
    Kumpulkan URL artikel dari halaman hasil search.
    Halaman search CNN Indonesia menampilkan kartu yang sama
    dengan halaman indeks: <a href="/kanal/timestamp-id/slug">
    """
    urls = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not ARTICLE_PATTERN.search(href):
            continue
        if any(x in href for x in ["/tv/", "/foto/", "/video/", "/infografis/"]):
            continue
        full = urljoin(BASE_URL, href)
        if full not in seen:
            seen.add(full)
            urls.append(full)
    return urls


def has_no_results(soup: BeautifulSoup) -> bool:
    """Cek apakah halaman menunjukkan 'tidak ada hasil'."""
    teks = soup.get_text(" ", strip=True).lower()
    keywords = ["tidak ditemukan", "no result", "0 result",
                "tidak ada hasil", "pencarian tidak"]
    return any(k in teks for k in keywords)


# ──────────────────────────────────────────────────────────────
# Parse detail satu artikel (sama dengan scraper indeks)
# ──────────────────────────────────────────────────────────────

def parse_tanggal(soup: BeautifulSoup) -> str:
    el = soup.select_one("div.text-cnn_grey")
    if el:
        return el.get_text(strip=True)
    el = soup.find("time")
    if el:
        return el.get("datetime") or el.get_text(strip=True)
    teks = soup.get_text(" ", strip=True)
    m = re.search(
        r"(Senin|Selasa|Rabu|Kamis|Jumat|Sabtu|Minggu)"
        r",\s+\d{1,2}\s+\w+\s+\d{4}\s+\d{2}:\d{2}\s+WIB",
        teks
    )
    return m.group(0) if m else ""


def parse_isi(soup: BeautifulSoup) -> str:
    content = soup.select_one("div.detail-text")
    if not content:
        return ""
    for junk in content.select(
        "div.paradetail, div[class*='ads'], table.linksisip, "
        "script, style, center, div[id*='gpt'], iframe, "
        "div[data-type], a.embed, .inbetween_ads"
    ):
        junk.decompose()
    paragraphs = [p.get_text(strip=True) for p in content.find_all("p") if p.get_text(strip=True)]
    return "\n\n".join(paragraphs)


def scrape_article(url: str) -> dict | None:
    soup = get_soup(url)
    if not soup:
        return None

    h1    = soup.select_one("h1")
    judul = h1.get_text(strip=True) if h1 else ""
    isi   = parse_isi(soup)
    tgl   = parse_tanggal(soup)

    if not judul and not isi:
        return None

    return {
        "url":              url,
        "judul":            judul,
        "isi":              isi,
        "tanggalPublikasi": tgl,
        "media":            MEDIA_NAME,
    }


# ──────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────

def main():
    cfg     = CONFIG
    results = []
    seen_article_urls = set()   # hindari duplikat antar query

    for search_cfg in cfg["searches"]:
        query    = search_cfg.get("query", "")
        kanal    = search_cfg.get("kanal", "")
        fromdate = search_cfg.get("fromdate", "")
        todate   = search_cfg.get("todate", "")

        label = f"query='{query}'"
        if kanal:    label += f" kanal={kanal}"
        if fromdate: label += f" dari={fromdate}"
        if todate:   label += f" s/d={todate}"
        log.info(f"═══ Search: {label} ═══")

        # Halaman pertama → deteksi total halaman
        url_p1 = build_search_url(query, kanal, fromdate, todate, page=1)
        log.info(f"URL: {url_p1}")
        soup1  = get_soup(url_p1)
        if not soup1:
            continue

        if has_no_results(soup1):
            log.info("Tidak ada hasil untuk query ini, lewati.")
            continue

        max_page = get_max_page(soup1)
        max_page = min(max_page, cfg["max_halaman"]) if cfg["max_halaman"] else max_page
        log.info(f"Total halaman: {max_page}")

        for page in range(1, max_page + 1):
            if page == 1:
                soup = soup1
            else:
                time.sleep(cfg["delay_halaman"])
                url_p = build_search_url(query, kanal, fromdate, todate, page)
                log.info(f"Halaman {page}: {url_p}")
                soup  = get_soup(url_p)
                if not soup:
                    break

            art_urls = parse_search_links(soup)
            log.info(f"Halaman {page}/{max_page} → {len(art_urls)} artikel ditemukan")

            if not art_urls:
                log.info("Halaman kosong, berhenti.")
                break

            for idx, art_url in enumerate(art_urls, 1):
                if art_url in seen_article_urls:
                    log.info(f"  [{idx}] Duplikat, skip: {art_url}")
                    continue
                seen_article_urls.add(art_url)

                log.info(f"  [{idx}/{len(art_urls)}] {art_url}")
                time.sleep(cfg["delay_artikel"])
                data = scrape_article(art_url)
                if data:
                    results.append(data)
                    log.info(f"    ✓ {data['judul'][:60]}...")

    # Simpan JSON
    with open(cfg["output_file"], "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    log.info(f"\n✓ Selesai! {len(results)} artikel → '{cfg['output_file']}'")
    return results


if __name__ == "__main__":
    main()