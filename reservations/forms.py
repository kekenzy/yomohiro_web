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
        fields = ['name', 'description', 'capacity', 'price_per_30min', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '場所名を入力してください'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': '場所の説明を入力してください'}),
            'capacity': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'price_per_30min': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'step': 1, 'placeholder': '30分あたりの金額を入力してください'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class ReservationForm(forms.ModelForm):
    """予約フォーム"""
    time_slots = forms.ModelMultipleChoiceField(
        queryset=TimeSlot.objects.filter(is_active=True),
        label='時間枠',
        required=True,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        help_text='複数の時間枠を選択できます'
    )
    
    class Meta:
        model = Reservation
        fields = ['location', 'date', 'customer_name', 'customer_email', 'customer_phone', 'notes']
        widgets = {
            'location': forms.Select(attrs={'class': 'form-select'}),
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'customer_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'お客様名を入力してください'}),
            'customer_email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'example@email.com'}),
            'customer_phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '例: 090-1234-5678'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'placeholder': '備考があれば入力してください'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        self.is_multi_date = kwargs.pop('is_multi_date', False)
        super().__init__(*args, **kwargs)
        # 有効な場所と時間枠のみを表示
        self.fields['location'].queryset = Location.objects.filter(is_active=True)
        self.fields['time_slots'].queryset = TimeSlot.objects.filter(is_active=True)
        
        # 複数日の予約の場合、場所・日付・時間枠を必須にしない
        if self.is_multi_date:
            self.fields['location'].required = False
            self.fields['date'].required = False
            self.fields['time_slots'].required = False
        
        # ログイン済みユーザーの場合、MemberProfileから情報を自動入力
        if self.user and self.user.is_authenticated:
            try:
                profile = MemberProfile.objects.get(user=self.user)
                self.fields['customer_name'].initial = profile.full_name
                self.fields['customer_email'].initial = self.user.email
                self.fields['customer_phone'].initial = profile.phone
            except MemberProfile.DoesNotExist:
                # MemberProfileが存在しない場合は、Userの情報を使用
                self.fields['customer_name'].initial = self.user.get_full_name() or self.user.username
                self.fields['customer_email'].initial = self.user.email

    def clean(self):
        cleaned_data = super().clean()
        
        # 複数日の予約の場合は、場所・日付・時間枠のバリデーションをスキップ
        if self.is_multi_date:
            # お客様情報のみをチェック
            if not cleaned_data.get('customer_name'):
                raise ValidationError('お客様名を入力してください。')
            if not cleaned_data.get('customer_email'):
                raise ValidationError('メールアドレスを入力してください。')
            if not cleaned_data.get('customer_phone'):
                raise ValidationError('電話番号を入力してください。')
            return cleaned_data
        
        # 単一日の予約の場合の既存のバリデーション
        location = cleaned_data.get('location')
        time_slots = cleaned_data.get('time_slots')
        reservation_date = cleaned_data.get('date')

        # 必須フィールドのチェック
        if not location:
            raise ValidationError('場所を選択してください。')
        if not reservation_date:
            raise ValidationError('予約日を選択してください。')
        if not cleaned_data.get('customer_name'):
            raise ValidationError('お客様名を入力してください。')
        if not cleaned_data.get('customer_email'):
            raise ValidationError('メールアドレスを入力してください。')
        if not cleaned_data.get('customer_phone'):
            raise ValidationError('電話番号を入力してください。')

        # 時間枠のチェック
        # 編集モード（self.instanceが存在する）の場合、時間枠は必須
        if self.instance and not time_slots:
            raise ValidationError('時間枠を選択してください。')
        
        # 新規予約の場合、ログイン済みユーザーで既存予約がある場合は、時間枠が選択されていなくても許可（既存予約の削除のみ）
        if not self.instance:
            has_existing_reservations = False
            if self.user and self.user.is_authenticated and location and reservation_date:
                existing_reservations = Reservation.objects.filter(
                    location=location,
                    date=reservation_date,
                    created_by=self.user,
                    status__in=['confirmed', 'pending']
                )
                has_existing_reservations = existing_reservations.exists()

            if not time_slots:
                if not has_existing_reservations:
                    raise ValidationError('時間枠を選択してください。')
                # 既存予約がある場合は、時間枠が選択されていなくても許可（既存予約の削除のみ）
                return cleaned_data

        # 時間枠が選択されている場合の処理
        if location and time_slots and reservation_date:
            # 各時間枠について重複チェック（自分の既存予約は除外）
            for time_slot in time_slots:
                existing_reservation = Reservation.objects.filter(
                    location=location,
                    time_slot=time_slot,
                    date=reservation_date,
                    status__in=['confirmed', 'pending']
                ).exclude(pk=self.instance.pk if self.instance else None)
                
                # ログイン済みユーザーの場合、自分の既存予約は除外
                if self.user and self.user.is_authenticated:
                    existing_reservation = existing_reservation.exclude(created_by=self.user)

                if existing_reservation.exists():
                    raise ValidationError(f'この場所と時間枠（{time_slot}）は既に予約されています。')

            # 過去の日付は予約できない
            if reservation_date < date.today():
                raise ValidationError('過去の日付は予約できません。')

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

class PlanForm(forms.ModelForm):
    """プランフォーム"""
    class Meta:
        model = Plan
        fields = ['name', 'description', 'price', 'is_default', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'プラン名を入力してください'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'プランの説明を入力してください'}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'step': 1, 'placeholder': '価格を入力してください'}),
            'is_default': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        is_default = cleaned_data.get('is_default')
        
        # デフォルトプランが複数存在しないようにする
        if is_default:
            existing_default = Plan.objects.filter(is_default=True).exclude(pk=self.instance.pk if self.instance else None)
            if existing_default.exists():
                raise forms.ValidationError('デフォルトプランは1つだけ設定できます。既存のデフォルトプランを解除してから設定してください。')
        
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
