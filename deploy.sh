#!/bin/bash

# ローカルからLightsailにデプロイするスクリプト
# SSHエイリアス: yomohiro (http://54.178.68.240)

set -e  # エラーが発生したら即座に終了

echo "🚀 Lightsailへのデプロイを開始します..."
echo "📍 ターゲット: yomohiro (54.178.68.240)"

# SSH接続テスト
echo "🔌 SSH接続をテスト中..."
if ! ssh -o ConnectTimeout=10 yomohiro "echo 'SSH接続成功'" 2>/dev/null; then
    echo "❌ SSH接続に失敗しました。SSH設定を確認してください。"
    echo "   ~/.ssh/config に以下が設定されているか確認:"
    echo "   Host yomohiro"
    echo "     HostName 54.178.68.240"
    echo "     User ubuntu"
    exit 1
fi

echo "✅ SSH接続成功"

# リモートでデプロイスクリプトを実行
echo "📤 リモートでデプロイスクリプトを実行中..."
ssh yomohiro 'bash -s' << 'ENDSSH'
set -e
export DEBIAN_FRONTEND=noninteractive

echo "🚀 デプロイを開始します..."

# プロジェクトディレクトリが存在しない場合はクローン
if [ ! -d "/home/ubuntu/yomohiro_web" ]; then
    echo "📦 プロジェクトディレクトリが見つかりません。クローンします..."
    cd /home/ubuntu
    REPO_URL="https://github.com/kekenzy/yomohiro_web.git"
    echo "📥 リポジトリをクローン中: $REPO_URL"
    git clone "$REPO_URL" yomohiro_web || {
        echo "❌ git cloneに失敗しました。"
        echo "   手動でクローンしてください:"
        echo "   cd /home/ubuntu"
        echo "   git clone $REPO_URL yomohiro_web"
        exit 1
    }
    echo "✅ クローン完了"
fi

# プロジェクトディレクトリに移動
cd /home/ubuntu/yomohiro_web || {
    echo "❌ プロジェクトディレクトリが見つかりません: /home/ubuntu/yomohiro_web"
    exit 1
}

# Gitから最新のコードを取得
echo "📥 最新のコードを取得中..."
# ローカルの変更がある場合はstashしてからpull
if ! git diff --quiet || ! git diff --cached --quiet; then
    echo "📦 ローカルの変更をstash中..."
    git stash
fi
# git pullの設定（rebaseを使用）
git config pull.rebase false
git pull origin main || {
    echo "⚠️  git pullに失敗しました。手動で確認してください。"
    exit 1
}
# stashした変更があれば復元
if git stash list | grep -q "stash@{0}"; then
    echo "📦 ローカルの変更を復元中..."
    git stash pop || true
fi

# 仮想環境を作成またはアクティベート
echo "📦 仮想環境を確認中..."
if [ ! -d "venv" ]; then
    echo "📦 仮想環境が見つかりません。作成します..."
    # python3-venvパッケージがインストールされているか確認
    if ! dpkg -l | grep -q python3-venv; then
        echo "📦 python3-venvパッケージをインストール中..."
        sudo apt-get update -qq
        sudo apt-get install -y python3-venv python3-pip
    fi
    python3 -m venv venv || {
        echo "❌ 仮想環境の作成に失敗しました。"
        exit 1
    }
    echo "✅ 仮想環境を作成しました"
fi

# 仮想環境が正しく作成されたか確認
if [ ! -f "venv/bin/activate" ]; then
    echo "❌ 仮想環境のactivateファイルが見つかりません。"
    exit 1
fi

source venv/bin/activate

# pip: SSH 経由だと TTY が無く進捗が出ず「止まった」ように見える・PyPI が遅いと無限待ちに見える
# 対策: 進捗バー強制、タイムアウト/リトライ、毎回の pip 自己更新チェックを無効化
export PYTHONUNBUFFERED=1
export PIP_DISABLE_PIP_VERSION_CHECK=1
export PIP_PROGRESS_BAR=on

PIP_TIMEOUT=180
PIP_RETRIES=5

echo "📦 pip / setuptools / wheel を更新中..."
python -m pip install --upgrade pip setuptools wheel \
    --timeout "$PIP_TIMEOUT" --retries "$PIP_RETRIES"

echo "📦 依存関係をインストール中（初回や PyPI が遅いときは数分かかります）..."
python -m pip install -r requirements.txt \
    --timeout "$PIP_TIMEOUT" --retries "$PIP_RETRIES" --progress-bar on

# データベースマイグレーション
echo "🗄️ データベースマイグレーション実行中..."
python manage.py migrate --noinput

# 設定の整合性チェック（依存不足や設定ミスで早期に失敗させる）
echo "🔍 Django システムチェック..."
python manage.py check

# 静的ファイルを収集
echo "📁 静的ファイルを収集中..."
python manage.py collectstatic --noinput

# 静的ファイルのパーミッションを設定
echo "🔐 静的ファイルのパーミッションを設定中..."
sudo chmod -R 755 /home/ubuntu/yomohiro_web/staticfiles
sudo chown -R ubuntu:www-data /home/ubuntu/yomohiro_web/staticfiles
sudo chmod 755 /home/ubuntu
sudo chmod 755 /home/ubuntu/yomohiro_web

