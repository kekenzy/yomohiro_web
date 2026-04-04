#!/bin/bash

# Let's Encrypt SSL証明書設定スクリプト
# 使用方法: ./setup_ssl.sh your-domain.com
#
# certbot は --webroot を使用（Nginx を停止しない）。初回の HTTP 用 nginx.conf に
# /.well-known/acme-challenge/ が含まれている必要があります。

set -e

if [ -z "$1" ]; then
    echo "❌ エラー: ドメイン名を指定してください"
    echo "使用方法: ./setup_ssl.sh your-domain.com"
    exit 1
fi

DOMAIN=$1
WWW_DOMAIN="www.$DOMAIN"
WEBROOT="/var/www/html"

echo "🔒 Let's Encrypt SSL証明書の設定を開始します..."
echo "📍 ドメイン: $DOMAIN, $WWW_DOMAIN"

# 公開 DNS に A レコードが無いと Let's Encrypt は必ず失敗する
if command -v dig >/dev/null 2>&1; then
    if ! dig +short "$DOMAIN" A | grep -qE '^[0-9.]'; then
        echo "❌ DNS エラー: $DOMAIN の A レコードが見つかりません（NXDOMAIN または未設定）。"
        echo "   レジストラで A レコードをサーバのグローバル IP に向け、反映を待ってから再実行してください。"
        exit 1
    fi
    if ! dig +short "$WWW_DOMAIN" A | grep -qE '^[0-9.]'; then
        echo "❌ DNS エラー: $WWW_DOMAIN の A レコードが見つかりません。"
        echo "   www 用の A（または CNAME）を設定してから再実行してください。"
        exit 1
    fi
fi

# apt が対話プロンプトで止まらないようにする（リモート実行でよく詰まる）
export DEBIAN_FRONTEND=noninteractive

# Certbotのインストール（webroot 用。nginx プラグインは不要）
echo "📦 Certbotをインストール中..."
sudo -E apt-get update -qq
sudo -E apt-get install -y -qq certbot

# ACME チャレンジ用ディレクトリ
echo "📁 ACME 用ディレクトリを作成中..."
sudo mkdir -p "$WEBROOT/.well-known/acme-challenge"
sudo chown -R www-data:www-data "$WEBROOT" 2>/dev/null || true

# ファイアウォールでHTTPSを許可
echo "🔥 ファイアウォールでHTTPSを許可中..."
sudo ufw allow 'Nginx Full' 2>/dev/null || true
sudo ufw allow OpenSSH 2>/dev/null || true

# Nginx設定を更新（server_nameを設定）
echo "⚙️  Nginx設定を更新中..."
sudo sed -i "s/server_name _;/server_name $DOMAIN $WWW_DOMAIN;/" /etc/nginx/sites-available/yomohiro_web
sudo nginx -t

# Nginxを再読み込み（ポート80で webroot を公開）
echo "🔄 Nginxを再読み込み中..."
sudo systemctl reload nginx

# SSL証明書の取得（webroot: Nginx は起動したまま）
echo "📜 SSL証明書を取得中..."
sudo certbot certonly \
    --webroot \
    -w "$WEBROOT" \
    -d "$DOMAIN" \
    -d "$WWW_DOMAIN" \
    --non-interactive \
    --agree-tos \
    --email "admin@$DOMAIN" \
    --preferred-challenges http

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
    sed -i "s|ALLOWED_HOSTS=.*|ALLOWED_HOSTS=$DOMAIN,$WWW_DOMAIN,54.178.68.240,localhost,127.0.0.1|" .env

    if grep -q '^CSRF_TRUSTED_ORIGINS=' .env; then
        sed -i "s|CSRF_TRUSTED_ORIGINS=.*|CSRF_TRUSTED_ORIGINS=https://$DOMAIN,https://$WWW_DOMAIN|" .env
    else
        echo "CSRF_TRUSTED_ORIGINS=https://$DOMAIN,https://$WWW_DOMAIN" >> .env
    fi

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
echo "🔒 証明書の自動更新は certbot の systemd タイマーで行われます（renew --dry-run で確認済み）"
echo ""
echo "次のステップ："
echo "1. DNS設定を確認してください（Aレコードが正しく設定されているか）"
echo "2. https://$DOMAIN にアクセスして動作確認"
echo "3. HTTPからHTTPSへのリダイレクトが動作しているか確認"
