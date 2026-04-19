import requests
from bs4 import BeautifulSoup
import json
import time
import os
from urllib.parse import urljoin

def jalankan_scraper_otomatis(url_template):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    hasil_data = []
    
    # 1. Kita tentukan titik awalnya
    halaman = 1 

    # 2. Gunakan While True agar program terus berjalan mencari halaman selanjutnya
    while True: 
        url_indeks = url_template.format(halaman)
        
        try:
            print(f"\n==================================================")
            print(f"[*] Mengakses Halaman {halaman}: {url_indeks}")
            print(f"==================================================")
            
            response = requests.get(url_indeks, headers=headers, timeout=10)
            response.raise_for_status() 
            soup = BeautifulSoup(response.text, 'html.parser')

            daftar_link = soup.select('h3 a') 
            
            # ---------------------------------------------------------
            # 3. KONDISI BERHENTI (REMBRAKE)
            # Jika 'daftar_link' kosong (panjangnya 0), berarti kita 
            # sudah melewati halaman terakhir. Hentikan perulangan!
            # ---------------------------------------------------------
            if not daftar_link:
                print(f"[!] Halaman {halaman} kosong / tidak ada berita. Proses crawling dihentikan otomatis.")
                break # Perintah 'break' akan menghancurkan perulangan 'while True'
                
            print(f"[+] Menemukan {len(daftar_link)} link berita. Memulai ekstraksi...")

            for i, link in enumerate(daftar_link):
                href = link.get('href')
                if not href: continue
                
                url_berita = urljoin(url_indeks, href)
                
                try:
                    res_detail = requests.get(url_berita, headers=headers, timeout=10)
                    soup_detail = BeautifulSoup(res_detail.text, 'html.parser')

                    judul = soup_detail.find('h1')
                    teks_judul = judul.text.strip() if judul else "Tanpa Judul"
                    
                    tanggal = soup_detail.find('div', class_='detail__date')
                    teks_tanggal = tanggal.text.strip() if tanggal else "Tanggal tidak ditemukan"
                    
                    konten_artikel = soup_detail.find('div', class_='detail__body-text')
                    
                    if konten_artikel:
                        class_sampah = ['noncontent', 'parallaxindetail', 'staticdetail_container']
                        for sampah in konten_artikel.find_all('div', class_=class_sampah):
                            sampah.decompose()
                            
                        for elemen_tersembunyi in konten_artikel.find_all(['style', 'script']):
                            elemen_tersembunyi.decompose()

                        isi_berita = konten_artikel.get_text(separator='\n\n', strip=True)
                    else:
                        isi_berita = "Gagal menemukan struktur isi berita"

                    hasil_data.append({
                        'Judul': teks_judul,
                        'Tanggal': teks_tanggal,
                        'URL': url_berita,
                        'Isi': isi_berita
                    })

                    print(f"  [{i+1}] Sukses: {teks_judul[:40]}...")
                    time.sleep(1) 

                except Exception as e:
                    print(f"  [!] Gagal di link {url_berita}: {e}")
                    
            # ---------------------------------------------------------
            # 4. LANJUT KE HALAMAN BERIKUTNYA
            # Tambahkan angka halaman saat ini dengan 1, lalu ulangi loop
            # ---------------------------------------------------------
            halaman += 1 
            time.sleep(2) # Istirahat 2 detik sebelum pindah halaman indeks

        except Exception as e:
            print(f"[X] Gagal mengakses URL halaman {halaman}: {e}")
            break 

    # Simpan ke JSON setelah While Loop selesai (Break)
    if hasil_data:
        os.makedirs('./result', exist_ok=True)
        file_path = './result/kumpulan_berita.json'
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(hasil_data, f, indent=4, ensure_ascii=False)
            
        print(f"\n[OK] LUAR BIASA! {len(hasil_data)} Data dari seluruh halaman berhasil disimpan ke '{file_path}'")
    else:
        print("\n[!] Tidak ada data yang berhasil diambil sama sekali.")


# =====================================================================
# BAGIAN PENGATURAN PENGGUNA
# =====================================================================
# Tidak perlu lagi memasukkan batas maksimal halaman!
TARGET_URL = "https://www.detik.com/search/searchnews?query=politik&result_type=latest&fromdatex=12/04/2026&todatex=12/04/2026" 
jalankan_scraper_otomatis(TARGET_URL)