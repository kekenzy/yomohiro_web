from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import Location, TimeSlot, Reservation, Plan, MemberProfile
from datetime import date
import re

class LocationForm(forms.ModelForm):
    """場所フォーム"""
    class Meta:
        model = Location
        fields = ['name', 'description', 'capacity', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '場所名を入力してください'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': '場所の説明を入力してください'}),
            'capacity': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class ReservationForm(forms.ModelForm):
    """予約フォーム"""
    class Meta:
        model = Reservation
        fields = ['location', 'time_slot', 'date', 'customer_name', 'customer_email', 'customer_phone', 'notes']
        widgets = {
            'location': forms.Select(attrs={'class': 'form-select'}),
            'time_slot': forms.Select(attrs={'class': 'form-select'}),
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'customer_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'お客様名を入力してください'}),
            'customer_email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'example@email.com'}),
            'customer_phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '例: 090-1234-5678'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'placeholder': '備考があれば入力してください'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 有効な場所と時間枠のみを表示
        self.fields['location'].queryset = Location.objects.filter(is_active=True)
        self.fields['time_slot'].queryset = TimeSlot.objects.filter(is_active=True)

    def clean(self):
        cleaned_data = super().clean()
        location = cleaned_data.get('location')
        time_slot = cleaned_data.get('time_slot')
        reservation_date = cleaned_data.get('date')

        if location and time_slot and reservation_date:
            # 同じ場所、時間枠、日付の予約が既に存在するかチェック
            existing_reservation = Reservation.objects.filter(
                location=location,
                time_slot=time_slot,
                date=reservation_date,
                status__in=['confirmed', 'pending']
            ).exclude(pk=self.instance.pk if self.instance else None)

            if existing_reservation.exists():
                raise ValidationError('この場所と時間枠は既に予約されています。')

            # 過去の日付は予約できない
            if reservation_date < date.today():
                raise ValidationError('過去の日付は予約できません。')

        # 必須フィールドのチェック
        if not location:
            raise ValidationError('場所を選択してください。')
        if not time_slot:
            raise ValidationError('時間枠を選択してください。')
        if not reservation_date:
            raise ValidationError('予約日を選択してください。')
        if not cleaned_data.get('customer_name'):
            raise ValidationError('お客様名を入力してください。')
        if not cleaned_data.get('customer_email'):
            raise ValidationError('メールアドレスを入力してください。')
        if not cleaned_data.get('customer_phone'):
            raise ValidationError('電話番号を入力してください。')

        return cleaned_data

class TimeSlotForm(forms.ModelForm):
    """時間枠フォーム"""
    class Meta:
        model = TimeSlot
        fields = ['start_time', 'end_time', 'is_active']
        widgets = {
            'start_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'end_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')

        if start_time and end_time:
            if start_time >= end_time:
                raise forms.ValidationError('終了時間は開始時間より後にしてください。')
            
            # 重複チェック
            existing_slot = TimeSlot.objects.filter(
                start_time=start_time,
                end_time=end_time
            ).exclude(pk=self.instance.pk if self.instance else None)
            
            if existing_slot.exists():
                raise forms.ValidationError('同じ時間枠が既に存在します。')

        return cleaned_data

class ReservationSearchForm(forms.Form):
    """予約検索フォーム"""
    location = forms.ModelChoiceField(
        queryset=Location.objects.filter(is_active=True),
        required=False,
        empty_label="すべての場所",
        label="場所",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        label="日付"
    )
    time_slot = forms.ModelChoiceField(
        queryset=TimeSlot.objects.filter(is_active=True),
        required=False,
        empty_label="すべての時間枠",
        label="時間枠",
        widget=forms.Select(attrs={'class': 'form-select'})
    )


# 会員登録フォーム - Step1: 基本情報
class MemberRegistrationStep1Form(forms.Form):
    """会員登録 Step1: 基本情報"""
    full_name = forms.CharField(
        max_length=100,
        label='氏名',
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '氏名を入力してください'
        })
    )
    gender = forms.ChoiceField(
        choices=MemberProfile.GENDER_CHOICES,
        label='性別',
        required=True,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    birth_date = forms.DateField(
        label='生年月日',
        required=True,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        })
    )
    email = forms.EmailField(
        label='メールアドレス',
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'example@email.com'
        })
    )
    password = forms.CharField(
        label='パスワード',
        required=True,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': '英数字8文字以上'
        }),
        min_length=8
    )
    password_confirm = forms.CharField(
        label='パスワード（確認）',
        required=True,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'パスワードを再入力してください'
        })
    )
    phone = forms.CharField(
        max_length=15,
        label='電話番号',
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '例: 090-1234-5678'
        })
    )
    postal_code = forms.CharField(
        max_length=10,
        label='郵便番号',
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '例: 123-4567',
            'id': 'postal_code'
        })
    )
    address = forms.CharField(
        label='住所',
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': '住所を入力してください',
            'id': 'address'
        })
    )

    def clean_password(self):
        password = self.cleaned_data.get('password')
        if password:
            # 英数字8文字以上チェック
            if len(password) < 8:
                raise ValidationError('パスワードは8文字以上で入力してください。')
            if not re.match(r'^[a-zA-Z0-9]+$', password):
                raise ValidationError('パスワードは英数字のみ使用できます。')
        return password

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        password_confirm = cleaned_data.get('password_confirm')

        if password and password_confirm:
            if password != password_confirm:
                raise ValidationError('パスワードが一致しません。')

        return cleaned_data


