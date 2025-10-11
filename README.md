# 予約システム

Djangoを使用したWebベースの予約システムです。場所と時間を選択して予約を作成し、管理者が予約を管理できるシステムです。

## 📚 ドキュメント

- **[デプロイ手順書](DEPLOYMENT.md)** - AWS Lightsailへの自動デプロイ手順

## 機能

### 一般ユーザー向け機能
- 場所と時間の選択
- リアルタイムでの空き状況確認
- お客様情報入力（氏名、メールアドレス、電話番号）
- 予約の作成と確認

### 管理者向け機能
- 管理者ログイン
- 予約の一覧表示、編集、削除
- 場所と時間枠の管理
- 電話での受付予約の直接入力

## 技術スタック

- **Backend**: Django 4.2.7
- **Database**: SQLite (開発環境) / PostgreSQL (本番環境)
- **Frontend**: Bootstrap 5.1.3
- **Icons**: Font Awesome 6.0.0

## セットアップ

### 前提条件

- Python 3.9以上
- Docker (オプション)

### ローカル環境でのセットアップ

1. リポジトリをクローン
```bash
git clone <repository-url>
cd yomohiro_web
```

2. 仮想環境を作成してアクティベート
```bash
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# または
venv\Scripts\activate  # Windows
```

3. 依存関係をインストール
```bash
pip install -r requirements.txt
```

4. データベースのマイグレーション
```bash
python manage.py migrate
```

5. 管理者ユーザーを作成
```bash
python manage.py createsuperuser
```

6. サンプルデータを作成（オプション）
```bash
python manage.py create_sample_data
```

7. 開発サーバーを起動
```bash
python manage.py runserver
```

8. ブラウザでアクセス
- メインサイト: http://localhost:8000/
- 管理画面: http://localhost:8000/admin/

### Docker環境でのセットアップ

1. Docker Composeで起動
```bash
docker-compose up --build
```

2. データベースのマイグレーション
```bash
docker-compose exec web python manage.py migrate
```

3. 管理者ユーザーを作成
```bash
docker-compose exec web python manage.py createsuperuser
```

4. サンプルデータを作成（オプション）
```bash
docker-compose exec web python manage.py create_sample_data
```

## 使用方法

### 予約の作成

1. ホームページから「新規予約」をクリック
2. 場所と日付を選択
3. 利用可能な時間枠から選択
4. お客様情報を入力
5. 予約を確定

### 管理者機能

1. 管理画面にログイン
2. 予約、場所、時間枠の管理が可能
3. 電話での受付予約も直接入力可能

## プロジェクト構造

```
yomohiro_web/
├── reservation_system/          # Djangoプロジェクト設定
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── reservations/                # 予約アプリケーション
│   ├── models.py               # データモデル
│   ├── views.py                # ビュー
│   ├── forms.py                # フォーム
│   ├── admin.py                # 管理者設定
│   ├── urls.py                 # URL設定
│   └── templates/              # テンプレート
│       └── reservations/
│           ├── base.html
│           ├── index.html
│           ├── reservation_form.html
│           └── ...
├── static/                     # 静的ファイル
├── manage.py
├── requirements.txt
├── docker-compose.yml
└── Dockerfile
```

## 環境変数

以下の環境変数を設定できます：

- `DEBUG`: デバッグモード（デフォルト: True）
- `SECRET_KEY`: Djangoのシークレットキー
- `DATABASE_URL`: データベース接続URL

## ライセンス

このプロジェクトはMITライセンスの下で公開されています。
# Test deployment3
