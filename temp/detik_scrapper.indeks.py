"""
Detik News Scraper - Mode INDEKS
==================================
Scraping berita dari halaman indeks Detik News
berdasarkan KANAL dan TANGGAL.

Penggunaan:
  python detik_scraper_indeks.py

Output: detik_indeks_result.json
"""

import requests
from bs4 import BeautifulSoup
import json
import time
import re
import logging
from datetime import datetime, timedelta
from urllib.parse import urljoin, urlencode

# ─────────────────────────────────────────────────────────────
# CONFIG – hanya isi ini
# ─────────────────────────────────────────────────────────────
CONFIG = {
    # Kanal yang ingin di-scrape.
    # Pilihan: lihat KANAL_MAP di bawah
    #
    # Satu kanal   : "kanal": "berita"
    # Multi kanal  : "kanal": ["berita", "internasional", "daerah"]
    # Semua kanal  : "kanal": "semua"
    "kanal": "berita",

    # Tanggal yang ingin di-scrape (format YYYY-MM-DD).
    #
    # Satu hari  : "tanggal": "2026-05-03"
    # Range      : "tanggal": ["2026-04-30", "2026-05-03"]  (inklusif)
    # Terbaru    : "tanggal": None  → tanpa filter tanggal
    "tanggal": "2026-05-03",

    # Batas maksimal halaman per kombinasi kanal+tanggal (None = semua)
    "max_halaman": None,

    # Jeda antar request (detik)
    "delay_halaman": 1.5,
    "delay_artikel": 1.0,

    # File output
    "output_file": "./result/detik_indeks_result.json",
}
# ─────────────────────────────────────────────────────────────

# Mapping nama kanal → slug URL
KANAL_MAP = {
    "semua":                  "",
    "berita":                 "berita",
    "daerah":                 "daerah",
    "internasional":          "internasional",
    "melindungi-tuah-marwah": "melindungi-tuah-marwah",
    "kolom":                  "kolom",
    "pro-kontra":             "pro-kontra",
    "foto-news":              "foto-news",
    "detiktv":                "detiktv",
    "bbc":                    "bbc",
    "australiaplus":          "australiaplus",
    "jawabarat":              "jawabarat",
    "jawatengah":             "jawatengah",
    "jawatimur":              "jawatimur",
    "suara-pembaca":          "suara-pembaca",
    "investigasi":            "investigasi",
    "intermeso":              "intermeso",
    "crimestory":             "crimestory",
    "pemilu":                 "pemilu",
    "pilkada":                "pilkada",
    "bangun-indonesia":       "bangun-indonesia",
    "jabodetabek":            "jabodetabek",
    "hukum":                  "hukum",
}

BASE_URL   = "https://news.detik.com"
MEDIA_NAME = "Detik News"

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




# ──────────────────────────────────────────────────────────────
# Validasi & normalisasi CONFIG
# ──────────────────────────────────────────────────────────────

def resolve_kanals(kanal_cfg) -> list:
    if isinstance(kanal_cfg, str):
        kanal_cfg = [kanal_cfg]
    result = []
    for k in kanal_cfg:
        k = k.strip().lower()
        if k not in KANAL_MAP:
            log.warning(
                f"Kanal '{k}' tidak dikenal, dilewati. "
                f"Pilihan: {list(KANAL_MAP.keys())}"
            )
            continue
        result.append(k)
    return result


def resolve_dates(tanggal_cfg) -> list:
    """
    Konversi input tanggal → list format MM/DD/YYYY (format Detik).

    None                          → [None]
    "YYYY-MM-DD"                  → ["MM/DD/YYYY"]
    ["YYYY-MM-DD", "YYYY-MM-DD"]  → range inklusif
    """
    if tanggal_cfg is None:
        return [None]

    fmt_in  = "%Y-%m-%d"
    fmt_out = "%m/%d/%Y"   # ← Detik pakai MM/DD/YYYY bukan DD/MM/YYYY

    if isinstance(tanggal_cfg, str):
        dt = datetime.strptime(tanggal_cfg.strip(), fmt_in)
        return [dt.strftime(fmt_out)]

    if isinstance(tanggal_cfg, list) and len(tanggal_cfg) == 2:
        start = datetime.strptime(tanggal_cfg[0].strip(), fmt_in)
        end   = datetime.strptime(tanggal_cfg[1].strip(), fmt_in)
        dates, cur = [], start
        while cur <= end:
            dates.append(cur.strftime(fmt_out))
            cur += timedelta(days=1)
        return dates

    raise ValueError(f"Format 'tanggal' tidak valid: {tanggal_cfg!r}")