# 会員登録フォーム - Step2: プラン選択
class MemberRegistrationStep2Form(forms.Form):
    """会員登録 Step2: プラン選択"""
    plan = forms.ModelChoiceField(
        queryset=Plan.objects.filter(is_active=True),
        label='プラン',
        required=True,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
        empty_label=None
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # デフォルトプランを設定
        default_plan = Plan.objects.filter(is_default=True, is_active=True).first()
        if default_plan:
            self.fields['plan'].initial = default_plan


# 会員登録フォーム - Step3: 顔写真登録
class MemberRegistrationStep3Form(forms.Form):
    """会員登録 Step3: 顔写真登録"""
    photo = forms.ImageField(
        label='顔写真',
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': 'image/*',
            'id': 'photo_upload'
        })
    )


# 会員登録フォーム - Step4: クレジットカード情報
class MemberRegistrationStep4Form(forms.Form):
    """会員登録 Step4: クレジットカード情報"""
    card_number = forms.CharField(
        max_length=19,
        label='クレジットカード番号',
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '1234-5678-9012-3456',
            'maxlength': '19',
            'id': 'card_number'
        })
    )
    card_expiry_month = forms.IntegerField(
        label='有効期限（月）',
        required=True,
        min_value=1,
        max_value=12,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'min': '1',
            'max': '12',
            'id': 'card_expiry_month'
        })
    )
    card_expiry_year = forms.IntegerField(
        label='有効期限（年）',
        required=True,
        min_value=date.today().year,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'min': str(date.today().year),
            'id': 'card_expiry_year'
        })
    )
    card_cvc = forms.CharField(
        max_length=4,
        label='CVC',
        required=True,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': '123',
            'maxlength': '4',
            'id': 'card_cvc'
        }),
        min_length=3
    )

    def clean_card_number(self):
        card_number = self.cleaned_data.get('card_number')
        if card_number:
            # ハイフンを除去して数字のみチェック
            card_number_clean = card_number.replace('-', '').replace(' ', '')
            if not card_number_clean.isdigit():
                raise ValidationError('カード番号は数字のみで入力してください。')
            if len(card_number_clean) < 13 or len(card_number_clean) > 19:
                raise ValidationError('カード番号の桁数が正しくありません。')
        return card_number

    def clean_card_cvc(self):
        card_cvc = self.cleaned_data.get('card_cvc')
        if card_cvc:
            if not card_cvc.isdigit():
                raise ValidationError('CVCは数字のみで入力してください。')
            if len(card_cvc) < 3 or len(card_cvc) > 4:
                raise ValidationError('CVCは3桁または4桁で入力してください。')
        return card_cvc
