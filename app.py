import subprocess
import platform
import paramiko
import stat
import io
import os
import uuid
import time
from flask import Flask, render_template, jsonify, request, send_file, redirect, url_for

app = Flask(__name__)

# --- KONFIGURASI ---
TARGET_MAC = "00:00:00:00:00:00"
TARGET_IP = "192.168.x.x"
WIN_USER = "USER"
WIN_PASS = "PASS"
INTERFACE = "eth0"

# --- GLOBAL VARIABLES (OPTIMISASI) ---
ssh_client = None  # Menyimpan koneksi SSH agar tetap hidup (Persistent)
ping_cache = {"status": False, "time": 0} # Menyimpan hasil ping sementara

# --- FUNGSI BANTUAN ---
def is_pc_online():
    global ping_cache
    # Jika data cache masih baru (< 3 detik), pakai cache saja
    if time.time() - ping_cache["time"] < 3:
        return ping_cache["status"]

    try:
        cmd = ['ping', '-c', '1', '-W', '1', TARGET_IP]
        is_online = subprocess.call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0
        
        # Update cache
        ping_cache = {"status": is_online, "time": time.time()}
        return is_online
    except:
        return False

def get_sftp_connection():
    global ssh_client
    
    # 1. Cek apakah koneksi lama masih hidup
    if ssh_client:
        try:
            transport = ssh_client.get_transport()
            if transport and transport.is_active():
                # Koneksi sehat, buka SFTP channel baru di atasnya
                return ssh_client, ssh_client.open_sftp()
        except:
            print("Koneksi SSH terputus, menyambung ulang...")
            ssh_client = None

    # 2. Jika tidak ada/mati, buat koneksi baru
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(TARGET_IP, username=WIN_USER, password=WIN_PASS, timeout=5)
        
        ssh_client = ssh # Simpan ke global
        return ssh, ssh.open_sftp()
    except Exception as e:
        print(f"SFTP Error: {e}")
        return None, None

def get_windows_drives(ssh_client):
    try:
        stdin, stdout, stderr = ssh_client.exec_command('wmic logicaldisk get name')
        output = stdout.read().decode().split()
        drives = [d for d in output if ':' in d]
        return drives
    except Exception as e:
        print(f"Gagal ambil drive: {e}")
        return ['C:']

# --- ROUTES ---
@app.route('/')
def index(): return render_template('dashboard.html')

@app.route('/status')
def status(): return jsonify({"online": is_pc_online()})

@app.route('/action', methods=['POST'])
def action():
    try:
        online = is_pc_online()
        if online:
            # Gunakan koneksi persisten jika ada, atau buat baru sementara
            client = ssh_client if ssh_client else paramiko.SSHClient()
            if not ssh_client:
                client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                client.connect(TARGET_IP, username=WIN_USER, password=WIN_PASS, timeout=3)

            ssh_cmd = f'c:\\windows\\system32\\shutdown.exe /s /t 0'
            stdin, stdout, stderr = client.exec_command(ssh_cmd)
            
            # Kita tidak menunggu output agar respon UI cepat
            return jsonify({"status": "success", "message": "Perintah Shutdown Terkirim", "next_state": "offline"})
        else:
            wake_cmd = ['etherwake', '-i', INTERFACE, TARGET_MAC]
            subprocess.run(wake_cmd, check=True)
            return jsonify({"status": "success", "message": "Perintah WOL Terkirim", "next_state": "online"})
    except Exception as e: return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/files')
