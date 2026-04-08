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

# この Lightsail インスタンスのグローバル IP（お名前.com の A レコードと一致させる）
ORIGIN_IP="${EXPECTED_ORIGIN_IP:-54.178.68.240}"

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

    # HTTP-01 は「このサーバの Nginx」に届く必要がある。Cloudflare プロキシだと別 IP になり 404 になりやすい
    RESOLVED=$(dig +short "$DOMAIN" A @8.8.8.8 | grep -E '^[0-9.]+$' | head -1)
    if [ -n "$RESOLVED" ] && [ "$RESOLVED" != "$ORIGIN_IP" ] && [ "${SKIP_ORIGIN_IP_CHECK:-}" != "1" ]; then
        echo "❌ DNS がこのサーバ（$ORIGIN_IP）を向いていません。現在の A レコード: $RESOLVED"
        echo "   Let's Encrypt は http://$DOMAIN/.well-known/acme-challenge/ にアクセスして検証します。"
        echo "   Cloudflare 利用時: DNS の「プロキシをオフ」（灰色の雲）にするか、一時的に DNS のみにしてください。"
        echo "   お名前.com のみ: A レコードを $ORIGIN_IP にし、反映を待ってから再実行してください。"
        echo "   （意図的に続行する場合: SKIP_ORIGIN_IP_CHECK=1 ./setup_ssl.sh $DOMAIN）"
        exit 1
    fi
fi

# apt が対話プロンプトで止まらないようにする（リモート実行でよく詰まる）
export DEBIAN_FRONTEND=noninteractive

# Certbotのインストール（webroot 用。nginx プラグインは不要）
# --no-install-recommends でメモリ使用量を抑える（小容量 Lightsail で apt が Killed になるのを防ぐ）
echo "📦 Certbotをインストール中..."
sudo -E apt-get update -qq
sudo -E apt-get install -y -qq --no-install-recommends certbot

# ACME チャレンジ用ディレクトリ
echo "📁 ACME 用ディレクトリを作成中..."
sudo mkdir -p "$WEBROOT/.well-known/acme-challenge"
sudo chown -R www-data:www-data "$WEBROOT" 2>/dev/null || true

# ローカルで webroot が配信できるか（nginx の location が効いているか）
echo "🧪 Nginx が /.well-known/ を配信できるか確認..."
echo "le-ping" | sudo tee "$WEBROOT/.well-known/acme-challenge/le-ping.txt" >/dev/null
sudo chmod 644 "$WEBROOT/.well-known/acme-challenge/le-ping.txt"
if ! curl -sf "http://127.0.0.1/.well-known/acme-challenge/le-ping.txt" -H "Host: $DOMAIN" | grep -q le-ping; then
    echo "❌ Nginx が $WEBROOT のチャレンジファイルを配信できていません。config/nginx.conf の location ^~ /.well-known/ を確認してください。"
    exit 1
fi
sudo rm -f "$WEBROOT/.well-known/acme-challenge/le-ping.txt"

# ファイアウォールでHTTPSを許可
echo "🔥 ファイアウォールでHTTPSを許可中..."
sudo ufw allow 'Nginx Full' 2>/dev/null || true
sudo ufw allow OpenSSH 2>/dev/null || true

# Nginx設定を更新（server_name をドメイン + 静的 IP に）
echo "⚙️  Nginx設定を更新中..."
sudo sed -i "s/server_name 54.178.68.240 yomohirokan.com www.yomohirokan.com;/server_name $DOMAIN $WWW_DOMAIN 54.178.68.240;/" /etc/nginx/sites-available/yomohiro_web
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
