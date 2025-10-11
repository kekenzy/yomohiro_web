#!/bin/bash

# AWS Lightsail 初期セットアップスクリプト
# このスクリプトはLightsailインスタンスで初回のみ実行します

set -e

echo "🚀 AWS Lightsail セットアップを開始します..."

# システムのアップデート
echo "📦 システムをアップデート中..."
sudo apt-get update
sudo apt-get upgrade -y

# 必要なパッケージをインストール
echo "📦 必要なパッケージをインストール中..."
sudo apt-get install -y python3 python3-pip python3-venv git nginx

# プロジェクトディレクトリを作成
echo "📁 プロジェクトディレクトリを作成中..."
cd /home/ubuntu
git clone https://github.com/YOUR_USERNAME/yomohiro_web.git
cd yomohiro_web

# ログディレクトリを作成
mkdir -p logs

# 仮想環境を作成
echo "📦 Python仮想環境を作成中..."
python3 -m venv venv
source venv/bin/activate

# 依存関係をインストール
echo "📦 依存関係をインストール中..."
pip install --upgrade pip
pip install -r requirements.txt

# 環境変数ファイルを作成
echo "⚙️ 環境変数ファイルを作成中..."
cat > .env << 'EOF'
SECRET_KEY=your-secret-key-here-please-change-this
DEBUG=False
ALLOWED_HOSTS=your-domain.com,www.your-domain.com,your-lightsail-ip
SECURE_SSL_REDIRECT=False
SESSION_COOKIE_SECURE=False
CSRF_COOKIE_SECURE=False
EOF

echo "⚠️  .envファイルを編集してください！"

# データベースのマイグレーション
echo "🗄️ データベースを初期化中..."
python manage.py migrate

# 静的ファイルを収集
echo "📁 静的ファイルを収集中..."
python manage.py collectstatic --noinput

# スーパーユーザーを作成
echo "👤 管理者ユーザーを作成してください："
python manage.py createsuperuser

# Gunicornのsystemdサービスを設定
echo "⚙️ Gunicornサービスを設定中..."
sudo cp config/gunicorn.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl start gunicorn
sudo systemctl enable gunicorn

# Nginxを設定
echo "⚙️ Nginxを設定中..."
sudo cp config/nginx.conf /etc/nginx/sites-available/yomohiro_web
sudo ln -sf /etc/nginx/sites-available/yomohiro_web /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx

# ファイアウォールを設定
echo "🔥 ファイアウォールを設定中..."
sudo ufw allow 'Nginx Full'
sudo ufw allow OpenSSH
echo "y" | sudo ufw enable

echo "✅ セットアップが完了しました！"
echo ""
echo "次のステップ："
echo "1. .envファイルを編集してSECRET_KEYとALLOWED_HOSTSを設定"
echo "2. DNSでドメインをLightsailのIPアドレスに向ける"
echo "3. SSL証明書を設定する（certbot --nginx）"
echo "4. GitHub Secretsに以下を設定："
echo "   - LIGHTSAIL_HOST: Lightsailインスタンスの公開IP"
echo "   - LIGHTSAIL_USER: ubuntu"
echo "   - LIGHTSAIL_SSH_KEY: SSH秘密鍵の内容"
echo ""
echo "🎉 準備完了！"

