# 本番環境の設定

Django アプリ（`reservation_system/settings.py`）が参照する **環境変数** と、本番で必要な **付帯作業** をまとめています。デプロイ手順そのものは [DEPLOYMENT.md](DEPLOYMENT.md) を参照してください。

---

## 前提

- 本番では **`DEBUG=False`** を必ず設定する。
- 秘密情報（`SECRET_KEY`、API トークン、DB パスワードなど）は **リポジトリに含めず**、サーバの `.env` やシークレット管理で渡す。
- 設定の読み込みは **`python-decouple`**（`config(...)`）経由。`.env` はデプロイ先のプロジェクトルート等に配置する。

---

## 環境変数一覧

### 必須に近い（本番）

| 変数名 | 説明 | 例・備考 |
|--------|------|----------|
| `SECRET_KEY` | Django の署名・暗号化用 | `python3 -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"` で生成 |
| `DEBUG` | 本番では `False` | `False` |
| `ALLOWED_HOSTS` | 許可するホスト（カンマ区切り） | `yomohirokan.com,www.yomohirokan.com,54.x.x.x` など。未設定時は `settings.py` の既定に本番ドメインを含む |
| `CSRF_TRUSTED_ORIGINS` | HTTPS オリジン（カンマ区切り、スキーム付き） | `https://yomohirokan.com,https://www.yomohirokan.com`。未設定時は `settings.py` の既定を使用 |
| `DATABASE_URL` | PostgreSQL 接続 URL | `postgresql://USER:PASSWORD@HOST:5432/DBNAME` |

### HTTPS / セキュリティ（`DEBUG=False` 時の既定）

`settings.py` では `DEBUG=False` のとき次を参照します（本番では通常 `True` にする）。

| 変数名 | 説明 | 本番の目安 |
|--------|------|------------|
| `SECURE_SSL_REDIRECT` | HTTP→HTTPS リダイレクト | `True`（SSL 構成後） |
| `SESSION_COOKIE_SECURE` | セッション Cookie を HTTPS のみ | `True` |
| `CSRF_COOKIE_SECURE` | CSRF Cookie を HTTPS のみ | `True` |

SSL 手順は [SSL_SETUP.md](SSL_SETUP.md) および [DEPLOYMENT.md](DEPLOYMENT.md) の該当節を参照。

### メール送信

| 変数名 | 説明 |
|--------|------|
| `EMAIL_BACKEND` | 本番では SMTP 等（例: `django.core.mail.backends.smtp.EmailBackend`） |
| `EMAIL_HOST` | SMTP ホスト |
| `EMAIL_PORT` | ポート（587 等） |
| `EMAIL_USE_TLS` | TLS 使用の有無 |
| `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` | SMTP 認証 |
| `DEFAULT_FROM_EMAIL` | 送信元アドレス |
| `SERVER_EMAIL` | サーバエラー通知等の送信元 |

開発では未設定でもコンソールバックエンドが既定で動きます。

### Square（決済）

| 変数名 | 説明 |
|--------|------|
| `SQUARE_APPLICATION_ID` | Square アプリケーション ID |
| `SQUARE_ACCESS_TOKEN` | アクセストークン |
| `SQUARE_ENVIRONMENT` | `sandbox` または `production` |
| `SQUARE_LOCATION_ID` | ロケーション ID |

フロー詳細は [SQUARE_PAYMENT_FLOW.md](SQUARE_PAYMENT_FLOW.md)、環境の切り替えは [SQUARE_ENVIRONMENT_SETUP.md](SQUARE_ENVIRONMENT_SETUP.md)。

### LINE Login（SSO）

ログイン画面に「LINEでログイン」を出すには **両方とも** 設定する（片方だけではボタンは非表示）。

| 変数名 | 説明 |
|--------|------|
| `LINE_CHANNEL_ID` | LINE Developers の **LINE Login** チャネルの Channel ID |
| `LINE_CHANNEL_SECRET` | 同チャネルの Channel secret |

**コールバック URL（LINE Developers コンソールに登録）**

本番ドメインを `https://YOUR_DOMAIN` とするときの例：

```
https://YOUR_DOMAIN/accounts/line/login/callback/
```

- 末尾のスラッシュを含める。
- **apex と `www` の両方**からアクセスする場合は、LINE に **両方の URL** を登録する（ホストが 1 文字でも違うと `Invalid redirect_uri`）。
- OAuth の `redirect_uri` は **HTTPS** 前提。オリジンが HTTP（`DEBUG=True` のまま本番など）だと **http://** で送られ、LINE 側が **https://** だけ許可していると必ず不一致になる。**本番は `DEBUG=False`**。どうしても `DEBUG=True` にする必要があるときは `.env` に `ACCOUNT_DEFAULT_HTTP_PROTOCOL=https` を明示する。
- 管理画面の **ソーシャルアプリケーション** に古い LINE 用エントリが複数あると、`SOCIALACCOUNT_PROVIDERS` と食い違うことがある。不要なら削除し、サイトに紐づく設定を 1 つに揃える。

