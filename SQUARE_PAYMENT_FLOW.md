# Square API決済機能 実装フロー

## 概要

DjangoアプリケーションにSquare APIを統合し、会員登録時の決済処理を実装しました。

## 実装内容

### 1. 必要な設定

#### 1.1 環境変数の設定

`env.example`に以下の設定を追加：

```env
# Square API settings
SQUARE_APPLICATION_ID=sandbox-sq0idb-Klqy4yYEmO_5_1Ea9msc3w
SQUARE_ACCESS_TOKEN=EAAAl5UHQGekKNOWGRkLWMJ7NTohmkFaFRZXL2wioazmvTMi-PcFmU9SHpwwdSSe
SQUARE_ENVIRONMENT=sandbox
SQUARE_LOCATION_ID=
SQUARE_WEBHOOK_SECRET=
```

#### 1.2 Django設定（`settings.py`）

```python
# Square API settings
SQUARE_APPLICATION_ID = config('SQUARE_APPLICATION_ID', default='sandbox-sq0idb-Klqy4yYEmO_5_1Ea9msc3w')
SQUARE_ACCESS_TOKEN = config('SQUARE_ACCESS_TOKEN', default='EAAAl5UHQGekKNOWGRkLWMJ7NTohmkFaFRZXL2wioazmvTMi-PcFmU9SHpwwdSSe')
SQUARE_ENVIRONMENT = config('SQUARE_ENVIRONMENT', default='sandbox')  # sandbox or production
SQUARE_LOCATION_ID = config('SQUARE_LOCATION_ID', default='')
```

#### 1.3 依存関係（`requirements.txt`）

```
squareup==38.0.0.20241218
```

### 2. データベースモデル

#### 2.1 PaymentTransactionモデル

決済トランザクション情報を保存するモデル：

```python
class PaymentTransaction(models.Model):
    """Square決済トランザクション"""
    STATUS_CHOICES = [
        ('pending', '保留中'),
        ('completed', '完了'),
        ('failed', '失敗'),
        ('cancelled', 'キャンセル'),
    ]

    reservation = models.ForeignKey(Reservation, on_delete=models.CASCADE, null=True, blank=True)
    member_profile = models.ForeignKey(MemberProfile, on_delete=models.CASCADE, null=True, blank=True)
    
    # Square決済情報
    square_payment_id = models.CharField(max_length=255, unique=True, null=True, blank=True)
    square_order_id = models.CharField(max_length=255, null=True, blank=True)
    payment_link_id = models.CharField(max_length=255, null=True, blank=True)
    payment_link_url = models.URLField(null=True, blank=True)
    
    # 決済情報
    amount = models.DecimalField(max_digits=10, decimal_places=0)
    currency = models.CharField(max_length=3, default='JPY')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # メタデータ
    metadata = models.JSONField(default=dict, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

### 3. 会員登録フロー

#### 3.1 4ステップの会員登録ウィザード

1. **Step1: 基本情報**
   - 氏名、性別、生年月日
   - メールアドレス、パスワード
   - 電話番号、郵便番号、住所

2. **Step2: プラン選択**
   - 会員プランの選択
   - デフォルトプランが自動選択

3. **Step3: 顔写真登録**
   - ファイルから選択
   - カメラで撮影

4. **Step4: クレジットカード情報**
   - カード番号、有効期限、CVC

#### 3.2 会員登録完了後の処理

```python
# Step4完了後
if plan and plan.price > 0:
    # プラン料金がある場合
    # 1. ユーザーとプロフィールを一時保存
    # 2. Square決済リンクを生成
    # 3. Square決済ページにリダイレクト
else:
    # プラン料金が0円の場合
    # 1. 会員登録を完了
    # 2. 自動ログイン
    # 3. 完了メールを送信
```

### 4. Square決済処理

#### 4.1 決済リンクの生成

```python
def create_payment_link(request, amount, order_id=None, description=''):
    """Square決済リンクを作成"""
    client = get_square_client()
    
    result = client.checkout.payment_links.create(
        idempotency_key=f"{order_id}_{datetime.now().timestamp()}",
        quick_pay={
            'name': description or '決済',
            'price_money': {
                'amount': int(amount),
                'currency': 'JPY'
            }
        }
    )
    
    if result.is_success():
        payment_link = result.body.payment_link
        return {
            'success': True,
            'payment_link_id': payment_link.id,
            'payment_link_url': payment_link.url,
            'order_id': payment_link.order_id
        }
