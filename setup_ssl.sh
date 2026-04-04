#!/bin/bash

# Let's Encrypt SSL証明書設定スクリプト
# 使用方法: ./setup_ssl.sh your-domain.com

set -e

if [ -z "$1" ]; then
    echo "❌ エラー: ドメイン名を指定してください"
    echo "使用方法: ./setup_ssl.sh your-domain.com"
    exit 1
fi

DOMAIN=$1
WWW_DOMAIN="www.$DOMAIN"

echo "🔒 Let's Encrypt SSL証明書の設定を開始します..."
echo "📍 ドメイン: $DOMAIN, $WWW_DOMAIN"

# Certbotのインストール
echo "📦 Certbotをインストール中..."
sudo apt-get update -qq
sudo apt-get install -y certbot python3-certbot-nginx

# ファイアウォールでHTTPSを許可
echo "🔥 ファイアウォールでHTTPSを許可中..."
sudo ufw allow 'Nginx Full'
sudo ufw allow OpenSSH

# Nginx設定を更新（server_nameを設定）
echo "⚙️  Nginx設定を更新中..."
sudo sed -i "s/server_name _;/server_name $DOMAIN $WWW_DOMAIN;/" /etc/nginx/sites-available/yomohiro_web
sudo nginx -t

# Nginxを再起動
echo "🔄 Nginxを再起動中..."
sudo systemctl restart nginx

# SSL証明書の取得（Nginxプラグインを使用せず、スタンドアロンで取得）
echo "📜 SSL証明書を取得中..."
sudo certbot certonly --standalone -d $DOMAIN -d $WWW_DOMAIN --non-interactive --agree-tos --email admin@$DOMAIN --preferred-challenges http

# Nginx設定をSSL用に更新
echo "⚙️  Nginx設定をSSL用に更新中..."
sudo cp /home/ubuntu/yomohiro_web/config/nginx_ssl.conf /etc/nginx/sites-available/yomohiro_web
sudo sed -i "s/your-domain.com/$DOMAIN/g" /etc/nginx/sites-available/yomohiro_web
sudo nginx -t

# Nginxを再起動
echo "🔄 Nginxを再起動中..."
sudo systemctl restart nginx

# 自動更新のテスト
echo "🔄 自動更新のテスト中..."
sudo certbot renew --dry-run

# .envファイルを更新
echo "⚙️  .envファイルを更新中..."
cd /home/ubuntu/yomohiro_web
if [ -f .env ]; then
    # ALLOWED_HOSTSにドメインを追加
    sed -i "s|ALLOWED_HOSTS=.*|ALLOWED_HOSTS=$DOMAIN,$WWW_DOMAIN,54.64.209.76,localhost,127.0.0.1|" .env
    
    # SSL設定を有効化
    sed -i 's/SECURE_SSL_REDIRECT=False/SECURE_SSL_REDIRECT=True/' .env
    sed -i 's/SESSION_COOKIE_SECURE=False/SESSION_COOKIE_SECURE=True/' .env
    sed -i 's/CSRF_COOKIE_SECURE=False/CSRF_COOKIE_SECURE=True/' .env
    
    echo "✅ .envファイルを更新しました"
else
    echo "⚠️  .envファイルが見つかりません。手動で設定してください。"
fi

# Gunicornを再起動
echo "🔄 Gunicornを再起動中..."
sudo systemctl restart gunicorn

echo ""
echo "✅ SSL証明書の設定が完了しました！"
echo ""
echo "🌐 HTTPS URL: https://$DOMAIN"
echo "🔒 証明書の自動更新は設定済みです"
echo ""
echo "次のステップ："
echo "1. DNS設定を確認してください（Aレコードが正しく設定されているか）"
echo "2. https://$DOMAIN にアクセスして動作確認"
echo "3. HTTPからHTTPSへのリダイレクトが動作しているか確認"

