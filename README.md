# 予約システム

Djangoを使用したWebベースの予約システムです。場所と時間を選択して予約を作成し、管理者が予約を管理できるシステムです。

## 📚 ドキュメント

| ドキュメント | 内容 |
|--------------|------|
| **[DOCUMENTATION.md](DOCUMENTATION.md)** | **全 Markdown の索引**（目的別・読む順） |
| **[PRODUCTION.md](PRODUCTION.md)** | **本番環境の設定**（環境変数、LINE / Square、migrate 等） |
| [DEPLOYMENT.md](DEPLOYMENT.md) | AWS Lightsail・GitHub Actions によるデプロイ手順 |
| [SSL_SETUP.md](SSL_SETUP.md) | Let's Encrypt 等の SSL |
| [FEATURES.md](FEATURES.md) | 機能一覧とソースの対応 |

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

- **Backend**: Django 4.2.7（認証: django-allauth、LINE Login 対応）
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

**デフォルトの管理者アカウント（Docker環境で既に作成済み）:**
- **ユーザー名:** `admin`
- **パスワード:** `admin123`
- **メールアドレス:** `admin@example.com`
- **アクセスURL:** http://localhost:8001/admin/

> ⚠️ **注意:** 本番環境では、必ず強力なパスワードに変更してください。

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

**デフォルトの管理者アカウント（既に作成済み）:**
- **ユーザー名:** `admin`
- **パスワード:** `admin123`
- **メールアドレス:** `admin@example.com`
- **アクセスURL:** http://localhost:8001/admin/

> ⚠️ **注意:** 本番環境では、必ず強力なパスワードに変更してください。

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

本番で必要な変数（`SECRET_KEY`、`ALLOWED_HOSTS`、`DATABASE_URL`、Square、LINE Login、メール、HTTPS 関連など）は **[PRODUCTION.md](PRODUCTION.md)** に表形式でまとめています。索引は **[DOCUMENTATION.md](DOCUMENTATION.md)** を参照してください。

## ライセンス

このプロジェクトはMITライセンスの下で公開されています。
