#!/bin/bash

# 自己署名証明書でHTTPSを設定するスクリプト（テスト用）
# 本番環境ではLet's Encryptを使用してください

set -e

echo "🔒 自己署名証明書でHTTPSを設定します（テスト用）..."

# 証明書ディレクトリを作成
sudo mkdir -p /etc/nginx/ssl

# 自己署名証明書を生成（有効期限1年）
echo "📜 自己署名証明書を生成中..."
sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout /etc/nginx/ssl/yomohiro_key.pem \
    -out /etc/nginx/ssl/yomohiro_cert.pem \
    -subj "/C=JP/ST=Fukuoka/L=Fukuoka/O=Yomohiro/CN=18.183.91.131" \
    -addext "subjectAltName=IP:18.183.91.131"

# 証明書のパーミッションを設定
sudo chmod 600 /etc/nginx/ssl/yomohiro_key.pem
sudo chmod 644 /etc/nginx/ssl/yomohiro_cert.pem

# Nginx設定をHTTPS用に更新
echo "⚙️  Nginx設定をHTTPS用に更新中..."
sudo tee /etc/nginx/sites-available/yomohiro_web > /dev/null << 'EOF'
# HTTPからHTTPSへのリダイレクト
server {
    listen 80;
    listen [::]:80;
    server_name 18.183.91.131 _;
    
    # HTTPSにリダイレクト
    return 301 https://$host$request_uri;
}

# HTTPS設定
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name 18.183.91.131 _;

    # SSL証明書（自己署名）
    ssl_certificate /etc/nginx/ssl/yomohiro_cert.pem;
    ssl_certificate_key /etc/nginx/ssl/yomohiro_key.pem;
    
    # SSL設定（堅牢な設定）
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers on;
    ssl_ciphers 'ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384';
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    ssl_session_tickets off;
    
    # セキュリティヘッダー
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    client_max_body_size 10M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-Port $server_port;
        proxy_redirect off;
        
        # タイムアウト設定
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    location /static/ {
        alias /home/ubuntu/yomohiro_web/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
        access_log off;
    }

    location /media/ {
        alias /home/ubuntu/yomohiro_web/media/;
        expires 30d;
        add_header Cache-Control "public, immutable";
        access_log off;
    }

    # ログ設定
    access_log /var/log/nginx/yomohiro_ssl_access.log;
    error_log /var/log/nginx/yomohiro_ssl_error.log;
}
EOF

# Nginx設定をテスト
echo "🔍 Nginx設定をテスト中..."
sudo nginx -t

# ファイアウォールでHTTPSを許可
echo "🔥 ファイアウォールでHTTPSを許可中..."
sudo ufw allow 'Nginx Full'
sudo ufw allow OpenSSH

# Nginxを再起動
echo "🔄 Nginxを再起動中..."
sudo systemctl restart nginx

# .envファイルを更新
echo "⚙️  .envファイルを更新中..."
cd /home/ubuntu/yomohiro_web
if [ -f .env ]; then
    # ALLOWED_HOSTSにIPアドレスを追加（既に含まれている場合はスキップ）
    if ! grep -q "18.183.91.131" .env; then
        sed -i "s|ALLOWED_HOSTS=.*|ALLOWED_HOSTS=18.183.91.131,localhost,127.0.0.1|" .env
    fi
    
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
echo "✅ HTTPS設定が完了しました！"
echo ""
echo "⚠️  注意: 自己署名証明書のため、ブラウザで警告が表示されます"
echo "   本番環境ではLet's Encryptの証明書を使用してください"
echo ""
echo "🌐 HTTPS URL: https://18.183.91.131"
echo "   HTTPアクセスは自動的にHTTPSにリダイレクトされます"

