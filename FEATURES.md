# U-街プラザ 東西南北館 予約システム - 機能一覧

> ドキュメント索引: [DOCUMENTATION.md](DOCUMENTATION.md) ／ 本番設定: [PRODUCTION.md](PRODUCTION.md)

## 🏗️ システム概要
Django 4.2.7を使用したWebベースの予約システムです。場所と時間を選択して予約を作成し、管理者が予約を管理できるシステムです。

## 📋 機能一覧

### 1. 予約システムの基本機能

#### 1.1 予約作成機能
- **ファイル**: `reservations/views.py` (reservation_create)
- **テンプレート**: `reservations/templates/reservations/reservation_form.html`
- **機能**:
  - 場所と時間の選択
  - リアルタイムでの空き状況確認（AJAX）
  - お客様情報入力（氏名、メールアドレス、電話番号）
  - 予約の作成と確認
  - 場所カードからの直接予約（ホーム画面から）

#### 1.2 予約確認機能
- **ファイル**: `reservations/views.py` (reservation_detail)
- **テンプレート**: `reservations/templates/reservations/reservation_detail.html`
- **機能**:
  - 予約詳細の表示
  - 予約ステータスの確認

#### 1.3 空き状況確認機能
- **ファイル**: `reservations/views.py` (check_availability)
- **機能**:
  - AJAXによるリアルタイム空き状況確認
  - 場所と日付を選択すると利用可能な時間枠を表示

### 2. 管理者機能

#### 2.1 管理者ダッシュボード
- **ファイル**: `reservations/views.py` (admin_dashboard)
- **テンプレート**: `reservations/templates/reservations/admin_dashboard.html`
- **機能**:
  - 今日の予約数表示
  - 今月の予約数表示
  - 利用可能な場所数表示
  - 最近の予約表示
  - 場所別予約数表示
  - 管理メニューへのアクセス

#### 2.2 予約管理機能
- **ファイル**: `reservations/views.py` (reservation_list)
- **テンプレート**: `reservations/templates/reservations/reservation_list.html`
- **機能**:
  - 予約一覧の表示
  - 予約検索機能（場所、日付、時間枠）
  - 予約カレンダー表示（FullCalendar）
  - 予約の編集・削除
  - ページネーション

#### 2.3 場所管理機能
- **ファイル**: `reservations/views.py` (location_management, location_add, location_edit, location_delete)
- **テンプレート**: `reservations/templates/reservations/location_management.html`
- **機能**:
  - 場所一覧の表示
  - 場所の追加・編集・削除
  - 場所のステータス管理（有効/無効）

#### 2.4 カスタムログイン機能
- **ファイル**: `reservations/views.py` (custom_login)
- **テンプレート**: `reservations/templates/reservations/login.html`
- **機能**:
  - 管理者専用ログイン画面
  - ログイン後のホーム画面リダイレクト

### 3. 表示機能

#### 3.1 ホーム画面
- **ファイル**: `reservations/views.py` (index)
- **テンプレート**: `reservations/templates/reservations/index.html`
- **機能**:
  - 場所カードの表示
  - 予約カレンダー表示（FullCalendar）
  - 管理者向けメニュー（ログイン時）
  - 営業情報表示
  - Google Maps表示

#### 3.2 場所一覧
- **ファイル**: `reservations/views.py` (location_list)
- **テンプレート**: `reservations/templates/reservations/location_list.html`
- **機能**:
  - 利用可能な場所の一覧表示

### 4. データモデル

#### 4.1 Location（場所）
- **ファイル**: `reservations/models.py`
- **フィールド**:
  - name: 場所名
  - description: 説明
  - capacity: 定員
  - is_active: 有効/無効
  - created_at: 作成日時
  - updated_at: 更新日時

#### 4.2 TimeSlot（時間枠）
- **ファイル**: `reservations/models.py`
- **フィールド**:
  - start_time: 開始時間
  - end_time: 終了時間
  - is_active: 有効/無効
  - created_at: 作成日時
  - updated_at: 更新日時

