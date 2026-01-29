# Django Admin ログイン情報

## デフォルト管理者アカウント

### 管理者アカウント

- **ユーザー名:** `admin`
- **パスワード:** `admin123`
- **メールアドレス:** `admin@example.com`

### アクセス情報

- **Admin画面URL:** http://localhost:8001/admin/
- **メインサイトURL:** http://localhost:8001/

## パスワード変更方法

### 方法1: Djangoシェルから変更

```bash
# Docker環境の場合
docker-compose exec web python manage.py changepassword admin

# ローカル環境の場合
python manage.py changepassword admin
```

### 方法2: Admin画面から変更

1. Admin画面にログイン
2. 「ユーザー」→「ユーザー」をクリック
3. `admin`ユーザーを選択
4. 「パスワード」セクションで「このフォーム」を選択
5. 新しいパスワードを入力して保存

## 新しいスーパーユーザーを作成する場合

```bash
# Docker環境の場合
docker-compose exec web python manage.py createsuperuser

# ローカル環境の場合
python manage.py createsuperuser
```

## セキュリティ注意事項

⚠️ **重要:** 
- 本番環境では、必ず強力なパスワードに変更してください
- デフォルトのパスワード（`admin123`）は開発環境のみで使用してください
- 定期的にパスワードを変更することを推奨します







