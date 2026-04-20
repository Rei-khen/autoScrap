"""
CNN Indonesia Scraper - Mode SEARCH (Final v3)
===============================================
Menggunakan endpoint API internal: GET /api/search

Perbaikan dari versi sebelumnya:
  1. Filter kanal: berbasis slug URL artikel (akurat 100%)
     bukan intidjnkanal yang ternyata tidak konsisten
  2. Tidak ada early stop berbasis tanggal — API sort by RELEVANSI bukan tanggal,
     jadi artikel lama bisa muncul di halaman awal dan artikel baru di halaman akhir
  3. Smart stop: berhenti jika N halaman berturut-turut tidak ada artikel yang lolos filter

Penggunaan:
  python cnn_scraper_search.py

Output: cnn_search_result.json
"""

import requests
from bs4 import BeautifulSoup
import json
import math
import time
import re
import logging
from datetime import datetime
from urllib.parse import urlencode

# ─────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────
CONFIG = {
    # Daftar query pencarian. Key yang tersedia:
    #   query     : kata kunci (wajib)
    #   kanal     : nasional | internasional | ekonomi | olahraga |
    #               teknologi | otomotif | edukasi | hiburan | gaya-hidup | tv
    #               (hapus/kosongkan = semua kanal)
    #   fromdate  : DD/MM/YYYY  (opsional)
    #   todate    : DD/MM/YYYY  (opsional)
    "searches": [
        {
            "query":    "iran",
            "kanal":    "",
            "fromdate": "18/04/2026",
            "todate":   "18/04/2026",
        },
        # Contoh lain:
        # {"query": "ekonomi"},
        # {"query": "bola", "fromdate": "17/04/2026", "todate": "18/04/2026"},
        # {"query": "teknologi", "kanal": "teknologi"},
    ],

    # Batas maksimal halaman per query (None = ikuti total dari server).
    # PENTING: server mengembalikan total=10000 untuk query umum.
    # Set angka wajar (misal 50) jika tidak butuh semua hasil.
    "max_halaman": 50,

    # Smart stop: berhenti jika sejumlah halaman berturut-turut tidak ada
    # artikel yang lolos filter. Berguna saat pakai filter tanggal sempit.
    # Set None untuk nonaktifkan.
    "stop_setelah_halaman_kosong": 5,

    # Jeda antar request (detik)
    "delay_halaman": 1.0,
    "delay_artikel": 0.8,

    # True  → buka halaman artikel untuk ambil isi bersih (tanpa HTML tag/iklan)
    # False → ambil isi dari field 'strisi' di API response (lebih cepat)
    "ambil_detail_artikel": True,

    # File output
    "output_file": "./result/cnn_search_result_v3.json",
}
# ─────────────────────────────────────────────────────────────

BASE_URL   = "https://www.cnnindonesia.com"
API_URL    = f"{BASE_URL}/api/search"
MEDIA_NAME = "CNN Indonesia"
PER_PAGE   = 10

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
    "Accept": "application/json, */*",
    "Accept-Language": "id-ID,id;q=0.9",
    "Referer": f"{BASE_URL}/",
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)


# ──────────────────────────────────────────────────────────────
# HTTP helpers
# ──────────────────────────────────────────────────────────────

def get_json(params: dict, retries: int = 3) -> dict | None:
    for attempt in range(1, retries + 1):
        try:
            r = SESSION.get(API_URL, params=params, timeout=15)
            r.raise_for_status()
            return r.json()
        except (requests.RequestException, ValueError) as e:
            log.warning(f"[{attempt}/{retries}] API error: {e}")
            if attempt < retries:
                time.sleep(3)
    log.error(f"Gagal hit API: params={params}")
    return None


