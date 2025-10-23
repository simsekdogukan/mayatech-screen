#!/bin/bash
###############################################################################
# Mayatech Ekran Yöneticisi - Otomatik Kurulum Scripti (v2.0)
# Departman: Mayatech Bilgi İşlem
# Sürüm: 2.0 - Tam Otomatik Kurulum
###############################################################################

set -e  # Hata durumunda dur

echo "=========================================="
echo "Mayatech Ekran Yöneticisi Kurulumu v2.0"
echo "=========================================="
echo ""

# Root kontrolü
if [ "$EUID" -ne 0 ]; then
    echo "Lütfen bu scripti sudo ile çalıştırın: sudo bash setup.sh"
    exit 1
fi

echo "[1/10] Eski proje temizleniyor..."
# Eski servisi durdur ve kaldır
systemctl stop mayatech-screen-manager 2>/dev/null || true
systemctl disable mayatech-screen-manager 2>/dev/null || true
systemctl daemon-reload

# Eski proje klasörünü sil
rm -rf /opt/mayatech-screen-manager 2>/dev/null || true
rm -rf /home/*/mayatech-screen-manager 2>/dev/null || true
rm -rf /root/mayatech-screen-manager 2>/dev/null || true

# Eski systemd servis dosyasını sil
rm -f /etc/systemd/system/mayatech-screen-manager.service

echo "[2/10] Sistem paketleri güncelleniyor..."
apt-get update -qq

echo "[3/10] Python ve pip yükleniyor..."
apt-get install -y python3 python3-pip python3-venv git sqlite3 > /dev/null 2>&1

echo "[4/10] Güvenlik ayarları yapılıyor..."
# Firewall ayarları
ufw --force enable
ufw allow 22/tcp    # SSH
ufw allow 8080/tcp  # Mayatech uygulaması
ufw --force reload

# Sistem güvenlik güncellemeleri
apt-get install -y unattended-upgrades
echo 'Unattended-Upgrade::Automatic-Reboot "false";' > /etc/apt/apt.conf.d/50unattended-upgrades

echo "[5/10] Yeni proje indiriliyor..."
# Proje klasörünü oluştur
mkdir -p /opt/mayatech-screen-manager
cd /opt/mayatech-screen-manager

# Eğer klasör boşsa klonla, değilse git pull yap
if [ -z "$(ls -A /opt/mayatech-screen-manager)" ]; then
    # Klasör boşsa klonla
    git clone https://github.com/simsekdogukan/mayatech-screen.git .
else
    # Klasör doluysa git pull yap
    git init
    git remote add origin https://github.com/simsekdogukan/mayatech-screen.git
    git pull origin main
fi

echo "[6/10] Python sanal ortam oluşturuluyor..."
python3 -m venv venv

echo "[7/10] Python paketleri yükleniyor..."
source venv/bin/activate
pip install --upgrade pip > /dev/null 2>&1
pip install -r requirements.txt > /dev/null 2>&1

echo "[8/10] Gerekli klasörler oluşturuluyor..."
mkdir -p static/pdfs
chmod 755 static/pdfs

echo "[9/10] Veritabanı sıfırlanıyor..."
# Eski veritabanını sil
rm -f mayatech.db
# Yeni veritabanı otomatik oluşturulacak (app.py'de init_db() fonksiyonu var)

echo "[10/12] İzinler ayarlanıyor..."
# Proje klasörü izinlerini düzelt
chown -R $SUDO_USER:$SUDO_USER /opt/mayatech-screen-manager
chmod -R 755 /opt/mayatech-screen-manager

# Veritabanı dosyası için yazma izni ver
touch /opt/mayatech-screen-manager/mayatech.db
chown $SUDO_USER:$SUDO_USER /opt/mayatech-screen-manager/mayatech.db
chmod 664 /opt/mayatech-screen-manager/mayatech.db

echo "[11/12] Veritabanı tabloları oluşturuluyor..."
# Veritabanı tablolarını oluştur
cd /opt/mayatech-screen-manager
source venv/bin/activate
python3 -c "
import sqlite3
conn = sqlite3.connect('mayatech.db')
conn.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    )
''')
conn.execute('''
    CREATE TABLE IF NOT EXISTS screens (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        slug TEXT UNIQUE NOT NULL,
        sheets_url TEXT NOT NULL,
        pdf_path TEXT,
        location TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
''')
conn.execute('''
    CREATE TABLE IF NOT EXISTS activity_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        action TEXT NOT NULL,
        details TEXT,
        ip_address TEXT NOT NULL,
        user_agent TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
''')
conn.execute('INSERT OR REPLACE INTO users (username, password) VALUES (?, ?)', ('solpro', 'solpro'))
conn.commit()
conn.close()
print('Veritabanı tabloları oluşturuldu ve varsayılan kullanıcı eklendi.')
"

echo "[12/12] Systemd servisi oluşturuluyor..."
INSTALL_DIR=$(pwd)
cat > /etc/systemd/system/mayatech-screen-manager.service << SERVICEEOF
[Unit]
Description=Mayatech Ekran Yöneticisi
After=network.target

[Service]
Type=simple
User=$SUDO_USER
WorkingDirectory=$INSTALL_DIR
Environment="PATH=$INSTALL_DIR/venv/bin"
ExecStart=$INSTALL_DIR/venv/bin/python3 $INSTALL_DIR/app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
SERVICEEOF

echo "[13/13] Servis başlatılıyor..."
systemctl daemon-reload
systemctl enable mayatech-screen-manager
systemctl start mayatech-screen-manager

# IP adresini al
SERVER_IP=$(hostname -I | awk '{print $1}')

echo ""
echo "=========================================="
echo "KURULUM TAMAMLANDI"
echo "=========================================="
echo ""
echo "Admin Paneli: http://$SERVER_IP:8080"
echo "Kullanici: solpro"
echo "Sifre: solpro"
echo ""
echo "Servis Durumu:"
systemctl status mayatech-screen-manager --no-pager -l
echo ""
echo "Yararli Komutlar:"
echo "  Servis yeniden baslat: sudo systemctl restart mayatech-screen-manager"
echo "  Servis durumu: sudo systemctl status mayatech-screen-manager"
echo "  Servis loglari: sudo journalctl -u mayatech-screen-manager -f"
echo ""
echo "Proje calisiyor. Tarayicida http://$SERVER_IP:8080 adresine gidin."
echo ""
echo "NOT: Sunucu kapanip acilsa bile program otomatik baslayacak."
echo "=========================================="