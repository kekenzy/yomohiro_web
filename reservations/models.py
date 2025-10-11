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