def get_soup(url: str, retries: int = 3) -> BeautifulSoup | None:
    for attempt in range(1, retries + 1):
        try:
            r = SESSION.get(url, timeout=15)
            r.raise_for_status()
            return BeautifulSoup(r.text, "html.parser")
        except requests.RequestException as e:
            log.warning(f"[{attempt}/{retries}] HTTP error: {e}")
            if attempt < retries:
                time.sleep(3)
    log.error(f"Gagal fetch: {url}")
    return None


# ──────────────────────────────────────────────────────────────
# Filter kanal — berbasis slug URL (akurat 100%)
# ──────────────────────────────────────────────────────────────

def extract_kanal_slug(url: str) -> str:
    """
    Ekstrak slug kanal dari URL artikel CNN Indonesia.
    Contoh: 'https://www.cnnindonesia.com/nasional/2026...' → 'nasional'
    """
    m = re.match(r"https?://www\.cnnindonesia\.com/([^/]+)/", url)
    return m.group(1) if m else ""


def passes_kanal_filter(url: str, kanal: str) -> bool:
    """
    Cek apakah kanal URL artikel sesuai filter.
    Perbandingan berbasis slug URL, bukan field API yang tidak konsisten.
    """
    if not kanal or kanal.lower() == "semua":
        return True
    article_kanal = extract_kanal_slug(url)
    return article_kanal == kanal.lower()


# ──────────────────────────────────────────────────────────────
# Filter tanggal — berbasis dtnewsdate
# ──────────────────────────────────────────────────────────────

def parse_dtnewsdate(val: str) -> datetime | None:
    """Parse '2026/04/19 22:19:23' → datetime"""
    try:
        return datetime.strptime(val.strip(), "%Y/%m/%d %H:%M:%S")
    except (ValueError, AttributeError):
        return None


def parse_user_date(val: str) -> datetime | None:
    """Parse 'DD/MM/YYYY' → datetime"""
    try:
        return datetime.strptime(val.strip(), "%d/%m/%Y")
    except (ValueError, AttributeError):
        return None


def passes_date_filter(item: dict, fromdate: str, todate: str) -> bool:
    """Cek apakah artikel dalam rentang tanggal yang diminta."""
    if not fromdate and not todate:
        return True
    dt = parse_dtnewsdate(item.get("dtnewsdate", ""))
    if dt is None:
        return False
    if fromdate:
        fr = parse_user_date(fromdate)
        if fr and dt.date() < fr.date():
            return False
    if todate:
        to = parse_user_date(todate)
        if to and dt.date() > to.date():
            return False
    return True


# ──────────────────────────────────────────────────────────────
# Parse isi artikel
# ──────────────────────────────────────────────────────────────

def clean_html(html_str: str) -> str:
    """HTML strisi → plain text (fallback jika tidak ambil detail)."""
    if not html_str:
        return ""
    soup = BeautifulSoup(html_str, "html.parser")
    for junk in soup.select("script, style, iframe, div[class*='ads']"):
        junk.decompose()
    paragraphs = [p.get_text(strip=True) for p in soup.find_all("p") if p.get_text(strip=True)]
    return "\n\n".join(paragraphs) if paragraphs else soup.get_text(separator="\n", strip=True)


def scrape_article_detail(url: str) -> tuple[str, str]:
    """Buka halaman artikel → return (isi_bersih, tanggal_publikasi)."""
    soup = get_soup(url)
    if not soup:
        return "", ""

    isi = ""
    content_div = soup.select_one("div.detail-text")
    if content_div:
        for junk in content_div.select(
            "div.paradetail, div[class*='ads'], table.linksisip, "
            "script, style, center, div[id*='gpt'], iframe, "
            "div[data-type], a.embed, .inbetween_ads"
        ):
            junk.decompose()
        paragraphs = [
            p.get_text(strip=True)
            for p in content_div.find_all("p")
            if p.get_text(strip=True)
        ]
        isi = "\n\n".join(paragraphs)

    tgl = ""
    el = soup.select_one("div.text-cnn_grey")
    if el:
        tgl = el.get_text(strip=True)
    else:
        el = soup.find("time")
        if el:
            tgl = el.get("datetime") or el.get_text(strip=True)

    return isi, tgl


