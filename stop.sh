#!/bin/bash

# U-街プラザ 東西南北館 予約システム 停止スクリプト
# 使用方法: ./stop.sh

echo "🛑 U-街プラザ 東西南北館 予約システムを停止します..."

# プロジェクトディレクトリに移動
cd "$(dirname "$0")"

# Djangoサーバーを停止
echo "🛑 Djangoサーバーを停止しています..."
pkill -f "manage.py runserver" 2>/dev/null

if [ $? -eq 0 ]; then
    echo "✅ Djangoサーバーが正常に停止されました。"
else
    echo "ℹ️ 実行中のDjangoサーバーが見つかりませんでした。"
fi

# 仮想環境を非アクティベート
echo "📦 仮想環境を非アクティベートしています..."
deactivate 2>/dev/null || true

echo "🎯 システムが停止されました。"