# ──────────────────────────────────────────────────────────────
# URL builder
# ──────────────────────────────────────────────────────────────

def build_indeks_url(kanal: str, tanggal: str | None, page: int = 1) -> str:
    """
    Bangun URL indeks Detik News.
    PENTING: parameter date dan page selalu di-include bersamaan
             agar pagination tidak kehilangan filter tanggal.

    Contoh output:
      https://news.detik.com/berita/indeks?date=05%2F03%2F2026
      https://news.detik.com/berita/indeks?page=2&date=05%2F03%2F2026
      https://news.detik.com/indeks                              (semua, terbaru)
      https://news.detik.com/indeks?date=05%2F03%2F2026         (semua, tanggal)
    """
    slug = KANAL_MAP[kanal]
    base = f"{BASE_URL}/{slug}/indeks" if slug else f"{BASE_URL}/indeks"

    params = {}
    if page > 1:
        params["page"] = str(page)
    if tanggal:
        params["date"] = tanggal

    if params:
        # safe='/' agar date=05/03/2026 tidak di-encode jadi date=05%2F03%2F2026
        # Detik hanya mengenali slash biasa, bukan %2F
        return f"{base}?{urlencode(params, safe='/')}"
    return base


# ──────────────────────────────────────────────────────────────
# HTTP helper
# ──────────────────────────────────────────────────────────────

def get_soup(url: str, retries: int = 3):
    for attempt in range(1, retries + 1):
        try:
            # Buat request BARU setiap kali — jangan pakai Session
            # Session menyebabkan Detik mengembalikan halaman yang sama
            # untuk semua page (kemungkinan HTTP/2 connection caching)
            r = requests.get(url, headers=HEADERS, timeout=15)
            r.raise_for_status()
            return BeautifulSoup(r.text, "html.parser")
        except requests.RequestException as e:
            log.warning(f"[{attempt}/{retries}] {url} → {e}")
            if attempt < retries:
                time.sleep(3)
    log.error(f"Gagal: {url}")
    return None


# ──────────────────────────────────────────────────────────────
# Pagination
# ──────────────────────────────────────────────────────────────

def get_max_page(soup: BeautifulSoup) -> int:
    """
    Deteksi total halaman dari pagination Detik.
    Struktur: <div class="pagination"> dengan link page=N
    Ambil angka page terbesar dari semua link, kecuali link "last page"
    yang biasanya melompat jauh (misal page=500).
    """
    page_nums = []
    pag = soup.select_one("div.pagination")
    if not pag:
        return 1

    for a in pag.find_all("a", href=True):
        m = re.search(r"[?&]page=(\d+)", a["href"])
        if m:
            num = int(m.group(1))
            # Abaikan tombol "last" yang biasanya page=500 atau sangat besar
            # Detik menampilkan max 5 halaman di pagination + tombol Next
            text = a.get_text(strip=True).lower()
            if text not in ("next", "prev", "last", "first"):
                page_nums.append(num)

    # Ambil page terbesar yang visible (bukan tombol lompat jauh)
    # Detik biasanya tampilkan 5 halaman berurutan, jadi max visible << 500
    if page_nums:
        # Filter outlier: abaikan nilai yang > 10x nilai terbesar lainnya
        sorted_nums = sorted(page_nums)
        filtered = [n for n in sorted_nums if n <= sorted_nums[0] * 20 + 10]
        return max(filtered) if filtered else 1

    return 1


# ──────────────────────────────────────────────────────────────
# Parse daftar artikel dari halaman indeks
# ──────────────────────────────────────────────────────────────

def parse_index_links(soup: BeautifulSoup) -> list:
    """
    Kumpulkan URL artikel unik dari halaman indeks Detik.
    Setiap artikel muncul 2x di HTML (dari img dan dari h3.media__title),
    deduplicate dengan set.
    """
    urls = []
    seen = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]

        # Harus pola artikel Detik: /d-XXXXXXX/
        if not re.search(r"/d-\d+/", href):
            continue

        # Abaikan non-artikel
        if any(x in href for x in ["/tag/", "/author/", "/search/", "#", "javascript:"]):
            continue

        # Harus dari domain news.detik.com
        if href.startswith("http") and "news.detik.com" not in href:
            continue

        full = href if href.startswith("http") else urljoin(BASE_URL, href)

        if full not in seen:
            seen.add(full)
            urls.append(full)

    return urls


# ──────────────────────────────────────────────────────────────
# Parse detail artikel
# ──────────────────────────────────────────────────────────────

