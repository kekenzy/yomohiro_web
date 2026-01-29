.PHONY: help up down build log logs restart shell migrate createsuperuser test clean deploy

# デフォルトターゲット
help:
	@echo "利用可能なコマンド:"
	@echo "  make up          - Dockerコンテナを起動（バックグラウンド）"
	@echo "  make down        - Dockerコンテナを停止"
	@echo "  make build       - Dockerイメージをビルド"
	@echo "  make rebuild     - Dockerイメージを再ビルド（--no-cache）"
	@echo "  make log         - ログをリアルタイムで表示"
	@echo "  make logs        - 最新50行のログを表示"
	@echo "  make restart     - Dockerコンテナを再起動"
	@echo "  make shell       - webコンテナのシェルに接続"
	@echo "  make migrate     - データベースマイグレーション実行"
	@echo "  make createsuperuser - スーパーユーザー作成"
	@echo "  make test        - テスト実行"
	@echo "  make clean       - 停止中のコンテナと未使用イメージを削除"
	@echo "  make adminer     - Adminer（DB管理ツール）を起動"
	@echo "  make deploy      - Lightsailにデプロイ（yomohiro）"

# Dockerコンテナを起動（バックグラウンド）
up:
	docker-compose up -d
	@echo "✅ Dockerコンテナを起動しました"
	@echo "📊 状態確認: make ps"
	@echo "📝 ログ確認: make log"

# Dockerコンテナを停止
down:
	docker-compose down
	@echo "✅ Dockerコンテナを停止しました"

# Dockerイメージをビルド
build:
	docker-compose build
	@echo "✅ Dockerイメージをビルドしました"

# Dockerイメージを再ビルド（キャッシュなし）
rebuild:
	docker-compose build --no-cache
	@echo "✅ Dockerイメージを再ビルドしました（キャッシュなし）"

# ログをリアルタイムで表示
log:
	docker-compose logs -f web

# 最新50行のログを表示
logs:
	docker-compose logs --tail=50 web

# Dockerコンテナを再起動
restart:
	docker-compose restart
	@echo "✅ Dockerコンテナを再起動しました"

# webコンテナのシェルに接続
shell:
	docker-compose exec web /bin/bash

# データベースマイグレーション実行
migrate:
	docker-compose exec web python manage.py migrate
	@echo "✅ マイグレーションを実行しました"

# スーパーユーザー作成
createsuperuser:
	docker-compose exec web python manage.py createsuperuser

# テスト実行
test:
	docker-compose exec web python manage.py test

# 停止中のコンテナと未使用イメージを削除
clean:
	docker-compose down
	docker system prune -f
	@echo "✅ クリーンアップを完了しました"

# コンテナの状態を表示
ps:
	docker-compose ps

# データベースのマイグレーション作成
makemigrations:
	docker-compose exec web python manage.py makemigrations

# 静的ファイルを収集
collectstatic:
	docker-compose exec web python manage.py collectstatic --noinput
	@echo "✅ 静的ファイルを収集しました"

# サンプルデータを作成
sample-data:
	docker-compose exec web python manage.py create_sample_data

# Adminer（DB管理ツール）の情報を表示
adminer:
	@echo "📊 Adminer（データベース管理ツール）"
	@echo "🌐 URL: http://localhost:8080"
	@echo ""
	@echo "接続情報:"
	@echo "  システム: PostgreSQL"
	@echo "  サーバー: db"
	@echo "  ユーザー名: reservation_user"
	@echo "  パスワード: reservation_password"
	@echo "  データベース: reservation_db"
	@echo ""
	@echo "コンテナを起動するには: make up"

# Lightsailにデプロイ
deploy:
	@echo "🚀 Lightsailにデプロイします..."
	@./deploy.sh

