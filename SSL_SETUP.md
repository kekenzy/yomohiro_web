# Let's Encrypt SSL証明書設定ガイド

本番の HTTPS 関連の環境変数（`SECURE_SSL_REDIRECT` 等）は [PRODUCTION.md](PRODUCTION.md) に記載しています。ドキュメント全体の索引は [DOCUMENTATION.md](DOCUMENTATION.md) です。

## 📋 前提条件

Let's EncryptでSSL証明書を取得するには、**ドメイン名が必要**です。
- IPアドレス（54.178.68.240）だけでは証明書を発行できません
- ドメインを取得し、DNSでAレコードを設定する必要があります

## 🔧 設定手順

### 1. ドメインの準備

1. ドメインを取得（例: `example.com`）
2. DNSプロバイダーで以下のAレコードを設定：
   ```
   Type: A
   Name: @ (または example.com)
   Value: 54.178.68.240
   TTL: 3600
   
   Type: A
   Name: www
   Value: 54.178.68.240
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

1. ✅ Certbotのインストール（**webroot** 方式。Nginx は止めずに証明書を取得）
2. ✅ ACME 用ディレクトリ `/var/www/html/.well-known/` の用意
3. ✅ ファイアウォールで HTTPS（443）を許可（`ufw` 利用時）
4. ✅ Nginx の `server_name` を指定ドメインに更新し、HTTP で証明書取得
5. ✅ Let's Encrypt で SSL 証明書を取得
6. ✅ Nginx を `config/nginx_ssl.conf` ベースの HTTPS 設定に切り替え
7. ✅ 自動更新のテスト（`certbot renew --dry-run`）
8. ✅ `.env` を更新（`ALLOWED_HOSTS` / `CSRF_TRUSTED_ORIGINS` / SSL 関連フラグ）
9. ✅ Gunicorn を再起動

**注意:** リポジトリの `config/nginx.conf` には HTTP 用の `/.well-known/acme-challenge/` の `location` が含まれています。サーバの Nginx が古い場合は、`git pull` 後に `config/nginx.conf` を反映するか、手動で同じ `location` を追加してください。

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

- ✅ **HSTS (Strict-Transport-Security)**: ブラウザに HTTPS を推奨（`preload` は付与しない。誤った証明書時にブラウザが完全にロックするのを防ぐ）
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

### `Killed` とだけ出て `./setup_ssl.sh` や `apt-get` が止まる場合

**原因の多くはメモリ不足（OOM）です。** 512MB プランの Lightsail では、`apt-get install certbot` の途中でカーネルがプロセスを強制終了し、シェルに `Killed` とだけ表示されることがあります。

**確認（SSH 先で）:**

```bash
sudo dmesg -T | tail -30 | grep -i 'killed process\|out of memory'
```

**対処（推奨）: スワップを 1〜2GB 追加してからスクリプトを再実行**

```bash
# 2GB スワップの例（未作成のときのみ）
sudo fallocate -l 2G /swapfile 2>/dev/null || sudo dd if=/dev/zero of=/swapfile bs=1M count=2048
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
grep -q '/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
free -h
```

その後、もう一度 `./setup_ssl.sh your-domain.com` を実行する。リポジトリの `setup_ssl.sh` は `--no-install-recommends certbot` でインストール負荷を抑えています。

一時的に **Gunicorn を止めてメモリを空ける**（`sudo systemctl stop gunicorn`）→ スクリプト実行 → 完了後 `sudo systemctl start gunicorn` も有効な場合があります。

### 証明書の取得に失敗する場合（`unauthorized` / `404` on `/.well-known/acme-challenge/`）

Let's Encrypt は **世界中から** `http://ドメイン/.well-known/acme-challenge/（ランダム）` に GET します。  
エラーに **自分の Lightsail の IP ではないアドレス**（例: `157.x` など）が出る場合、**Cloudflare のプロキシ**で別 IP が返っている可能性が高いです。その場合、検証リクエストが **あなたのサーバ上の Nginx** に届かず **404** になります。

**対処（どちらか）:**

1. **Cloudflare を使っている場合**  
   - 該当ホストの DNS で **プロキシをオフ**（**灰色の雲**・DNS のみ）にしてから、もう一度 `./setup_ssl.sh` を実行する。  
   - 証明書が取れたら、必要なら再度プロキシをオンにしてよい（更新時も同様のことがあるため、**DNS チャレンジ**や **Cloudflare Origin CA** の検討も可）。

2. **お名前.com などで A レコードだけの場合**  
   - **A レコード**が **Lightsail の静的 IP**（例: `54.178.68.240`）を向いているか確認する。  
   - 反映待ちのあと、`dig your-domain.com @8.8.8.8` で IP が一致するか見る。

**サーバ上の確認:**

```bash
# DNS がオリジン IP を向いているか（Cloudflare プロキシ OFF 時はこの IP になる）
dig +short your-domain.com A @8.8.8.8

# Nginx がチャレンジ用ディレクトリを返せるか（ローカル）
echo test | sudo tee /var/www/html/.well-known/acme-challenge/ping.txt
curl -s "http://127.0.0.1/.well-known/acme-challenge/ping.txt" -H "Host: your-domain.com"

sudo tail -50 /var/log/nginx/error.log
```

### 証明書を手動で更新する場合

```bash
sudo certbot renew
sudo systemctl reload nginx
```

### `NET::ERR_CERT_AUTHORITY_INVALID` と「HSTS のためアクセスできません」

**状況:** HTTPS の証明書がブラウザに信頼されない（自己署名・パス誤り・Let’s Encrypt 未取得など）のに、以前 **`Strict-Transport-Security`（HSTS）** を一度でも受け取っていると、Chrome は **警告を迂回できず** 接続できなくなります。

**いま取れる対処（順番に）:**

1. **別の経路でサーバに触れる**  
   - ブラウザでは **`http://（Lightsail の静的 IP）/`** を開く（例: `http://54.178.68.240/`）。`nginx_ssl.conf` では IP 向け HTTP は **HTTPS に飛ばさない** ブロックになっているため、**証明書が壊れていてもサイトの中身の復旧作業ができる**ことが多いです。  
   - または **SSH**（`ssh yomohiro` など）で接続する。

2. **この PC の Chrome にだけ HSTS 記録を消す（一時的）**  
   - アドレスバーに `chrome://net-internals/#hsts` と入力。  
   - **「Delete domain security policies」** に `yomohirokan.com` を入れて **Delete**。  
   - `www.yomohirokan.com` も同様に試す。  
   - これでも **`https://` のままでは証明書が無効ならエラーは残る**が、**HSTS だけが原因の「一切進めない」状態**は緩むことがあります。根本は **有効な証明書**（下記）。

3. **根本対応: スワップを足してから `setup_ssl.sh` を最後まで成功させる**  
   - メモリ不足で `Killed` になった場合は、同じページの **「`Killed` で止まる」** の節（スワップ追加）を先に実施。  
   - `sudo nginx -t` で設定が通るか確認。`/etc/letsencrypt/live/ドメイン/` が無いのに `nginx_ssl.conf` だけ載っていると、Nginx が起動しない／変な証明書になることがあります。

4. **リポジトリを `git pull` したうえで** `config/nginx_ssl.conf` をサーバに反映し、`preload` / `includeSubDomains` を付けない現行版にすると、**同じ事故で二度とブラウザが完全ロックしにくく**なります。

## 📚 参考リンク

- [Let's Encrypt公式サイト](https://letsencrypt.org/)
- [Certbot公式ドキュメント](https://certbot.eff.org/)