```

#### 4.2 決済トランザクションの保存

```python
transaction = PaymentTransaction.objects.create(
    member_profile=profile,
    payment_link_id=result['payment_link_id'],
    payment_link_url=result['payment_link_url'],
    square_order_id=result.get('order_id'),
    amount=plan.price,
    status='pending'
)
```

### 5. Webhook処理

#### 5.1 Webhookエンドポイント

```python
@require_http_methods(["POST"])
def square_webhook(request):
    """Square Webhookエンドポイント"""
    # 1. 署名検証（本番環境では必須）
    # 2. 決済イベントの処理
    # 3. トランザクションの更新
    # 4. 会員登録完了メールの送信
```

#### 5.2 決済完了時の処理

```python
if event_type == 'payment.created' or event_type == 'payment.updated':
    payment = event_data.get('object', {}).get('payment', {})
    status = payment.get('status')
    
    if status == 'COMPLETED':
        # トランザクションを更新
        transaction.status = 'completed'
        transaction.save()
        
        # 会員登録の場合は完了メールを送信
        if transaction.member_profile:
            send_registration_complete_email(transaction.member_profile.user)
```

### 6. 決済完了後のリダイレクト

#### 6.1 決済完了ページ

```python
def payment_complete(request):
    """決済完了後のリダイレクト先"""
    payment_link_id = request.GET.get('payment_link_id')
    
    transaction = PaymentTransaction.objects.get(payment_link_id=payment_link_id)
    
    if transaction.status == 'completed':
        if transaction.member_profile:
            # 会員登録の場合は自動ログイン
            user = transaction.member_profile.user
            login(request, user)
            return redirect('reservations:index')
```

## フロー図

```
会員登録開始
    ↓
Step1: 基本情報入力
    ↓
Step2: プラン選択
    ↓
Step3: 顔写真登録
    ↓
Step4: クレジットカード情報入力
    ↓
プラン料金の確認
    ├─ 料金 > 0円
    │   ↓
    │   ユーザー・プロフィール作成（一時保存）
    │   ↓
    │   Square決済リンク生成
    │   ↓
    │   Square決済ページへリダイレクト
    │   ↓
    │   ユーザーが決済完了
    │   ↓
    │   Square Webhook受信
    │   ↓
    │   トランザクション更新（status='completed'）
    │   ↓
    │   会員登録完了メール送信
    │   ↓
    │   会員登録完了
    │
    └─ 料金 = 0円
        ↓
        ユーザー・プロフィール作成
        ↓
        自動ログイン
        ↓
        会員登録完了メール送信
        ↓
        会員登録完了
```

## URL設定

```python
urlpatterns = [
    # 会員登録
    path('member-registration/', views.member_registration, name='member_registration'),
    
    # 決済
    path('payment/create/', views.payment_create, name='payment_create'),
    path('payment/create/<int:reservation_id>/', views.payment_create, name='payment_create_reservation'),
    path('payment/complete/', views.payment_complete, name='payment_complete'),
    
    # Webhook
    path('webhooks/square/', views.square_webhook, name='square_webhook'),
]
```

## テスト方法

### 1. Sandbox環境でのテスト

1. Square Developer PortalでSandboxアカウントを作成
2. テスト用のアクセストークンを取得
3. 環境変数に設定

### 2. テスト用カード情報

Square Sandboxでは以下のテストカードが使用可能：

- **成功**: 4111 1111 1111 1111
- **失敗**: 4000 0000 0000 0002
- **3D Secure**: 4000 0027 6000 3184

### 3. Webhookのテスト

1. Square Developer PortalでWebhook URLを設定
2. テストイベントを送信
3. ログで確認

## 本番環境への移行

### 1. 環境変数の変更

```env
SQUARE_ENVIRONMENT=production
SQUARE_ACCESS_TOKEN=<本番環境のアクセストークン>
SQUARE_WEBHOOK_SECRET=<Webhook署名検証用のシークレット>
```

### 2. Webhook URLの設定

Square Developer Portalで本番環境のWebhook URLを設定：
```
https://your-domain.com/webhooks/square/
```

### 3. SSL証明書

WebhookはHTTPS必須のため、SSL証明書を設定してください。

## 注意事項

1. **セキュリティ**
   - アクセストークンは環境変数で管理
   - Webhook署名検証を必ず実装
   - クレジットカード情報は暗号化して保存

2. **エラーハンドリング**
   - 決済リンク生成失敗時の処理
   - Webhook受信失敗時の処理
   - タイムアウト処理

3. **ログ**
   - 決済トランザクションのログ記録
   - エラー時の詳細ログ

4. **料金**
   - 日本でのオンライン決済手数料: 3.6%
   - 売上が発生した時のみ手数料が発生

## 参考資料

- [Square Developer Documentation](https://developer.squareup.com/docs)
- [Square Python SDK](https://github.com/square/square-python-sdk)
- [Square Checkout API](https://developer.squareup.com/docs/checkout-api/overview)








