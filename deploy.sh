#!/bin/bash

# ローカルからLightsailにデプロイするスクリプト
# SSHエイリアス: yomohiro (18.183.107.163)

set -e  # エラーが発生したら即座に終了

echo "🚀 Lightsailへのデプロイを開始します..."
echo "📍 ターゲット: yomohiro (18.183.107.163)"

# SSH接続テスト
echo "🔌 SSH接続をテスト中..."
if ! ssh -o ConnectTimeout=10 yomohiro "echo 'SSH接続成功'" 2>/dev/null; then
    echo "❌ SSH接続に失敗しました。SSH設定を確認してください。"
    echo "   ~/.ssh/config に以下が設定されているか確認:"
    echo "   Host yomohiro"
    echo "     HostName 18.183.107.163"
    echo "     User ubuntu"
    exit 1
fi

echo "✅ SSH接続成功"

# リモートでデプロイスクリプトを実行
echo "📤 リモートでデプロイスクリプトを実行中..."
ssh yomohiro 'bash -s' << 'ENDSSH'
set -e

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

# 依存関係をインストール
echo "📦 依存関係をインストール中..."
pip install -r requirements.txt

# データベースマイグレーション
echo "🗄️ データベースマイグレーション実行中..."
python manage.py migrate --noinput

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
ALLOWED_HOSTS=18.183.107.163,localhost,127.0.0.1
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

# Nginxを設定（初回のみ）
if [ ! -f "/etc/nginx/sites-available/yomohiro_web" ]; then
    echo "⚙️  Nginxを設定中（初回セットアップ）..."
    if [ -f "config/nginx.conf" ]; then
        sudo mkdir -p /etc/nginx/sites-available /etc/nginx/sites-enabled
        sudo cp config/nginx.conf /etc/nginx/sites-available/yomohiro_web
        sudo ln -sf /etc/nginx/sites-available/yomohiro_web /etc/nginx/sites-enabled/
        sudo rm -f /etc/nginx/sites-enabled/default
        sudo nginx -t && sudo systemctl restart nginx
        echo "✅ Nginxを設定しました"
    else
        echo "⚠️  config/nginx.confが見つかりません。手動で設定してください。"
    fi
else
    # Nginxを再起動
    echo "🔄 Nginxを再起動中..."
    sudo systemctl restart nginx || {
        echo "⚠️  Nginxの再起動に失敗しました。状態を確認してください。"
        sudo systemctl status nginx
    }
fi

echo "✅ デプロイが完了しました！"
ENDSSH

echo ""
echo "✅ デプロイが正常に完了しました！"
echo "🌐 アプリケーション: http://18.183.107.163"

