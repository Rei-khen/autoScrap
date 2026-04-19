"""
CNN Indonesia News Scraper
==========================
Mengambil daftar berita dari halaman indeks CNN Indonesia
dan menyimpan hasilnya dalam format JSON.

Penggunaan:
    python cnn_indonesia_scraper.py

Konfigurasi bisa diubah di bagian CONFIG di bawah.
"""

import requests
from bs4 import BeautifulSoup
import json
import time
import re
import logging
from datetime import datetime, timedelta
from urllib.parse import urljoin

# ─────────────────────────────────────────────
# CONFIG – sesuaikan di sini
# ─────────────────────────────────────────────
CONFIG = {
    # Kanal yang tersedia (sesuaikan slug & ID):
    #   nasional=3, hukum-kriminal=11, ekonomi=2, politik=4
    #   teknologi=16, olahraga=6, hiburan=8, gaya-hidup=10
    #   peristiwa=18
    "kanal_slug": "nasional",
    "kanal_id":   3,

    # Rentang tanggal (format YYYY/MM/DD)
    "tanggal_mulai":   "2026/04/15",
    "tanggal_selesai": "2026/04/15",

    # Jeda antar request (detik) – jangan terlalu cepat
    "delay_antar_halaman":  1.5,
    "delay_antar_artikel":  1.0,

    # True  → buka setiap artikel dan ambil isi lengkapnya
    # False → simpan metadata dari halaman indeks saja (lebih cepat)
    "ambil_isi_artikel": True,

    # File output
    "output_file": "../result/cnn_indonesia_berita.json",
}
# ─────────────────────────────────────────────

BASE_URL = "https://www.cnnindonesia.com"

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
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8",
    "Referer": BASE_URL,
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)

# Pola URL artikel CNN Indonesia:
# /nasional/20260407132552-12-1345108/judul-artikel
ARTICLE_URL_PATTERN = re.compile(r"/[\w-]+/\d{14}-\d+-\d+/")


# ──────────────────────────────────────────────────────────────
# Utilitas
# ──────────────────────────────────────────────────────────────

def get_soup(url: str, retries: int = 3):
    """Ambil HTML dari URL, return BeautifulSoup atau None jika gagal."""
    for attempt in range(1, retries + 1):
        try:
            resp = SESSION.get(url, timeout=15)
            resp.raise_for_status()
            return BeautifulSoup(resp.text, "html.parser")
        except requests.RequestException as exc:
            log.warning(f"Percobaan {attempt}/{retries} gagal untuk {url}: {exc}")
            if attempt < retries:
                time.sleep(3)
    log.error(f"Gagal mengambil: {url}")
    return None


def daterange(start: str, end: str):
    """Generator tanggal dari start s/d end (format YYYY/MM/DD)."""
    fmt = "%Y/%m/%d"
    current = datetime.strptime(start, fmt)
    stop    = datetime.strptime(end, fmt)
    while current <= stop:
        yield current.strftime(fmt)
        current += timedelta(days=1)


# ──────────────────────────────────────────────────────────────
# Deteksi total halaman
# ──────────────────────────────────────────────────────────────

def get_total_pages(soup: BeautifulSoup) -> int:
    """
    Deteksi total halaman dari link pagination CNN Indonesia.
    Link pagination mengandung ?page=N atau &page=N.
    """
    max_page = 1
    for a in soup.find_all("a", href=True):
        match = re.search(r"[?&]page=(\d+)", a["href"])
        if match:
            num = int(match.group(1))
            if num > max_page:
                max_page = num
    return max_page


# ──────────────────────────────────────────────────────────────
# Scraping halaman indeks → daftar artikel
# ──────────────────────────────────────────────────────────────

def extract_articles_from_soup(soup: BeautifulSoup, tanggal: str, page: int) -> list:
    """
    Parse daftar artikel dari BeautifulSoup halaman indeks.

    Struktur halaman indeks CNN Indonesia:
      <a href="/nasional/20260407...-12-xxx/judul">
        <img src="...">
        <h2>Judul Artikel</h2>
        <span>Kategori • N jam yang lalu</span>
      </a>
    """
    articles = []
    seen_urls = set()

    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]

        # Filter hanya URL artikel (bukan menu, navigasi, iklan, dll.)
        if not ARTICLE_URL_PATTERN.search(href):
            continue

        # Abaikan link video/foto/infografis
        if any(x in href for x in ["/tv/", "/foto/", "/infografis/", "/video/"]):
            continue

        full_url = urljoin(BASE_URL, href)

        # Hindari duplikat
        if full_url in seen_urls:
            continue
        seen_urls.add(full_url)

        # Judul – ambil dari <h2> atau <h3> di dalam <a>
        title_el = a_tag.find(["h2", "h3"])
        if title_el:
            judul = title_el.get_text(strip=True)
        else:
            # Fallback: teks <a> setelah buang elemen img
            cloned = BeautifulSoup(str(a_tag), "html.parser")
            for img in cloned.find_all("img"):
                img.decompose()
            judul = cloned.get_text(strip=True)

        if not judul or len(judul) < 5:
            continue

        # Thumbnail
        img_el = a_tag.find("img")
        thumbnail = None
        if img_el:
            thumbnail = (
                img_el.get("src")
                or img_el.get("data-src")
                or img_el.get("data-lazy-src")
            )

        # Kategori & waktu tayang dari teks span di dalam <a>
        kategori = None
        waktu    = None
        for elem in a_tag.find_all(["span", "div"]):
            teks = elem.get_text(strip=True)
            if "•" in teks:
                parts    = teks.split("•", 1)
                kategori = parts[0].strip()
                waktu    = parts[1].strip()
                break
            elif teks and not any(c.isdigit() for c in teks) and 2 < len(teks) < 50:
                if kategori is None:
                    kategori = teks

        articles.append({
            "judul":          judul,
            "url":            full_url,
            "kategori":       kategori,
            "waktu_tayang":   waktu,
            "thumbnail":      thumbnail,
            "tanggal_indeks": tanggal,
            "halaman":        page,
        })

    return articles


