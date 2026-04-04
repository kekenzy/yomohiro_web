# AWS Lightsail デプロイ手順書

このドキュメントでは、GitHub ActionsとAWS Lightsailを使用した自動デプロイの設定手順を説明します。

## 📋 前提条件

- AWSアカウント
- GitHubアカウント
- ドメイン（オプション、推奨）

## 🚀 デプロイの流れ

```
GitHub (push) → GitHub Actions (CI/CD) → AWS Lightsail (本番環境)
```

## 📦 1. AWS Lightsailインスタンスの作成

### 1.1 インスタンスの作成

1. [AWS Lightsail Console](https://lightsail.aws.amazon.com/)にアクセス
2. 「インスタンスの作成」をクリック
3. 以下の設定を選択：
   - **リージョン**: Tokyo (ap-northeast-1)
   - **プラットフォーム**: Linux/Unix
   - **設計図**: OS のみ → Ubuntu 22.04 LTS
   - **インスタンスプラン**: $3.50/月 (512MB RAM, 1vCPU, 20GB SSD)
   - **インスタンス名**: yomohiro-web

### 1.2 静的IPアドレスの割り当て

1. 作成したインスタンスの詳細ページを開く
2. 「ネットワーキング」タブをクリック
3. 「静的IPアドレスの作成」をクリック
4. 名前を付けて作成
5. 作成した静的IPをメモ（例: 54.64.209.76）

### 1.3 SSHキーペアのダウンロード

1. インスタンスの詳細ページで「アカウントページ」タブをクリック
2. 「デフォルトのキー」をダウンロード
3. キーファイルを安全な場所に保存

または、新しいSSHキーペアを作成：

```bash
ssh-keygen -t rsa -b 4096 -C "lightsail-deploy-key"
```

## 🔧 2. Lightsailインスタンスの初期設定

### 2.1 SSHで接続

```bash
# ダウンロードしたキーファイルの権限を変更
chmod 400 LightsailDefaultKey-ap-northeast-1.pem

# SSHで接続
ssh -i LightsailDefaultKey-ap-northeast-1.pem ubuntu@YOUR_LIGHTSAIL_IP
```

### 2.2 初期セットアップスクリプトの実行

Lightsailインスタンス上で実行：

```bash
# GitHubリポジトリをクローン（事前にGitHubにプッシュしておく）
cd /home/ubuntu
git clone https://github.com/YOUR_USERNAME/yomohiro_web.git
cd yomohiro_web

# セットアップスクリプトを実行
chmod +x setup_lightsail.sh
./setup_lightsail.sh
```

スクリプトが以下を自動で実行します：
- システムのアップデート
- 必要なパッケージのインストール（Python, Nginx等）
- 仮想環境の作成
- 依存関係のインストール
- データベースの初期化
- 管理者ユーザーの作成
- Gunicorn/Nginxの設定

### 2.3 環境変数の設定

`.env`ファイルを編集：

```bash
cd /home/ubuntu/yomohiro_web
nano .env
```

以下の内容を設定：

```env
SECRET_KEY=your-long-random-secret-key-here
DEBUG=False
ALLOWED_HOSTS=your-domain.com,www.your-domain.com,YOUR_LIGHTSAIL_IP
SECURE_SSL_REDIRECT=False  # SSL設定後にTrueに変更
SESSION_COOKIE_SECURE=False  # SSL設定後にTrueに変更
CSRF_COOKIE_SECURE=False  # SSL設定後にTrueに変更
```

SECRET_KEYの生成：

```python
python3 -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### 2.4 サービスの確認

```bash
# Gunicornの状態確認
sudo systemctl status gunicorn

# Nginxの状態確認
sudo systemctl status nginx

# ログの確認
tail -f /home/ubuntu/yomohiro_web/logs/gunicorn_error.log
```

## 🔐 3. GitHub Secretsの設定

### 3.1 SSH秘密鍵の準備

```bash
# SSH秘密鍵の内容をコピー
cat ~/.ssh/lightsail_key  # または LightsailDefaultKey-ap-northeast-1.pem
```

### 3.2 GitHubリポジトリにSecretsを追加

1. GitHubリポジトリページを開く
2. Settings → Secrets and variables → Actions
3. 「New repository secret」をクリック
4. 以下の3つのSecretを追加：

| Name | Value |
|------|-------|
| `LIGHTSAIL_HOST` | LightsailインスタンスのIPアドレス（例: 54.64.209.76） |
| `LIGHTSAIL_USER` | `ubuntu` |
| `LIGHTSAIL_SSH_KEY` | SSH秘密鍵の内容全体 |

## 🌐 4. ドメインの設定（オプション）

### 4.1 DNSレコードの追加

お使いのDNSプロバイダー（お名前.com、Route 53等）で以下のレコードを追加：

```
Type: A
Name: @ (または your-domain.com)
Value: YOUR_LIGHTSAIL_IP
TTL: 3600

Type: A
Name: www
Value: YOUR_LIGHTSAIL_IP
TTL: 3600
```

### 4.2 Nginx設定の更新

```bash
sudo nano /etc/nginx/sites-available/yomohiro_web
```

`server_name`を実際のドメインに変更：

```nginx
server_name your-domain.com www.your-domain.com;
```

Nginxを再起動：

```bash
sudo nginx -t
sudo systemctl restart nginx
```

### 4.3 SSL証明書の設定（Let's Encrypt）

```bash
# Certbotのインストール
sudo apt-get update
sudo apt-get install -y certbot python3-certbot-nginx

# SSL証明書の取得と自動設定
sudo certbot --nginx -d your-domain.com -d www.your-domain.com

# 自動更新の確認
sudo certbot renew --dry-run
```

SSL証明書設定後、`.env`ファイルを更新：

```bash
nano /home/ubuntu/yomohiro_web/.env
```

以下をTrueに変更：

```env
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
```

Gunicornを再起動：

```bash
sudo systemctl restart gunicorn
```

## 🔄 5. 自動デプロイの動作確認

### 5.1 変更をプッシュ

```bash
# ローカルで変更を加える
git add .
git commit -m "Test deployment"
git push origin main
```

### 5.2 GitHub Actionsの確認

1. GitHubリポジトリページを開く
2. 「Actions」タブをクリック
3. 最新のワークフロー実行を確認
4. テストとデプロイが成功することを確認

### 5.3 本番環境の確認

ブラウザで以下にアクセス：
- `http://YOUR_LIGHTSAIL_IP` または `https://your-domain.com`
- 管理画面: `http://YOUR_LIGHTSAIL_IP/admin` または `https://your-domain.com/admin`

## 🛠️ トラブルシューティング

### デプロイが失敗する場合

```bash
# Lightsailインスタンスでログを確認
tail -f /home/ubuntu/yomohiro_web/logs/gunicorn_error.log
tail -f /var/log/nginx/yomohiro_error.log

# サービスの状態を確認
sudo systemctl status gunicorn
sudo systemctl status nginx

# 手動でデプロイスクリプトを実行
cd /home/ubuntu/yomohiro_web
./deploy_lightsail.sh
```

### GitHub Actionsでエラーが出る場合

1. GitHub Secretsが正しく設定されているか確認
2. SSH接続が成功するか確認：

```bash
ssh -i ~/.ssh/lightsail_key ubuntu@YOUR_LIGHTSAIL_IP
```

3. Lightsailのファイアウォール設定を確認

### 502 Bad Gateway エラー

```bash
# Gunicornが起動しているか確認
sudo systemctl status gunicorn

# 起動していない場合
sudo systemctl start gunicorn
sudo systemctl restart nginx
```

## 📊 メンテナンスコマンド

### ログの確認

```bash
# アプリケーションログ
tail -f /home/ubuntu/yomohiro_web/logs/gunicorn_error.log
tail -f /home/ubuntu/yomohiro_web/logs/gunicorn_access.log

# Nginxログ
sudo tail -f /var/log/nginx/yomohiro_error.log
sudo tail -f /var/log/nginx/yomohiro_access.log
```

### データベースのバックアップ

```bash
cd /home/ubuntu/yomohiro_web
source venv/bin/activate

# バックアップの作成
python manage.py dumpdata > backup_$(date +%Y%m%d_%H%M%S).json

# バックアップからの復元
python manage.py loaddata backup_20251011_120000.json
```

### サービスの再起動

```bash
# Gunicornのみ再起動
sudo systemctl restart gunicorn

# Nginxのみ再起動
sudo systemctl restart nginx

# 両方再起動
sudo systemctl restart gunicorn nginx
```

## 💰 コスト見積もり

| サービス | 月額コスト |
|---------|-----------|
| Lightsail (512MB) | $3.50 |
| データ転送 (1TB含む) | $0.00 |
| **合計** | **$3.50/月** |

※ SSL証明書（Let's Encrypt）は無料です

## 🔒 セキュリティのベストプラクティス

1. **定期的なアップデート**
   ```bash
   sudo apt-get update && sudo apt-get upgrade -y
   ```

2. **ファイアウォールの設定**
   - 必要なポートのみ開放（80, 443, 22）

3. **SECRET_KEYの保護**
   - 本番環境では必ず変更
   - `.env`ファイルをGitにコミットしない

4. **定期バックアップ**
   - データベースの定期バックアップを設定

5. **SSL証明書の自動更新**
   - Certbotが自動で更新（確認: `sudo certbot renew --dry-run`）

## 📚 参考リンク

- [Django Deployment Checklist](https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/)
- [Gunicorn Documentation](https://docs.gunicorn.org/)
- [Nginx Documentation](https://nginx.org/en/docs/)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [AWS Lightsail Documentation](https://docs.aws.amazon.com/lightsail/)

## ✅ チェックリスト

デプロイ前の確認事項：

- [ ] Lightsailインスタンスが起動している
- [ ] 静的IPアドレスが割り当てられている
- [ ] SSH接続ができる
- [ ] GitHubリポジトリにコードがプッシュされている
- [ ] GitHub Secretsが設定されている（3つ）
- [ ] .envファイルが正しく設定されている
- [ ] Gunicornが起動している
- [ ] Nginxが起動している
- [ ] ドメインのDNS設定が完了している（オプション）
- [ ] SSL証明書が設定されている（オプション）

## 🎉 完了！

これで、GitHubにプッシュするだけで自動的にAWS Lightsailにデプロイされるようになりました！

