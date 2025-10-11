#!/bin/bash

# AWS Lightsail デプロイスクリプト
# このスクリプトはLightsailインスタンス上で実行されます

set -e  # エラーが発生したら即座に終了

echo "🚀 デプロイを開始します..."

# プロジェクトディレクトリに移動
cd /home/ubuntu/yomohiro_web

# Gitから最新のコードを取得
echo "📥 最新のコードを取得中..."
git pull origin main

# 仮想環境をアクティベート
echo "📦 仮想環境をアクティベート中..."
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

# Gunicornを再起動
echo "🔄 Gunicornを再起動中..."
sudo systemctl restart gunicorn

# Nginxを再起動
echo "🔄 Nginxを再起動中..."
sudo systemctl restart nginx

echo "✅ デプロイが完了しました！"

