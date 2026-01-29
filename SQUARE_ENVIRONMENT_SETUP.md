# Square API環境変数設定ガイド

## SQUARE_ENVIRONMENT

### 設定値

- **`sandbox`**: 開発・テスト環境
- **`production`**: 本番環境

### 説明

Square APIを使用する環境を指定します。

#### sandbox（開発環境）

- **用途**: 開発・テスト時
- **特徴**:
  - テスト用の決済が可能
  - 実際の決済は発生しない
  - テスト用のカード情報を使用可能
- **設定例**:
  ```env
  SQUARE_ENVIRONMENT=sandbox
  ```

#### production（本番環境）

- **用途**: 本番運用時
- **特徴**:
  - 実際の決済が発生する
  - 実際のカード情報が必要
  - 決済手数料が発生（日本では3.6%）
- **設定例**:
  ```env
  SQUARE_ENVIRONMENT=production
  ```

### コードでの使用箇所

```python
# reservations/views.py
def get_square_client():
    from django.conf import settings
    from square.environment import SquareEnvironment
    
    # SQUARE_ENVIRONMENTの値に応じて環境を設定
    environment = SquareEnvironment.SANDBOX if settings.SQUARE_ENVIRONMENT == 'sandbox' else SquareEnvironment.PRODUCTION
    
    client = Square(
        token=settings.SQUARE_ACCESS_TOKEN,
        environment=environment
    )
    
    return client
```

---

## SQUARE_WEBHOOK_SECRET

### 設定値

- **空文字列**: 開発環境（署名検証をスキップ）
- **シークレット文字列**: 本番環境（必須）

### 説明

Squareから送信されるWebhookの署名検証に使用するシークレットキーです。

#### 取得方法

1. [Square Developer Portal](https://developer.squareup.com/)にログイン
2. アプリケーションを選択
3. **Webhooks** セクションに移動
4. **署名キー（Signature Key）** を確認または生成

#### 開発環境での設定

開発環境では空文字列でも動作しますが、セキュリティ上設定を推奨します：

```env
# 開発環境（空でも動作するが、設定を推奨）
SQUARE_WEBHOOK_SECRET=
```

または、Sandbox環境の署名キーを設定：

```env
# Sandbox環境の署名キーを設定
SQUARE_WEBHOOK_SECRET=your-sandbox-signature-key
```

#### 本番環境での設定

**本番環境では必ず設定してください**。Webhookの改ざんを防ぐために必須です：

```env
# 本番環境（必須）
SQUARE_WEBHOOK_SECRET=your-production-signature-key
```

### コードでの使用箇所

```python
# reservations/views.py
@require_http_methods(["POST"])
def square_webhook(request):
    from decouple import config as decouple_config
    
    # Webhook署名の検証
    signature = request.headers.get('X-Square-Signature', '')
    webhook_secret = decouple_config('SQUARE_WEBHOOK_SECRET', default='')
    
    if webhook_secret:
        # 署名検証を実行
        body = request.body
        expected_signature = hmac.new(
            webhook_secret.encode('utf-8'),
            body,
            hashlib.sha256
        ).hexdigest()
        
        if not hmac.compare_digest(signature, expected_signature):
            return JsonResponse({'error': 'Invalid signature'}, status=401)
    
    # Webhook処理を続行...
```

### セキュリティ上の注意

1. **本番環境では必須**
   - Webhookの署名検証なしでは、悪意のあるリクエストを受け入れる可能性があります
   - 必ず`SQUARE_WEBHOOK_SECRET`を設定してください

2. **シークレットの管理**
   - 環境変数で管理（`.env`ファイルに保存）
   - Gitリポジトリにコミットしない（`.gitignore`に追加）
   - 本番環境では環境変数やシークレット管理サービスを使用

3. **署名検証の仕組み**
   - SquareはWebhook送信時に、リクエストボディとシークレットキーからHMAC-SHA256署名を生成
   - `X-Square-Signature`ヘッダーに署名を含めて送信
   - サーバー側で同じ方法で署名を計算し、一致するか確認

---

## 設定例

### 開発環境（Sandbox）

```env
SQUARE_APPLICATION_ID=sandbox-sq0idb-Klqy4yYEmO_5_1Ea9msc3w
SQUARE_ACCESS_TOKEN=EAAAl5UHQGekKNOWGRkLWMJ7NTohmkFaFRZXL2wioazmvTMi-PcFmU9SHpwwdSSe
SQUARE_ENVIRONMENT=sandbox
SQUARE_LOCATION_ID=LHQHHBA22J5E1
SQUARE_WEBHOOK_SECRET=  # 空でも動作するが、設定を推奨
```

### 本番環境（Production）

```env
SQUARE_APPLICATION_ID=your-production-application-id
SQUARE_ACCESS_TOKEN=your-production-access-token
SQUARE_ENVIRONMENT=production
SQUARE_LOCATION_ID=your-production-location-id
SQUARE_WEBHOOK_SECRET=your-production-webhook-secret  # 必須
```

---

## トラブルシューティング

### SQUARE_ENVIRONMENT

**問題**: 決済が失敗する

- **確認事項**:
  - `SQUARE_ENVIRONMENT`が正しく設定されているか
  - Sandbox環境では`sandbox`、本番環境では`production`
  - アクセストークンが環境に一致しているか（Sandbox用トークンはSandbox環境でのみ使用可能）

### SQUARE_WEBHOOK_SECRET

**問題**: Webhookが受け取れない

- **確認事項**:
  - 署名キーが正しく設定されているか
  - Square Developer PortalでWebhook URLが正しく設定されているか
  - HTTPSが有効になっているか（WebhookはHTTPS必須）

**問題**: Webhookの署名検証が失敗する

- **確認事項**:
  - `SQUARE_WEBHOOK_SECRET`が正しく設定されているか
  - Square Developer Portalの署名キーと一致しているか
  - リクエストボディが改ざんされていないか

---

## 参考資料

- [Square Webhooks Documentation](https://developer.squareup.com/docs/webhooks/overview)
- [Square Webhook Signature Verification](https://developer.squareup.com/docs/webhooks/step4validate)
- [Square Developer Portal](https://developer.squareup.com/)








