from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django.utils import timezone

class Location(models.Model):
    """場所"""
    name = models.CharField(max_length=100, verbose_name='場所名')
    description = models.TextField(blank=True, verbose_name='説明')
    capacity = models.PositiveIntegerField(verbose_name='定員')
    is_active = models.BooleanField(default=True, verbose_name='有効')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = '場所'
        verbose_name_plural = '場所'
        ordering = ['name']

    def __str__(self):
        return self.name

class TimeSlot(models.Model):
    """時間枠"""
    start_time = models.TimeField(verbose_name='開始時間')
    end_time = models.TimeField(verbose_name='終了時間')
    is_active = models.BooleanField(default=True, verbose_name='有効')
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = '時間枠'
        verbose_name_plural = '時間枠'
        ordering = ['start_time']

    def __str__(self):
        return f"{self.start_time} - {self.end_time}"

class Reservation(models.Model):
    """予約"""
    STATUS_CHOICES = [
        ('confirmed', '確認済み'),
        ('pending', '保留中'),
        ('cancelled', 'キャンセル'),
    ]

    location = models.ForeignKey(Location, on_delete=models.CASCADE, verbose_name='場所')
    time_slot = models.ForeignKey(TimeSlot, on_delete=models.CASCADE, verbose_name='時間枠')
    date = models.DateField(verbose_name='予約日')
    
    # お客様情報
    customer_name = models.CharField(max_length=100, verbose_name='お客様名')
    customer_email = models.EmailField(verbose_name='メールアドレス')
    customer_phone = models.CharField(
        max_length=15, 
        verbose_name='電話番号',
        validators=[
            RegexValidator(
                regex=r'^[\d\-\(\)\s]+$',
                message='電話番号は数字、ハイフン、括弧、スペースのみ使用可能です'
            )
        ]
    )
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='ステータス')
    notes = models.TextField(blank=True, verbose_name='備考')
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='作成者')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = '予約'
        verbose_name_plural = '予約'
        unique_together = ['location', 'time_slot', 'date']
        ordering = ['-date', 'time_slot__start_time']

    def __str__(self):
        return f"{self.customer_name} - {self.location.name} - {self.date} {self.time_slot}"

    @property
    def is_available(self):
        """この予約が利用可能かどうか"""
        return self.status == 'confirmed'


class Plan(models.Model):
    """会員プラン"""
    name = models.CharField(max_length=100, verbose_name='プラン名')
    description = models.TextField(blank=True, verbose_name='説明')
    price = models.DecimalField(max_digits=10, decimal_places=0, default=0, verbose_name='価格')
    is_default = models.BooleanField(default=False, verbose_name='デフォルトプラン')
    is_active = models.BooleanField(default=True, verbose_name='有効')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = '会員プラン'
        verbose_name_plural = '会員プラン'
        ordering = ['price']

    def __str__(self):
        return self.name


def member_photo_upload_path(instance, filename):
    """会員の顔写真のアップロードパス"""
    return f'member_photos/{instance.user.id}/{filename}'


class MemberProfile(models.Model):
    """会員プロフィール"""
    GENDER_CHOICES = [
        ('male', '男性'),
        ('female', '女性'),
        ('other', 'その他'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, verbose_name='ユーザー')
    
    # 基本情報
    full_name = models.CharField(max_length=100, verbose_name='氏名')
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, verbose_name='性別')
    birth_date = models.DateField(verbose_name='生年月日')
    phone = models.CharField(
        max_length=15,
        verbose_name='電話番号',
        validators=[
            RegexValidator(
                regex=r'^[\d\-\(\)\s]+$',
                message='電話番号は数字、ハイフン、括弧、スペースのみ使用可能です'
            )
        ]
    )
    postal_code = models.CharField(max_length=10, blank=True, verbose_name='郵便番号')
    address = models.TextField(blank=True, verbose_name='住所')
    
    # プラン情報
    plan = models.ForeignKey(Plan, on_delete=models.SET_NULL, null=True, verbose_name='プラン')
    
    # 顔写真
    photo = models.ImageField(upload_to=member_photo_upload_path, blank=True, null=True, verbose_name='顔写真')
    
    # クレジットカード情報（暗号化して保存すべきですが、簡易実装として）
    card_number_encrypted = models.CharField(max_length=255, blank=True, verbose_name='カード番号（暗号化）')
    card_expiry_month = models.IntegerField(null=True, blank=True, verbose_name='カード有効期限（月）')
    card_expiry_year = models.IntegerField(null=True, blank=True, verbose_name='カード有効期限（年）')
    card_cvc_encrypted = models.CharField(max_length=255, blank=True, verbose_name='CVC（暗号化）')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = '会員プロフィール'
        verbose_name_plural = '会員プロフィール'

    def __str__(self):
        return f"{self.full_name} ({self.user.username})"


class PaymentTransaction(models.Model):
    """Square決済トランザクション"""
    STATUS_CHOICES = [
        ('pending', '保留中'),
        ('completed', '完了'),
        ('failed', '失敗'),
        ('cancelled', 'キャンセル'),
    ]

    reservation = models.ForeignKey(Reservation, on_delete=models.CASCADE, null=True, blank=True, verbose_name='予約')
    member_profile = models.ForeignKey(MemberProfile, on_delete=models.CASCADE, null=True, blank=True, verbose_name='会員')
    
    # Square決済情報
    square_payment_id = models.CharField(max_length=255, unique=True, null=True, blank=True, verbose_name='Square決済ID')
    square_order_id = models.CharField(max_length=255, null=True, blank=True, verbose_name='Square注文ID')
    payment_link_id = models.CharField(max_length=255, null=True, blank=True, verbose_name='決済リンクID')
    payment_link_url = models.URLField(null=True, blank=True, verbose_name='決済リンクURL')
    
    # 決済情報
    amount = models.DecimalField(max_digits=10, decimal_places=0, verbose_name='金額')
    currency = models.CharField(max_length=3, default='JPY', verbose_name='通貨')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='ステータス')
    
    # メタデータ
    metadata = models.JSONField(default=dict, blank=True, verbose_name='メタデータ')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = '決済トランザクション'
        verbose_name_plural = '決済トランザクション'
        ordering = ['-created_at']

    def __str__(self):
        return f"決済 #{self.id} - {self.amount}円 - {self.get_status_display()}"
