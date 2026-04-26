#!/bin/bash
# =====================================================
#  Oracle Cloud Ubuntu VM セットアップスクリプト
#  実行: bash oracle_setup.sh
# =====================================================
set -e

echo "=== [1/6] システム更新 ==="
sudo apt update && sudo apt upgrade -y

echo "=== [2/6] Python & pip インストール ==="
sudo apt install -y python3 python3-pip python3-venv git nginx

echo "=== [3/6] アプリディレクトリ作成 ==="
mkdir -p ~/stock_app
cd ~/stock_app

echo "=== [4/6] 仮想環境 & 依存パッケージ ==="
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "=== [5/6] systemd サービス登録（自動起動） ==="
sudo tee /etc/systemd/system/stock_app.service > /dev/null << 'SERVICE'
[Unit]
Description=株式おすすめアプリ
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/stock_app
Environment="PATH=/home/ubuntu/stock_app/venv/bin"
ExecStart=/home/ubuntu/stock_app/venv/bin/gunicorn app:app --config gunicorn_config.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
SERVICE

sudo systemctl daemon-reload
sudo systemctl enable stock_app
sudo systemctl start stock_app

echo "=== [6/6] ファイアウォール（ポート5000を開放） ==="
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 5000 -j ACCEPT
sudo netfilter-persistent save

echo ""
echo "✅ セットアップ完了！"
echo "   ブラウザで http://$(curl -s ifconfig.me):5000 を開いてください"
