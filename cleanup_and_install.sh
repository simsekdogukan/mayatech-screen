#!/bin/bash
###############################################################################
# Mayatech Ekran Yöneticisi - Temizlik ve Yeniden Kurulum Scripti
# Bu script eski projeyi siler ve yeni versiyonu kurar
###############################################################################

set -e  # Hata durumunda dur

echo "=========================================="
echo "MAYATECH TEMIZLIK VE YENIDEN KURULUM"
echo "=========================================="
echo ""

# Root kontrolü
if [ "$EUID" -ne 0 ]; then
    echo "Lutfen bu scripti sudo ile calistirin: sudo bash cleanup_and_install.sh"
    exit 1
fi

echo "[1/8] Eski servis durduruluyor..."
systemctl stop mayatech-screen-manager 2>/dev/null || true
systemctl disable mayatech-screen-manager 2>/dev/null || true
systemctl daemon-reload

echo "[2/8] Eski dosyalar siliniyor..."
rm -rf /home/*/mayatech-screen-manager 2>/dev/null || true
rm -rf /root/mayatech-screen-manager 2>/dev/null || true
rm -rf /opt/mayatech-screen-manager 2>/dev/null || true
rm -f /etc/systemd/system/mayatech-screen-manager.service

echo "[3/8] Eski veritabani temizleniyor..."
rm -f /home/*/mayatech.db 2>/dev/null || true
rm -f /root/mayatech.db 2>/dev/null || true
rm -f /opt/mayatech.db 2>/dev/null || true

echo "[4/8] Git kuruluyor..."
apt-get update -qq
apt-get install -y git > /dev/null 2>&1

echo "[5/8] Yeni proje klonlaniyor..."
cd /opt
git clone https://github.com/simsekdogukan/mayatech-screen-manager.git
cd mayatech-screen-manager

echo "[6/8] Setup.sh calistiriliyor..."
bash setup.sh

echo ""
echo "=========================================="
echo "TEMIZLIK VE KURULUM TAMAMLANDI"
echo "=========================================="
echo ""
echo "Admin Paneli: http://$(hostname -I | awk '{print $1}'):8080"
echo "Kullanici: solpro"
echo "Sifre: solpro"
echo ""
echo "Proje temizlendi ve yeniden kuruldu!"
echo "=========================================="