def parse_tanggal(soup: BeautifulSoup) -> str:
    """Ekstrak tanggal publikasi. Selector: div.detail__date"""
    el = soup.select_one("div.detail__date")
    if el:
        return el.get_text(strip=True)
    # Fallback
    for sel in ["div[class*='date']", "time"]:
        el = soup.select_one(sel)
        if el:
            val = el.get("datetime") or el.get_text(strip=True)
            if val:
                return val
    # Fallback regex
    teks = soup.get_text(" ", strip=True)
    m = re.search(
        r"(Senin|Selasa|Rabu|Kamis|Jumat|Sabtu|Minggu)"
        r",\s+\d{1,2}\s+\w+\s+\d{4}\s+\d{2}:\d{2}\s+WIB",
        teks,
    )
    return m.group(0) if m else ""


def parse_isi(soup: BeautifulSoup) -> str:
    """Ekstrak isi bersih. Selector utama: div.detail__body-text"""
    content = soup.select_one("div.detail__body-text")
    if not content:
        content = soup.select_one("div.itp_bodycontent")
    if not content:
        return ""

    # Buang elemen iklan dan sampah — selector dipisah agar tidak ada koma trailing
    junk_selectors = [
        "script", "style", "iframe",
        "div[class*='ads']", "div[class*='iklan']",
        "div[class*='banner']", "div[class*='promo']",
        "div[class*='related']", "div[class*='rekomendasi']",
        "div[class*='embed']", "div[class*='social']",
        "div[id*='ads']", "div[id*='iklan']",
        "figure", "div.detail__body-tag",
        "div[class*='taboola']", "div[class*='outbrain']",
    ]
    for sel in junk_selectors:
        for junk in content.select(sel):
            junk.decompose()

    paragraphs = [
        p.get_text(strip=True)
        for p in content.find_all("p")
        if p.get_text(strip=True)
    ]
    return "\n\n".join(paragraphs)


def scrape_article(url: str) -> dict | None:
    soup = get_soup(url)
    if not soup:
        return None

    h1    = soup.select_one("h1.detail__title, h1")
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
    cfg       = CONFIG
    results   = []
    seen_urls = set()

    kanals = resolve_kanals(cfg["kanal"])
    dates  = resolve_dates(cfg["tanggal"])

    if not kanals:
        log.error("Tidak ada kanal valid. Periksa CONFIG['kanal'].")
        return []

    log.info(f"Kanal      : {kanals}")
    log.info(f"Tanggal    : {[d or '(terbaru)' for d in dates]}")
    log.info(f"Max halaman: {cfg['max_halaman'] or 'semua'}")
    log.info(f"Total kombinasi: {len(kanals)} kanal × {len(dates)} tanggal")

    for kanal in kanals:
        for tanggal in dates:
            tgl_label = tanggal or "(terbaru)"
            log.info(f"═══ kanal={kanal}  tanggal={tgl_label} ═══")

            url_p1 = build_indeks_url(kanal, tanggal, page=1)
            log.info(f"URL: {url_p1}")
            soup1 = get_soup(url_p1)
            if not soup1:
                continue

            max_page = get_max_page(soup1)
            if cfg["max_halaman"]:
                max_page = min(max_page, cfg["max_halaman"])
            log.info(f"Total halaman: {max_page}")

            for page in range(1, max_page + 1):
                if page == 1:
                    soup = soup1
                else:
                    time.sleep(cfg["delay_halaman"])
                    # PENTING: selalu sertakan tanggal di URL halaman berikutnya
                    soup = get_soup(build_indeks_url(kanal, tanggal, page))
                    if not soup:
                        break

                art_urls = parse_index_links(soup)
                log.info(f"  Halaman {page}/{max_page} → {len(art_urls)} artikel ditemukan")

                if not art_urls:
                    log.info("  Halaman kosong, berhenti.")
                    break

                for idx, art_url in enumerate(art_urls, 1):
                    if art_url in seen_urls:
                        log.info(f"    [{idx}] Duplikat, skip.")
                        continue
                    seen_urls.add(art_url)

                    log.info(f"    [{idx}/{len(art_urls)}] {art_url}")
                    time.sleep(cfg["delay_artikel"])
                    data = scrape_article(art_url)
                    if data:
                        results.append(data)
                        log.info(f"      ✓ {data['judul'][:65]}...")

    with open(cfg["output_file"], "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    log.info(f"\n✓ Selesai! {len(results)} artikel → '{cfg['output_file']}'")
    return results


if __name__ == "__main__":
    main()