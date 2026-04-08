import requests
from bs4 import BeautifulSoup
import json  # Library untuk memproses JSON
import time
import os
from urllib.parse import urljoin

def jalankan_scraper(url_indeks):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    try:
        print(f"[*] Mengakses halaman daftar berita: {url_indeks}")
        response = requests.get(url_indeks, headers=headers, timeout=10)
        response.raise_for_status() 
        soup = BeautifulSoup(response.text, 'html.parser')

        # Mencari tag judul berita di halaman indeks
        daftar_link = soup.select('h3 a') 
        
        hasil_data = []
        print(f"[+] Menemukan {len(daftar_link)} potensi link berita. Memulai ekstraksi...\n")

        for i, link in enumerate(daftar_link):
            href = link.get('href')
            if not href: continue
            
            url_berita = urljoin(url_indeks, href)
            
            try:
                res_detail = requests.get(url_berita, headers=headers, timeout=10)
                soup_detail = BeautifulSoup(res_detail.text, 'html.parser')

                # 1. Ambil Judul
                judul = soup_detail.find('h1')
                teks_judul = judul.text.strip() if judul else "Tanpa Judul"
                
                # 2. Ambil Isi Berita
                konten_artikel = soup_detail.find('div', class_='detail__body-text')
                
                if konten_artikel:
                    # Bersihkan elemen sampah (Iklan, Video, dll)
                    class_sampah = ['noncontent', 'parallaxindetail', 'staticdetail_container']
                    for sampah in konten_artikel.find_all('div', class_=class_sampah):
                        sampah.decompose()
                        
                    for elemen_tersembunyi in konten_artikel.find_all(['style', 'script']):
                        elemen_tersembunyi.decompose()

                    # Sedot seluruh teks yang tersisa
                    isi_berita = konten_artikel.get_text(separator='\n\n', strip=True)
                else:
                    isi_berita = "Gagal menemukan struktur isi berita"

                # 3. Simpan ke format Dictionary Python (yang akan diubah jadi JSON)
                hasil_data.append({
                    'Judul': teks_judul,
                    'URL': url_berita,
                    'Isi': isi_berita
                })

                print(f"[{i+1}] Sukses mengambil: {teks_judul[:40]}...")
                time.sleep(1) 

            except Exception as e:
                print(f"[!] Gagal di link {url_berita}: {e}")

        # ---------------------------------------------------------
        # PERUBAHAN: Menyimpan data ke dalam file JSON
        # ---------------------------------------------------------
        if hasil_data:
            os.makedirs('./result', exist_ok=True)
            file_path = './result/kumpulan_berita.json' # Ekstensi diubah ke .json
            
            with open(file_path, 'w', encoding='utf-8') as f:
                # indent=4 membuat JSON lebih mudah dibaca manusia (pretty print)
                # ensure_ascii=False memastikan karakter bahasa Indonesia/unik tidak berubah jadi kode
                json.dump(hasil_data, f, indent=4, ensure_ascii=False)
                
            print(f"\n[OK] Proses selesai! Data disimpan ke '{file_path}'")
        else:
            print("\n[!] Tidak ada data yang berhasil diambil.")

    except Exception as e:
        print(f"[X] Gagal mengakses URL utama: {e}")


# =====================================================================
# BAGIAN PENGATURAN PENGGUNA
# =====================================================================
TARGET_URL = "https://news.detik.com/" 
jalankan_scraper(TARGET_URL)