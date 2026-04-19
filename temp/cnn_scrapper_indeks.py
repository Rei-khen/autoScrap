"""
CNN Indonesia Scraper - Mode INDEKS
====================================
Scraping berita berdasarkan KANAL dan TANGGAL.
URL indeks dibangun otomatis, tidak perlu diisi manual.

Penggunaan:
  python cnn_scraper_indeks.py

Output: cnn_indeks_result.json
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
    # Pilihan: "semua" | "nasional" | "internasional" | "ekonomi" |
    #          "olahraga" | "teknologi" | "otomotif" | "edukasi" |
    #          "hiburan" | "gaya-hidup" | "tv"
    #
    # Contoh satu kanal  : "kanal": "nasional"
    # Contoh multi kanal : "kanal": ["nasional", "ekonomi", "teknologi"]
    # Contoh semua kanal : "kanal": "semua"
    "kanal": "nasional",

    # Tanggal yang ingin di-scrape (format YYYY-MM-DD).
    #
    # Satu hari    : "tanggal": "2026-04-18"
    # Range        : "tanggal": ["2026-04-12", "2026-04-18"]  (inklusif)
    # Tanpa filter : "tanggal": None  → ambil berita terbaru tanpa filter tanggal
    "tanggal": "2026-04-18",

    # Batas maksimal halaman per kombinasi kanal+tanggal (None = semua halaman)
    "max_halaman": None,

    # Jeda antar request (detik) — jangan terlalu kecil
    "delay_halaman": 1.5,
    "delay_artikel": 1.0,

    # File output
    "output_file": "./result/cnn_indeks_result.json",
}
# ─────────────────────────────────────────────────────────────

# Mapping nama kanal → (path indeks, ID)
KANAL_MAP = {
    "semua":         ("indeks",               "2"),
    "nasional":      ("nasional/indeks",       "3"),
    "internasional": ("internasional/indeks",  "6"),
    "ekonomi":       ("ekonomi/indeks",        "5"),
    "olahraga":      ("olahraga/indeks",       "7"),
    "teknologi":     ("teknologi/indeks",      "8"),
    "otomotif":      ("otomotif/indeks",       "577"),
    "edukasi":       ("edukasi/indeks",        "559"),
    "hiburan":       ("hiburan/indeks",        "9"),
    "gaya-hidup":    ("gaya-hidup/indeks",     "10"),
    "tv":            ("tv/indeks",             "398"),
}

BASE_URL   = "https://www.cnnindonesia.com"
MEDIA_NAME = "CNN Indonesia"

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
# Validasi & normalisasi CONFIG
# ──────────────────────────────────────────────────────────────

def resolve_kanals(kanal_cfg) -> list:
    """Normalisasi input kanal → list nama kanal yang valid."""
    if isinstance(kanal_cfg, str):
        kanal_cfg = [kanal_cfg]
    result = []
    for k in kanal_cfg:
        k = k.strip().lower()
        if k not in KANAL_MAP:
            log.warning(
                f"Kanal '{k}' tidak dikenal, dilewati. "
                f"Pilihan valid: {list(KANAL_MAP.keys())}"
            )
            continue
        result.append(k)
    return result


def resolve_dates(tanggal_cfg) -> list:
    """
    Normalisasi input tanggal → list tanggal format 'YYYY/MM/DD' (format CNN).
      None              → [None]   (tanpa filter tanggal)
      "YYYY-MM-DD"      → ["YYYY/MM/DD"]
      ["YYYY-MM-DD", "YYYY-MM-DD"] → range inklusif
    """
    if tanggal_cfg is None:
        return [None]

    fmt_in  = "%Y-%m-%d"
    fmt_out = "%Y/%m/%d"

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

    raise ValueError(
        f"Format 'tanggal' tidak valid: {tanggal_cfg!r}. "
        "Gunakan string 'YYYY-MM-DD' atau list dua elemen untuk range."
    )


# ──────────────────────────────────────────────────────────────
# URL builder
# ──────────────────────────────────────────────────────────────

def build_indeks_url(kanal: str, tanggal: str | None, page: int = 1) -> str:
    """
    Bangun URL indeks CNN Indonesia dari nama kanal + tanggal.

    Contoh output:
      https://www.cnnindonesia.com/nasional/indeks/3
      https://www.cnnindonesia.com/nasional/indeks/3?date=2026/04/18
      https://www.cnnindonesia.com/nasional/indeks/3?date=2026/04/18&page=2
      https://www.cnnindonesia.com/indeks/2?date=2026/04/18          (semua kanal)
    """
    path, id_ = KANAL_MAP[kanal]
    base = f"{BASE_URL}/{path}/{id_}"

    params = {}
    if tanggal:
        params["date"] = tanggal
    if page > 1:
        params["page"] = str(page)

    if params:
        # safe='/' agar tanggal "2026/04/18" tidak di-encode jadi "2026%2F04%2F18"
        return f"{base}?{urlencode(params, safe='/')}"
    return base


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
    log.error(f"Gagal mengambil: {url}")
    return None


# ──────────────────────────────────────────────────────────────
# Pagination
# ──────────────────────────────────────────────────────────────

def get_max_page(soup: BeautifulSoup) -> int:
    """Deteksi total halaman dari link pagination."""
    max_p = 1
    for a in soup.find_all("a", href=True):
        m = re.search(r"[?&]page=(\d+)", a["href"])
        if m:
            max_p = max(max_p, int(m.group(1)))
    return max_p


# ──────────────────────────────────────────────────────────────
# Parse daftar artikel dari halaman indeks
# ──────────────────────────────────────────────────────────────

def parse_index_links(soup: BeautifulSoup) -> list:
    """Kumpulkan URL artikel dari halaman indeks."""
    urls, seen = [], set()
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


# ──────────────────────────────────────────────────────────────
# Parse detail artikel
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
        teks,
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
            soup1  = get_soup(url_p1)
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