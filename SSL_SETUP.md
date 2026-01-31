# Let's Encrypt SSL証明書設定ガイド

## 📋 前提条件

Let's EncryptでSSL証明書を取得するには、**ドメイン名が必要**です。
- IPアドレス（18.183.91.131）だけでは証明書を発行できません
- ドメインを取得し、DNSでAレコードを設定する必要があります

## 🔧 設定手順

### 1. ドメインの準備

1. ドメインを取得（例: `example.com`）
2. DNSプロバイダーで以下のAレコードを設定：
   ```
   Type: A
   Name: @ (または example.com)
   Value: 18.183.91.131
   TTL: 3600
   
   Type: A
   Name: www
   Value: 18.183.91.131
   TTL: 3600
   ```
3. DNSの反映を待つ（通常数分〜数時間）

### 2. SSL証明書の取得

リモートサーバーにSSH接続して、以下のコマンドを実行：

```bash
# リモートサーバーに接続
ssh yomohiro

# プロジェクトディレクトリに移動
cd /home/ubuntu/yomohiro_web

# 最新のコードを取得
git pull origin main

# SSL設定スクリプトを実行（ドメイン名を指定）
chmod +x setup_ssl.sh
./setup_ssl.sh your-domain.com
```

**例：**
```bash
./setup_ssl.sh example.com
```

### 3. 設定内容

スクリプトが自動で以下を実行します：

1. ✅ Certbotのインストール
2. ✅ ファイアウォールでHTTPS（443）を許可
3. ✅ Nginx設定をSSL用に更新
4. ✅ Let's EncryptでSSL証明書を取得
5. ✅ 自動更新の設定
6. ✅ `.env`ファイルを更新（SSL設定を有効化）
7. ✅ Gunicornを再起動

### 4. 確認

設定完了後、以下を確認：

```bash
# SSL証明書の確認
sudo certbot certificates

# 自動更新のテスト
sudo certbot renew --dry-run

# Nginx設定の確認
sudo nginx -t

# サービス状態の確認
sudo systemctl status nginx
sudo systemctl status gunicorn
```

### 5. アクセステスト

ブラウザで以下にアクセス：
- `https://your-domain.com`
- `https://www.your-domain.com`
- HTTP（`http://your-domain.com`）は自動的にHTTPSにリダイレクトされます

## 🔒 セキュリティ機能

設定されるセキュリティ機能：

- ✅ **HSTS (Strict-Transport-Security)**: ブラウザにHTTPSを強制
- ✅ **OCSP Stapling**: SSL証明書の検証を高速化
- ✅ **強力な暗号化**: TLS 1.2/1.3のみ、強力な暗号スイート
- ✅ **セキュリティヘッダー**: XSS保護、クリックジャッキング対策など
- ✅ **自動更新**: 証明書は自動で更新されます（90日ごと）

## 🔄 証明書の自動更新

Let's Encryptの証明書は90日で期限切れになりますが、Certbotが自動で更新します。

更新の確認：
```bash
sudo certbot renew --dry-run
```

## ⚠️ 注意事項

1. **ドメイン名が必要**: IPアドレスだけでは証明書を発行できません
2. **DNS設定**: ドメインのAレコードが正しく設定されている必要があります
3. **ポート80の開放**: Let's Encryptの認証にはポート80へのアクセスが必要です
4. **メールアドレス**: 証明書の期限切れ通知を受け取るメールアドレスを設定してください

## 🛠️ トラブルシューティング

### 証明書の取得に失敗する場合

```bash
# DNS設定を確認
nslookup your-domain.com
dig your-domain.com

# ポート80が開いているか確認
sudo ufw status

# Nginxのエラーログを確認
sudo tail -50 /var/log/nginx/error.log
```

### 証明書を手動で更新する場合

```bash
sudo certbot renew
sudo systemctl reload nginx
```

## 📚 参考リンク

- [Let's Encrypt公式サイト](https://letsencrypt.org/)
- [Certbot公式ドキュメント](https://certbot.eff.org/)

