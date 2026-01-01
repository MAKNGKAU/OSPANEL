## OSPANEL - Control Center OSIS 🎛️
OSPANEL adalah sistem manajemen jarak jauh berbasis web yang dirancang khusus untuk Sekretariat OSIS SMK "SORE" Tulungagung. Sistem ini berfungsi sebagai jembatan (middleware) yang memungkinkan pengurus untuk menyalakan komputer, mengakses file, dan memantau status perangkat dari jarak jauh melalui jaringan lokal maupun internet (VPN).

###🚀 Fitur Utama
Remote Power Control: Menyalakan PC yang mati total (Wake-on-LAN) dan mematikannya (Remote Shutdown).

Web File Explorer: Menjelajahi, Mengunduh (File/Folder Zip), dan Mengunggah file tanpa akses fisik.

Persistent Connection: Koneksi SSH/SFTP yang dioptimalkan untuk kecepatan instan.

Smart Polling: Mekanisme hemat daya yang tidak membebani server/klien saat tab tidak aktif.

Secure Access: Terintegrasi dengan Tailscale untuk akses HTTPS aman dari mana saja.

###🛠️ Arsitektur Sistem
Controller (Linux/STB/Raspi): Menjalankan server Python (Flask/Waitress).

Target (Windows PC): Komputer sekretariat yang dikontrol.

Network: Tailscale (VPN Mesh) & LAN.

###📋 Prasyarat (Requirements)

1. Perangkat Controller (Server)
   OS: Linux (OpenWRT / Armbian / Ubuntu Server / Raspbian).

Python 3.8 atau lebih baru.

Koneksi LAN ke router yang sama dengan PC Target (Wajib untuk fitur Wake-on-LAN).

2. Perangkat Target (PC Windows)
   OpenSSH Server: Harus terinstal dan aktif.

Wake-on-LAN (WOL): Harus diaktifkan di BIOS dan Pengaturan Network Adapter.

Static IP: Disarankan menggunakan IP Statis

###⚙️ Instalasi & Konfigurasi
Langkah 1: Persiapan PC Target (Windows)
Sebelum menjalankan aplikasi, pastikan PC Windows sudah siap menerima perintah:

Instal OpenSSH Server:

Buka Settings > Apps > Optional features.

Cari "OpenSSH Server" dan instal.

Buka Services (services.msc), cari "OpenSSH SSH Server", set ke Automatic dan klik Start.

Aktifkan WOL:

Masuk ke BIOS saat booting, cari menu "Power Management" > aktifkan "Wake on LAN".

Di Windows, buka Device Manager > Network adapters > Klik kanan Driver LAN > Properties > Tab Power Management > Centang "Allow this device to wake the computer".

Langkah 2: Instalasi Aplikasi di Controller (Linux)
Clone Repository:

```Bash
git clone https://github.com/MAKNGKAU/OSPANEL.git
cd OSPANEL
```

Install Dependencies: Disarankan menggunakan Virtual Environment, tapi untuk STB/Embedded bisa langsung:

```Bash
sudo apt install python3-flask
sudo apt install python3-paramiko
sudo apt install python3-waitress
```

Pastikan library etherwake atau wakeonlan sudah terinstal di Linux Anda (sudo apt install etherwake atau opkg install etherwake).

Konfigurasi Kredensial: Edit file app.py menggunakan nano atau teks editor lain:

```Bash
nano app.py
```

Sesuaikan bagian berikut dengan data PC Windows Anda:

# --- KONFIGURASI ---

TARGET_MAC = "XX:XX:XX:XX:XX:XX" # MAC Address LAN PC Windows
TARGET_IP = "192.168.x.x" # IP Address PC Windows
WIN_USER = "USER" # Username Login Windows
WIN_PASS = "PASS" # Password Login Windows
INTERFACE = "eth0" # Interface LAN di Linux (cek dengan `ifconfig`)
Simpan dengan CTRL+X, lalu Y.

Langkah 3: Uji Coba Manual
Jalankan server untuk memastikan tidak ada error:

```Bash
python3 app.py
```

Akses via browser: http://<IP-LINUX>:5000. Jika berhasil, tekan CTRL+C untuk berhenti.

###🤖 Membuat Auto-Start Service (Systemd)
Agar aplikasi berjalan otomatis saat STB/Server dinyalakan, kita akan membuat service Linux.

Buat File Service:

```Bash
sudo nano /etc/systemd/system/OSPANEL.service
```

Isi File Service: Sesuaikan path /home/user/OSPANEL dengan lokasi folder Anda.

```Ini, TOML
[Unit]
Description=OSPANEL Control Center Service
After=network.target network-online.target

[Service]
User=root
WorkingDirectory=/home/user/OSPANEL

# Ganti path python3 jika perlu (cek dengan `which python3`)

ExecStart=/usr/bin/python3 /home/user/OSPANEL/app.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Aktifkan Service:

```Bash
sudo systemctl daemon-reload
sudo systemctl enable OSPANEL
sudo systemctl start OSPANEL
```

Cek Status:

```Bash
sudo systemctl status OSPANEL
```

Jika statusnya active (running), berarti server sudah berjalan otomatis.

###🌐 Konfigurasi Tailscale & HTTPS
Untuk akses aman dari luar jaringan menggunakan nama domain cantik (MagicDNS) dan HTTPS.

1. Install & Login Tailscale
   Jika belum terinstal di Linux Controller:

```Bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
```

Login menggunakan link yang muncul di terminal.

2. Mengaktifkan Tailscale Serve (HTTPS Proxy)
   Fitur ini akan membelokkan port 5000 aplikasi ke port 443 (HTTPS) milik Tailscale.

Jalankan perintah berikut di terminal Linux Controller:

```Bash
sudo tailscale serve --bg --https=443 http://localhost:5000
```

Penjelasan:

--bg: Menjalankan di background.

--https=443: Membuka akses HTTPS port 443.

http://localhost:5000: Mengarahkan trafik ke aplikasi OSPANEL kita.

3. Akses Final
   Sekarang, Anda bisa mengakses OSPANEL dari mana saja (selama terhubung Tailscale) dengan alamat:

https://nama-hostname-linux-anda.tailnet-name.ts.net

Cek perintah tailscale status untuk melihat nama lengkap hostname Anda.
