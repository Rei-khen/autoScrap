import requests
from bs4 import BeautifulSoup
import csv
import time
from urllib.parse import urljoin

def jalankan_scraper(url_indeks):
    # Header untuk menyamar sebagai browser asli (menghindari blokir)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    try:
        print(f"[*] Mengakses halaman daftar berita: {url_indeks}")
        response = requests.get(url_indeks, headers=headers, timeout=10)
        response.raise_for_status() # Cek jika website error (misal 404 atau 500)
        soup = BeautifulSoup(response.text, 'html.parser')

        # ---------------------------------------------------------
        # PENTING: Ubah bagian ini sesuai struktur website target
        # Cari tag HTML yang membungkus LINK judul berita.
        # Contoh di bawah mencari tag <a> di dalam <h3>
        # ---------------------------------------------------------
        daftar_link = soup.select('h3 a') 
        
        hasil_data = []
        print(f"[+] Menemukan {len(daftar_link)} potensi link berita. Memulai ekstraksi...\n")

        for i, link in enumerate(daftar_link):
            href = link.get('href')
            if not href: continue
            
            # Gabungkan URL jika website menggunakan link relatif (misal: /berita/123)
            url_berita = urljoin(url_indeks, href)
            
            try:
                # Masuk ke URL isi berita
                res_detail = requests.get(url_berita, headers=headers, timeout=10)
                soup_detail = BeautifulSoup(res_detail.text, 'html.parser')

                # Ambil Judul
                judul = soup_detail.find('h1')
                teks_judul = judul.text.strip() if judul else "Tanpa Judul"
                
                # ---------------------------------------------------------
                # PENTING: Ubah bagian ini sesuai struktur website target
                # Cari div yang membungkus isi teks berita.
                # ---------------------------------------------------------
                konten_artikel = soup_detail.find('article') # Atau div class='read__content' dll.
                
                if konten_artikel:
                    # Ambil semua paragraf <p> di dalam artikel
                    paragraf = konten_artikel.find_all('p')
                    isi_berita = "\n".join([p.text.strip() for p in paragraf if p.text.strip()])
                else:
                    isi_berita = "Gagal menemukan struktur isi berita"

                # Simpan ke memori
                hasil_data.append({
                    'Judul': teks_judul,
                    'URL': url_berita,
                    'Isi': isi_berita
                })

                print(f"[{i+1}] Sukses mengambil: {teks_judul[:40]}...")
                
                # Beri jeda 1 detik agar server tidak mengira kita melakukan serangan (DDoS)
                time.sleep(1) 

            except Exception as e:
                print(f"[!] Gagal di link {url_berita}: {e}")

        # Simpan semua data ke file CSV
        if hasil_data:
            with open('.result/kumpulan_berita.csv', 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=['Judul', 'URL', 'Isi'])
                writer.writeheader()
                writer.writerows(hasil_data)
            print("\n[OK] Proses selesai! Data disimpan ke 'kumpulan_berita.csv'")
        else:
            print("\n[!] Tidak ada data yang berhasil diambil.")

    except Exception as e:
        print(f"[X] Gagal mengakses URL utama: {e}")


# =====================================================================
# BAGIAN PENGATURAN PENGGUNA
# =====================================================================

# Masukkan URL di dalam tanda kutip di bawah ini:
TARGET_URL = "https://news.detik.com/" 

# Jalankan program
jalankan_scraper(TARGET_URL)