def scrape_index_page(kanal_slug: str, kanal_id: int, tanggal: str, page: int):
    """Ambil satu halaman indeks, return (soup, articles)."""
    url = f"{BASE_URL}/{kanal_slug}/indeks/{kanal_id}?date={tanggal}&page={page}"
    log.info(f"Scraping indeks → {url}")
    soup = get_soup(url)
    if soup is None:
        return None, []
    articles = extract_articles_from_soup(soup, tanggal, page)
    log.info(f"  Ditemukan {len(articles)} artikel di halaman {page}")
    return soup, articles


# ──────────────────────────────────────────────────────────────
# Scraping isi artikel
# ──────────────────────────────────────────────────────────────

def scrape_article_detail(url: str) -> dict:
    """Ambil isi lengkap satu artikel."""
    log.info(f"  Detail → {url}")
    soup = get_soup(url)
    if soup is None:
        return {}

    detail = {}

    # Judul
    h1 = soup.select_one("h1")
    detail["judul"] = h1.get_text(strip=True) if h1 else None

    # Waktu publikasi
    waktu_el = soup.select_one("div.text-cnn_grey, time")
    detail["waktu_publikasi"] = waktu_el.get_text(strip=True) if waktu_el else None

    # Penulis / sumber
    penulis_el = soup.select_one("span.text-cnn_red")
    detail["penulis"] = penulis_el.get_text(strip=True) if penulis_el else None

    # Gambar utama
    fig_img = soup.select_one("div.detail-image figure img, figure img")
    if fig_img:
        detail["gambar_utama"] = fig_img.get("src") or fig_img.get("data-src")
        caption_el = soup.select_one("figcaption")
        detail["keterangan_gambar"] = caption_el.get_text(strip=True) if caption_el else None
    else:
        detail["gambar_utama"]      = None
        detail["keterangan_gambar"] = None

    # Isi artikel
    content_div = soup.select_one("div.detail-text")
    if content_div:
        # Buang elemen iklan, tabel sisip, script, style, dll.
        for junk in content_div.select(
            "div.paradetail, div[class*='ads'], table.linksisip, "
            "script, style, center, div[id*='gpt'], iframe, "
            "div[data-type], a.embed"
        ):
            junk.decompose()

        paragraphs = [
            p.get_text(strip=True)
            for p in content_div.find_all("p")
            if p.get_text(strip=True)
        ]
        detail["isi"]             = "\n\n".join(paragraphs)
        detail["jumlah_paragraf"] = len(paragraphs)
    else:
        detail["isi"]             = None
        detail["jumlah_paragraf"] = 0

    # Tags
    tags = []
    for tag_el in soup.select("a[href*='/tag/']"):
        t = tag_el.get_text(strip=True)
        if t:
            tags.append(t)
    detail["tags"] = list(dict.fromkeys(tags))

    return detail


# ──────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────

def main():
    cfg = CONFIG
    all_articles = []

    for tanggal in daterange(cfg["tanggal_mulai"], cfg["tanggal_selesai"]):
        log.info(f"═══ Tanggal: {tanggal} ═══")

        # Ambil halaman pertama
        soup_p1, articles_p1 = scrape_index_page(
            cfg["kanal_slug"], cfg["kanal_id"], tanggal, page=1
        )
        total_pages = get_total_pages(soup_p1) if soup_p1 else 1
        log.info(f"Total halaman terdeteksi: {total_pages}")

        articles_all_pages = list(articles_p1)

        # Halaman 2, 3, dst.
        for page in range(2, total_pages + 1):
            time.sleep(cfg["delay_antar_halaman"])
            _, arts = scrape_index_page(
                cfg["kanal_slug"], cfg["kanal_id"], tanggal, page
            )
            if not arts:
                log.info(f"Halaman {page} kosong, berhenti.")
                break
            articles_all_pages.extend(arts)

        log.info(f"Total artikel untuk {tanggal}: {len(articles_all_pages)}")

        # Ambil detail isi artikel (opsional)
        if cfg["ambil_isi_artikel"]:
            for idx, art in enumerate(articles_all_pages, 1):
                log.info(f"[{idx}/{len(articles_all_pages)}] Mengambil detail...")
                time.sleep(cfg["delay_antar_artikel"])
                detail = scrape_article_detail(art["url"])
                art.update(detail)

        all_articles.extend(articles_all_pages)

    # Simpan ke JSON
    output = {
        "metadata": {
            "kanal":          cfg["kanal_slug"],
            "tanggal_mulai":  cfg["tanggal_mulai"],
            "tanggal_selesai":cfg["tanggal_selesai"],
            "total_artikel":  len(all_articles),
            "di_scrape_pada": datetime.now().isoformat(),
        },
        "artikel": all_articles,
    }

    with open(cfg["output_file"], "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    log.info(f"✓ Selesai! {len(all_articles)} artikel disimpan ke '{cfg['output_file']}'")


if __name__ == "__main__":
    main()