from django import forms
from django.core.exceptions import ValidationError
from .models import Location, TimeSlot, Reservation
from datetime import date

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