**`Invalid redirect_uri` が消えないとき（ブラウザの authorize URL に `redirect_uri=https://yomohirokan.com/...` と出ているのに 400 になる場合）**

LINE は **そのリクエストの `client_id` が指すチャネル 1 つ**の「LINE ログイン」タブに書かれたコールバックだけを見ます。次を順に確認する。

1. [LINE Developers コンソール](https://developers.line.biz/console/) を開き、一覧から **チャネルを開く**。
2. **基本設定**で **Channel ID** を確認する。ネットワークタブの `client_id=`（例: `2009743735`）と **同じ数字のチャネル**であること（別チャネルの ID を `.env` に入れていないか）。
3. そのチャネルの種類が **LINE Login** であること（Messaging API だけのチャネルではないこと）。
4. **LINE ログイン**タブ → **コールバック URL** に、次を **コピペで 1 行追加し保存**する（前後に空白を入れない）。複数行あればよい。
   - `https://yomohirokan.com/accounts/line/login/callback/`
   - `www` からもアクセスするなら `https://www.yomohirokan.com/accounts/line/login/callback/` も別行で追加。
5. **基本設定** → **OpenID Connect** でメール利用の申請が未承認なら、`.env` で `LINE_LOGIN_SCOPE=profile,openid` のみにする（`email` は申請承認後に追加。公式は「メール取得は申請必須」としている）。Gunicorn 再起動が必要。

Django **Sites**（管理画面 → Sites）は **本番ドメイン**（例: `yomohirokan.com`）に直す。`example.com` のままだとメール内リンクなどはずれるが、`redirect_uri` 自体は通常ブラウザの Host で組み立てられる。

### 任意・その他

| 変数名 | 説明 |
|--------|------|
| `LINE_CHANNEL_*` 未設定 | LINE ボタンは表示されない（メール／パスワードログインのみ）。 |

---

## Django / アプリ固有の本番作業

### 1. マイグレーション

コードに新しいマイグレーションが含まれるたびに本番で実行する。

```bash
python manage.py migrate --noinput
```

`django.contrib.sites` / `allauth`（account・socialaccount）を有効にしている場合も、初回デプロイ後に同コマンドでテーブルが作成される。

### 2. 静的ファイル

```bash
python manage.py collectstatic --noinput
```

WhiteNoise 利用時も、デプロイスクリプトに含めることが多い。

### 3. Sites フレームワーク（`SITE_ID = 1`）

`django.contrib.sites` を使用しているため、**管理画面 → Sites** で `example.com` を **実際のドメイン** に変更する（メール本文の絶対 URL 等で使われる場合がある）。

### 4. プロセス再起動

`.env` を変更したあとは **Gunicorn（または uwsgi）を再起動** して環境変数を読み直す。

```bash
sudo systemctl restart gunicorn
```

（ユニット名は環境に合わせる。）

---

## 関連ドキュメント

| ドキュメント | 内容 |
|--------------|------|
| [DOCUMENTATION.md](DOCUMENTATION.md) | リポジトリ内 Markdown の索引 |
| [DEPLOYMENT.md](DEPLOYMENT.md) | Lightsail・GitHub Actions デプロイ |
| [SSL_SETUP.md](SSL_SETUP.md) | Let's Encrypt 等 |
| [LIGHTSAIL_NETWORK_SETUP.md](LIGHTSAIL_NETWORK_SETUP.md) | Lightsail ネットワーク |
| [SQUARE_PAYMENT_FLOW.md](SQUARE_PAYMENT_FLOW.md) | Square 決済フロー |
| [FEATURES.md](FEATURES.md) | 機能一覧（開発者向け） |

---

## `.env` 記述例（本番・イメージ）

実際の値は置き換えること。**このブロックをそのままコミットしない。**

```env
DEBUG=False
SECRET_KEY=（十分に長いランダム文字列）
ALLOWED_HOSTS=yomohirokan.com,www.yomohirokan.com,（サーバIPがあれば追加）
CSRF_TRUSTED_ORIGINS=https://yomohirokan.com,https://www.yomohirokan.com
DATABASE_URL=postgresql://user:password@localhost:5432/reservation_db

SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True

EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.example.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
DEFAULT_FROM_EMAIL=noreply@your-domain.com

SQUARE_APPLICATION_ID=
SQUARE_ACCESS_TOKEN=
SQUARE_ENVIRONMENT=production
SQUARE_LOCATION_ID=

LINE_CHANNEL_ID=
LINE_CHANNEL_SECRET=
```

LINE を使わない場合は `LINE_CHANNEL_ID` / `LINE_CHANNEL_SECRET` を空のままにするか、行ごと省略してよい。