# ログディレクトリを作成
mkdir -p logs
chmod 755 logs

# .envファイルが存在しない場合は作成
if [ ! -f ".env" ]; then
    echo "⚙️  .envファイルが見つかりません。作成します..."
    source venv/bin/activate
    SECRET_KEY=$(python3 -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())")
    cat > .env << EOF
SECRET_KEY=$SECRET_KEY
DEBUG=False
ALLOWED_HOSTS=54.178.68.240,localhost,127.0.0.1,yomohirokan.com,www.yomohirokan.com
CSRF_TRUSTED_ORIGINS=https://yomohirokan.com,https://www.yomohirokan.com
SECURE_SSL_REDIRECT=False
SESSION_COOKIE_SECURE=False
CSRF_COOKIE_SECURE=False
EOF
    echo "✅ .envファイルを作成しました"
fi

# Gunicornサービスを設定（初回のみ）
if [ ! -f "/etc/systemd/system/gunicorn.service" ]; then
    echo "⚙️  Gunicornサービスを設定中（初回セットアップ）..."
    if [ -f "config/gunicorn.service" ]; then
        sudo cp config/gunicorn.service /etc/systemd/system/
        sudo systemctl daemon-reload
        sudo systemctl enable gunicorn
        sudo systemctl start gunicorn
        echo "✅ Gunicornサービスを設定しました"
    else
        echo "⚠️  config/gunicorn.serviceが見つかりません。手動で設定してください。"
    fi
else
    # Gunicornを再起動
    echo "🔄 Gunicornを再起動中..."
    sudo systemctl restart gunicorn || {
        echo "⚠️  Gunicornの再起動に失敗しました。状態を確認してください。"
        sudo systemctl status gunicorn
    }
fi

# Nginxをインストール（未インストールの場合）
if ! command -v nginx &> /dev/null; then
    echo "📦 Nginxをインストール中..."
    sudo apt-get update -qq
    sudo apt-get install -y nginx
fi

# Cloudflare 等の「手前 HTTPS・オリジン HTTP」で Django が誤動作しないよう map を http コンテキストに置く
if [ -f "config/nginx/conf.d/yomohiro_forwarded_proto.conf" ]; then
    echo "⚙️  Nginx conf.d（X-Forwarded-Proto map）を配置..."
    sudo mkdir -p /etc/nginx/conf.d
    sudo cp config/nginx/conf.d/yomohiro_forwarded_proto.conf /etc/nginx/conf.d/
fi

# Cloudflare「フル / フル（厳密）」はオリジンへ HTTPS（443）で接続する。443 が無いと 503 になる。
# 自己署名は Cloudflare フル用（来訪者の TLS は Cloudflare が担当）。Let's Encrypt 取得後は差し替え可。
if [ ! -f "/etc/nginx/ssl/cloudflare_origin.crt" ]; then
    echo "📜 Cloudflare フル用オリジン証明書を生成（自己署名・初回のみ）..."
    sudo mkdir -p /etc/nginx/ssl
    if ! sudo openssl req -x509 -nodes -days 825 -newkey rsa:2048 \
        -keyout /etc/nginx/ssl/cloudflare_origin.key \
        -out /etc/nginx/ssl/cloudflare_origin.crt \
        -subj "/CN=yomohirokan.com" \
        -addext "subjectAltName=DNS:yomohirokan.com,DNS:www.yomohirokan.com" 2>/dev/null; then
        sudo openssl req -x509 -nodes -days 825 -newkey rsa:2048 \
            -keyout /etc/nginx/ssl/cloudflare_origin.key \
            -out /etc/nginx/ssl/cloudflare_origin.crt \
            -subj "/CN=yomohirokan.com"
    fi
    sudo chmod 600 /etc/nginx/ssl/cloudflare_origin.key
    sudo chmod 644 /etc/nginx/ssl/cloudflare_origin.crt
fi

# Nginx サイト設定は毎回リポジトリから反映（443 や map の変更を取り込む）
if [ -f "config/nginx.conf" ]; then
    echo "⚙️  Nginx サイト設定を反映..."
    sudo mkdir -p /etc/nginx/sites-available /etc/nginx/sites-enabled
    sudo cp config/nginx.conf /etc/nginx/sites-available/yomohiro_web
    if [ ! -L "/etc/nginx/sites-enabled/yomohiro_web" ]; then
        sudo ln -sf /etc/nginx/sites-available/yomohiro_web /etc/nginx/sites-enabled/
        sudo rm -f /etc/nginx/sites-enabled/default
    fi
    sudo nginx -t && sudo systemctl reload nginx
    echo "✅ Nginx を更新しました（443 は Lightsail ネットワークで TCP 443 を許可してください）"
else
    echo "⚠️  config/nginx.conf が見つかりません。手動で設定してください。"
fi

echo "✅ デプロイが完了しました！"
ENDSSH

echo ""
echo "✅ デプロイが正常に完了しました！"
echo "🌐 アプリケーション: http://54.178.68.240"