# ──────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────

def main():
    cfg       = CONFIG
    results   = []
    seen_urls = set()

    for search_cfg in cfg["searches"]:
        query    = search_cfg.get("query", "").strip()
        kanal    = search_cfg.get("kanal", "").strip()
        fromdate = search_cfg.get("fromdate", "").strip()
        todate   = search_cfg.get("todate", "").strip()

        if not query:
            log.warning("Query kosong, dilewati.")
            continue

        label = f"query='{query}'"
        if kanal:    label += f"  kanal={kanal}"
        if fromdate: label += f"  dari={fromdate}"
        if todate:   label += f"  s/d={todate}"
        log.info(f"═══ Search: {label} ═══")

        # Halaman 1 → ambil total
        resp = get_json({"query": query, "page": 1})
        if not resp:
            continue

        total_items  = int(resp.get("total") or 0)
        total_pages  = math.ceil(total_items / PER_PAGE) if total_items else 1
        if cfg["max_halaman"]:
            total_pages = min(total_pages, cfg["max_halaman"])

        log.info(f"Total item server: {total_items}  →  akan scan {total_pages} halaman")

        pages_data    = {1: resp.get("data", [])}
        artikel_lolos = 0
        halaman_kosong_berturut = 0

        for page in range(1, total_pages + 1):
            # Smart stop
            limit = cfg.get("stop_setelah_halaman_kosong")
            if limit and halaman_kosong_berturut >= limit:
                log.info(f"  {limit} halaman berturut-turut tidak ada yang lolos, berhenti.")
                break

            if page in pages_data:
                items = pages_data[page]
            else:
                time.sleep(cfg["delay_halaman"])
                resp = get_json({"query": query, "page": page})
                if not resp:
                    break
                items = resp.get("data", [])

            if not items:
                log.info(f"  Halaman {page} kosong, berhenti.")
                break

            lolos_di_halaman = 0

            for item in items:
                url   = item.get("url", "")
                judul = item.get("strjudul", "")

                if not url:
                    continue

                # Filter kanal (berbasis slug URL)
                if not passes_kanal_filter(url, kanal):
                    continue

                # Filter tanggal
                if not passes_date_filter(item, fromdate, todate):
                    continue

                # Deduplicate
                if url in seen_urls:
                    continue
                seen_urls.add(url)

                lolos_di_halaman += 1
                artikel_lolos    += 1
                log.info(f"  ✓ [{artikel_lolos}] [{extract_kanal_slug(url)}] {judul[:65]}...")

                if cfg["ambil_detail_artikel"]:
                    time.sleep(cfg["delay_artikel"])
                    isi, tgl = scrape_article_detail(url)
                    if not isi:
                        isi = clean_html(item.get("strisi", ""))
                    if not tgl:
                        tgl = item.get("dtnewsdate", "")
                else:
                    isi = clean_html(item.get("strisi", ""))
                    tgl = item.get("dtnewsdate", "")

                results.append({
                    "url":              url,
                    "judul":            judul,
                    "isi":              isi,
                    "tanggalPublikasi": tgl,
                    "media":            MEDIA_NAME,
                })

            if lolos_di_halaman == 0:
                halaman_kosong_berturut += 1
                log.info(f"  Halaman {page}/{total_pages}: 0 lolos filter "
                         f"({halaman_kosong_berturut}/{limit or '∞'} streak)")
            else:
                halaman_kosong_berturut = 0
                log.info(f"  Halaman {page}/{total_pages}: {lolos_di_halaman} artikel lolos")

        log.info(f"  Total artikel lolos: {artikel_lolos}")

    # Simpan JSON
    with open(cfg["output_file"], "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    log.info(f"\n✓ Selesai! {len(results)} artikel → '{cfg['output_file']}'")
    return results


if __name__ == "__main__":
    main()