#### 4.3 Reservation（予約）
- **ファイル**: `reservations/models.py`
- **フィールド**:
  - location: 場所（ForeignKey）
  - time_slot: 時間枠（ForeignKey）
  - date: 予約日
  - customer_name: お客様名
  - customer_email: メールアドレス
  - customer_phone: 電話番号
  - status: ステータス（確認済み/保留中/キャンセル）
  - notes: 備考
  - created_by: 作成者（ForeignKey）
  - created_at: 作成日時
  - updated_at: 更新日時

### 5. フォーム

#### 5.1 ReservationForm（予約フォーム）
- **ファイル**: `reservations/forms.py`
- **機能**:
  - 予約作成・編集用フォーム
  - バリデーション機能
  - 重複予約チェック

#### 5.2 LocationForm（場所フォーム）
- **ファイル**: `reservations/forms.py`
- **機能**:
  - 場所作成・編集用フォーム

#### 5.3 ReservationSearchForm（予約検索フォーム）
- **ファイル**: `reservations/forms.py`
- **機能**:
  - 予約検索用フォーム

### 6. 静的ファイル

#### 6.1 CSS
- **ファイル**: `static/css/style.css`
- **機能**:
  - 統一されたデザインテーマ
  - 警告色（#ffc107）をベースとしたカラーパレット
  - レスポンシブデザイン
  - アニメーション効果

#### 6.2 JavaScript
- **ファイル**: `reservations/templates/reservations/index.html` (extra_js)
- **機能**:
  - FullCalendar統合
  - 場所カードクリックイベント
  - カレンダーイベント表示

### 7. URL設定

#### 7.1 メインURL
- **ファイル**: `reservation_system/urls.py`
- **パターン**:
  - admin/: Django管理サイト
  - '': reservations.urls

#### 7.2 アプリケーションURL
- **ファイル**: `reservations/urls.py`
- **パターン**:
  - '': ホーム画面
  - 'locations/': 場所一覧
  - 'reservations/': 予約一覧
  - 'reservations/create/': 予約作成
  - 'dashboard/': 管理者ダッシュボード
  - 'location-management/': 場所管理
  - 'login/': カスタムログイン
  - 'api/calendar/events/': カレンダーイベントAPI

### 8. 管理機能

#### 8.1 Django管理サイト
- **ファイル**: `reservations/admin.py`
- **機能**:
  - Location管理
  - TimeSlot管理
  - Reservation管理

## 🚀 技術スタック

- **Backend**: Django 4.2.7
- **Database**: SQLite (開発環境)
- **Frontend**: Bootstrap 5.1.3, Font Awesome 6.0.0
- **Calendar**: FullCalendar 6.1.8
- **Language**: Python 3.13
- **Environment**: Virtual Environment (venv)

## 📁 プロジェクト構造

```
yomohiro_web/
├── reservation_system/          # Djangoプロジェクト設定
│   ├── settings.py             # 設定ファイル
│   ├── urls.py                 # メインURL設定
│   └── wsgi.py                 # WSGI設定
├── reservations/               # 予約アプリケーション
│   ├── models.py              # データモデル
│   ├── views.py               # ビュー
│   ├── forms.py               # フォーム
│   ├── admin.py               # 管理者設定
│   ├── urls.py                # URL設定
│   └── templates/             # テンプレート
│       └── reservations/
│           ├── base.html      # ベーステンプレート
│           ├── index.html     # ホーム画面
│           ├── reservation_form.html    # 予約フォーム
│           ├── reservation_list.html    # 予約管理
│           ├── location_management.html # 場所管理
│           └── ...
├── static/                    # 静的ファイル
│   ├── css/
│   │   └── style.css         # メインCSS
│   └── js/
├── venv/                     # 仮想環境
├── manage.py                 # Django管理コマンド
├── requirements.txt          # 依存関係
└── README.md                 # プロジェクト説明
```