def list_files():
    req_path = request.args.get('path', 'root')
    ssh, sftp = get_sftp_connection()
    
    if not sftp: return "Gagal koneksi ke PC", 500
    
    files_list = []
    parent_path = ""
    try:
        if req_path == 'root':
            drives = get_windows_drives(ssh)
            for drive in drives:
                files_list.append({'name': drive, 'path': f"{drive}/", 'type': 'dir', 'size': 0})
            current_path = 'root'
            parent_path = ''
        else:
            req_path = req_path.replace('\\', '/')
            if not req_path.endswith('/'): req_path += '/'
            try:
                for attr in sftp.listdir_attr(req_path):
                    is_dir = stat.S_ISDIR(attr.st_mode)
                    files_list.append({
                        'name': attr.filename,
                        'path': f"{req_path}{attr.filename}",
                        'type': 'dir' if is_dir else 'file',
                        'size': attr.st_size
                    })
                files_list.sort(key=lambda x: (x['type'] != 'dir', x['name'].lower()))
                current_path = req_path
                if req_path.count('/') <= 1 or (req_path.endswith('/') and req_path.count('/') == 1): parent_path = 'root'
                else:
                    parent_path = os.path.dirname(req_path.rstrip('/'))
                    if parent_path.endswith(':'): parent_path += '/'
            except IOError: return f"Akses Ditolak", 403
    except Exception as e: return str(e), 500
    finally:
        # OPTIMISASI: JANGAN tutup SSH (ssh.close), cukup tutup SFTP session
        if sftp: sftp.close()
    
    return jsonify({'current_path': current_path, 'parent_path': parent_path, 'files': files_list})

@app.route('/download')
def download_file():
    file_path = request.args.get('path')
    ssh, sftp = get_sftp_connection()
    if not sftp: return "PC Offline", 500
    try:
        remote_file = sftp.open(file_path, 'rb')
        return send_file(remote_file, as_attachment=True, download_name=os.path.basename(file_path))
    except Exception as e: return str(e), 404
    # Note: sftp session dibiarkan terbuka sebentar untuk streaming, 
    # garbage collector python biasanya akan membersihkannya nanti.

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files: return "No file", 400
    file = request.files['file']
    target_path = request.form.get('path')
    if target_path == 'root': return "Pilih drive dulu", 400
    
    ssh, sftp = get_sftp_connection()
    if not sftp: return "PC Offline", 500
    try:
        full_path = f"{target_path}/{file.filename}".replace('//', '/')
        sftp.putfo(file.stream, full_path)
        return "Success"
    except Exception as e: return str(e), 500
    finally:
        if sftp: sftp.close() # Hanya tutup SFTP

@app.route('/download_folder')
def download_folder():
    folder_path = request.args.get('path')
    ssh, sftp = get_sftp_connection()
    if not ssh: return "PC Offline", 500

    temp_name = f"ControlCenter_{uuid.uuid4().hex[:8]}.zip"
    win_temp_path = f"C:/Windows/Temp/{temp_name}"
    folder_path_clean = folder_path.replace('/', '\\').rstrip('\\')

    try:
        zip_cmd = f"powershell Compress-Archive -Path '{folder_path_clean}' -DestinationPath '{win_temp_path}' -Force"
        stdin, stdout, stderr = ssh.exec_command(zip_cmd)
        if stdout.channel.recv_exit_status() != 0:
            return f"Gagal membuat ZIP. Error: {stderr.read().decode()}", 500

        remote_file = sftp.open(win_temp_path, 'rb')

        def stream_and_remove():
            try:
                yield from remote_file
            finally:
                remote_file.close()
                # Hapus file ZIP temp di Windows
                ssh.exec_command(f"del /F /Q '{win_temp_path}'")
                if sftp: sftp.close() # Tutup sesi SFTP
                # JANGAN tutup SSH client global

        return app.response_class(
            stream_and_remove(),
            headers={
                'Content-Disposition': f'attachment; filename={os.path.basename(folder_path_clean)}.zip',
                'Content-Type': 'application/zip'
            }
        )
    except Exception as e:
        if sftp: sftp.close()
        return str(e), 500

# --- SERVER UTAMA (Waitress Multi-thread) ---
if __name__ == '__main__':
    from waitress import serve
    print("Server berjalan di http://0.0.0.0:5000 (Multi-threaded)")
    # Threads = 6 memungkinkan 6 user/request diproses bersamaan
    serve(app, host='0.0.0.0', port=5000, threads=6)