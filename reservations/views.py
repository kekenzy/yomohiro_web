from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.contrib.auth import authenticate, login
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.core.files.base import ContentFile
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from datetime import date, datetime, timedelta
import json
import base64
import hmac
import hashlib
from .models import Location, TimeSlot, Reservation, Plan, MemberProfile
from .forms import (
    ReservationForm, ReservationSearchForm, LocationForm, TimeSlotForm, PlanForm,
    MemberRegistrationStep1Form, MemberRegistrationStep2Form,
    MemberRegistrationStep3Form, MemberRegistrationStep4Form
)
from .decorators import superuser_required

def custom_login(request):
    """カスタムログインビュー"""
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, 'ログインしました。')
            return redirect('reservations:index')
        else:
            messages.error(request, 'ユーザー名またはパスワードが正しくありません。')
    
    return render(request, 'reservations/login.html')

def index(request):
    """予約システムのトップページ"""
    locations = Location.objects.filter(is_active=True)
    context = {
        'locations': locations
    }
    
    # ログイン時は管理者向けの統計データを追加
    if request.user.is_authenticated:
        today = date.today()
        month_start = today.replace(day=1)
        
        # 今日の予約数
        today_reservations = Reservation.objects.filter(date=today).count()
        
        # 今月の予約数
        month_reservations = Reservation.objects.filter(date__gte=month_start).count()
        
        # 利用可能な場所数
        location_count = locations.count()
        
        # 最近の予約数（過去7日間）
        recent_date = today - timedelta(days=7)
        recent_count = Reservation.objects.filter(date__gte=recent_date).count()
        
        # ログインユーザーの予約一覧を取得（未来の予約のみ、確認済み・保留中のみ）
        user_reservations = Reservation.objects.filter(
            Q(created_by=request.user) | Q(customer_email=request.user.email),
            date__gte=today,
            status__in=['confirmed', 'pending']
        ).select_related('location', 'time_slot').order_by('date', 'time_slot__start_time')
        
        # 連続予約をまとめる
        grouped_user_reservations = group_consecutive_reservations(list(user_reservations))
        
        context.update({
            'today_reservations': today_reservations,
            'month_reservations': month_reservations,
            'location_count': location_count,
            'recent_count': recent_count,
            'user_reservations': grouped_user_reservations,
        })
    
    return render(request, 'reservations/index.html', context)

@login_required
def my_reservations(request):
    """マイ予約一覧"""
    today = date.today()
    
    # ログインユーザーの予約一覧を取得（未来の予約のみ、確認済み・保留中のみ）
    user_reservations = Reservation.objects.filter(
        Q(created_by=request.user) | Q(customer_email=request.user.email),
        date__gte=today,
        status__in=['confirmed', 'pending']
    ).select_related('location', 'time_slot').order_by('date', 'time_slot__start_time')
    
    # 連続予約をまとめる
    grouped_user_reservations = group_consecutive_reservations(list(user_reservations))
    
    # ページネーション
    paginator = Paginator(grouped_user_reservations, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'reservations/my_reservations.html', {
        'page_obj': page_obj,
        'user_reservations': grouped_user_reservations,
    })

def group_consecutive_reservations(reservations):
    """連続した予約をまとめる"""
    if not reservations:
        return []
    
    # 日付、場所、ユーザー（email）でグループ化し、時間順にソート
    grouped = {}
    for reservation in reservations:
        key = (reservation.date, reservation.location.id, reservation.customer_email)
        if key not in grouped:
            grouped[key] = []
        grouped[key].append(reservation)
    
    # 各グループ内で時間順にソート
    for key in grouped:
        grouped[key].sort(key=lambda r: r.time_slot.start_time)
    
    # 連続した予約をまとめる
    grouped_reservations = []
    for key, group in grouped.items():
        if len(group) == 1:
            grouped_reservations.append({
                'reservations': group,
                'start_time': group[0].time_slot.start_time,
                'end_time': group[0].time_slot.end_time,
                'customer_name': group[0].customer_name,
                'customer_email': group[0].customer_email,
                'location': group[0].location,
                'date': group[0].date,
                'status': group[0].status,
                'notes': group[0].notes or '',
                'ids': [r.id for r in group]
            })
        else:
            # 連続しているかチェック
            consecutive_groups = []
            current_group = [group[0]]
            
            for i in range(1, len(group)):
                prev_end = current_group[-1].time_slot.end_time
                curr_start = group[i].time_slot.start_time
                
                # 前の終了時間と現在の開始時間が同じか、1分以内なら連続
                if prev_end == curr_start or (datetime.combine(date.today(), curr_start) - datetime.combine(date.today(), prev_end)).total_seconds() <= 60:
                    current_group.append(group[i])
                else:
                    consecutive_groups.append(current_group)
                    current_group = [group[i]]
            
            consecutive_groups.append(current_group)
            
            # 各連続グループをまとめる
            for consecutive_group in consecutive_groups:
                grouped_reservations.append({
                    'reservations': consecutive_group,
                    'start_time': consecutive_group[0].time_slot.start_time,
                    'end_time': consecutive_group[-1].time_slot.end_time,
                    'customer_name': consecutive_group[0].customer_name,
                    'customer_email': consecutive_group[0].customer_email,
                    'location': consecutive_group[0].location,
                    'date': consecutive_group[0].date,
                    'status': consecutive_group[0].status,
                    'notes': consecutive_group[0].notes or '',
                    'ids': [r.id for r in consecutive_group]
                })
    
    return grouped_reservations

def get_calendar_events(request):
    """Googleカレンダー用の予約データを取得"""
    start_date = request.GET.get('start')
    end_date = request.GET.get('end')
    
    try:
        # 日付の解析
        if start_date:
            start_date = datetime.strptime(start_date[:10], '%Y-%m-%d').date()
        else:
            start_date = date.today()
        
        if end_date:
            end_date = datetime.strptime(end_date[:10], '%Y-%m-%d').date()
        else:
            end_date = start_date + timedelta(days=30)
        
        # 予約データを取得
        # 一般ユーザーの場合は自分の予約のみ、スーパーユーザーの場合は全ての予約
        if request.user.is_authenticated:
            if request.user.is_superuser:
                # スーパーユーザーは全ての予約を表示
                reservations = Reservation.objects.filter(
                    date__gte=start_date,
                    date__lte=end_date
                ).select_related('location', 'time_slot').order_by('date', 'location', 'customer_email', 'time_slot__start_time')
            else:
                # 一般ユーザーは自分の予約のみ表示
                reservations = Reservation.objects.filter(
                    date__gte=start_date,
                    date__lte=end_date
                ).filter(
                    Q(created_by=request.user) | Q(customer_email=request.user.email)
                ).select_related('location', 'time_slot').order_by('date', 'location', 'customer_email', 'time_slot__start_time')
        else:
            # 未ログインユーザーは予約を表示しない
            reservations = Reservation.objects.none()
        
        # 連続予約をまとめる
        grouped_reservations = group_consecutive_reservations(list(reservations))
        
        events = []
        for group in grouped_reservations:
            # 予約の開始時間と終了時間を設定
            start_time = datetime.combine(group['date'], group['start_time'])
            end_time = datetime.combine(group['date'], group['end_time'])
            
            # イベントの色を設定（場所によって異なる色を使用）
            colors = ['#ffc107', '#e0a800', '#ff8c00', '#ff6b35', '#f7931e']
            color_index = group['location'].id % len(colors)
            
            # タイトル（複数の予約がある場合は時間範囲を表示）
            time_str = f"{group['start_time'].strftime('%H:%M')}-{group['end_time'].strftime('%H:%M')}"
            if len(group['reservations']) > 1:
                time_str += f" ({len(group['reservations'])}枠)"
            
            event = {
                'id': f"group_{group['ids'][0]}",  # 最初の予約IDを使用
                'title': f"{group['customer_name']} - {group['location'].name} - {time_str}",
                'start': start_time.isoformat(),
                'end': end_time.isoformat(),
                'backgroundColor': colors[color_index],
                'borderColor': colors[color_index],
                'textColor': '#000',
                'extendedProps': {
                    'location': group['location'].name,
                    'customer_name': group['customer_name'],
                    'customer_email': group['customer_email'],
                    'customer_phone': group['reservations'][0].customer_phone,
                    'status': group['status'],
                    'notes': group['notes'],
                    'reservation_ids': group['ids'],  # 予約IDのリスト
                    'count': len(group['reservations'])
                }
            }
            events.append(event)
        
        return JsonResponse(events, safe=False)
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

def location_list(request):
    """場所一覧"""
    locations = Location.objects.filter(is_active=True)
    return render(request, 'reservations/location_list.html', {
        'locations': locations
    })

@login_required
@superuser_required
def reservation_list(request):
    """予約一覧（スーパーユーザーのみ）"""
    form = ReservationSearchForm(request.GET)
    reservations = Reservation.objects.all()
    
    if form.is_valid():
        location = form.cleaned_data.get('location')
        reservation_date = form.cleaned_data.get('date')
        time_slot = form.cleaned_data.get('time_slot')
        
        if location:
            reservations = reservations.filter(location=location)
        if reservation_date:
            reservations = reservations.filter(date=reservation_date)
        if time_slot:
            reservations = reservations.filter(time_slot=time_slot)
    
    # 連続予約をまとめる
    reservations_list = list(reservations.order_by('date', 'location', 'customer_email', 'time_slot__start_time'))
    grouped_reservations = group_consecutive_reservations(reservations_list)
    
    # ページネーション
    paginator = Paginator(grouped_reservations, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'reservations/reservation_list.html', {
        'page_obj': page_obj,
        'form': form
    })

def reservation_create(request):
    """予約作成"""
    if request.method == 'POST':
        # セッションから複数日の予約データを取得
        session_key = 'reservation_data'
        existing_data = request.session.get(session_key, {})
        is_multi_date = existing_data.get('is_multi_date', False)
        
        form = ReservationForm(request.POST, user=request.user, is_multi_date=is_multi_date)
        if form.is_valid():
            # セッションに予約情報を保存して確認画面へ
            session_key = 'reservation_data'
            
            # セッションから既存の予約データを取得（複数日の予約データがある場合）
            existing_data = request.session.get(session_key, {})
            is_multi_date = existing_data.get('is_multi_date', False)
            multi_date_slots = existing_data.get('multi_date_slots', {})
            
            if is_multi_date and multi_date_slots:
                # 複数日の予約の場合：お客様情報のみを更新
                cleaned_data = {
                    'location': existing_data.get('location'),
                    'multi_date_slots': multi_date_slots,
                    'is_multi_date': True,
                    'customer_name': form.cleaned_data.get('customer_name'),
                    'customer_email': form.cleaned_data.get('customer_email'),
                    'customer_phone': form.cleaned_data.get('customer_phone'),
                    'notes': form.cleaned_data.get('notes', ''),
                }
            else:
                # 単一日の予約の場合：既存の処理
                cleaned_data = form.cleaned_data.copy()
                # locationをIDに変換
                if 'location' in cleaned_data and cleaned_data['location']:
                    cleaned_data['location'] = cleaned_data['location'].id
                # time_slotsをIDのリストに変換（選択されていない場合は空リスト）
                if 'time_slots' in cleaned_data and cleaned_data['time_slots']:
                    cleaned_data['time_slot_ids'] = [ts.id for ts in cleaned_data['time_slots']]
                else:
                    cleaned_data['time_slot_ids'] = []
                if 'time_slots' in cleaned_data:
                    del cleaned_data['time_slots']
                # dateを文字列に変換
                if 'date' in cleaned_data and cleaned_data['date']:
                    cleaned_data['date'] = cleaned_data['date'].isoformat()
                
                # ログイン済みユーザーの既存予約を取得して、選択解除された予約を特定
                if request.user.is_authenticated:
                    location_id = cleaned_data.get('location')
                    reservation_date_str = cleaned_data.get('date')
                    reservation_date = datetime.fromisoformat(reservation_date_str).date() if reservation_date_str else None
                    selected_time_slot_ids = cleaned_data.get('time_slot_ids', [])
                    
                    if location_id and reservation_date:
                        # その日の自分の既存予約を取得
                        existing_reservations = Reservation.objects.filter(
                            location_id=location_id,
                            date=reservation_date,
                            created_by=request.user,
                            status__in=['confirmed', 'pending']
                        )
                        
                        # 選択解除された予約IDを保存（確定時に削除するため）
                        deselected_reservation_ids = []
                        for reservation in existing_reservations:
                            if reservation.time_slot.id not in selected_time_slot_ids:
                                deselected_reservation_ids.append(reservation.id)
                        
                        cleaned_data['deselected_reservation_ids'] = deselected_reservation_ids
            
            request.session[session_key] = cleaned_data
            return redirect('reservations:reservation_confirm')
        else:
            print(f"Debug: Form errors - {form.errors}")
            messages.error(request, 'フォームにエラーがあります。以下を確認してください。')
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
            
            # エラー時も複数日の予約データを保持してフォームを再表示
            # セッションから複数日の予約データを取得
            session_key = 'reservation_data'
            existing_data = request.session.get(session_key, {})
            is_multi_date = existing_data.get('is_multi_date', False)
            multi_date_slots = existing_data.get('multi_date_slots', {})
            multi_date_details = None
            
            if is_multi_date and multi_date_slots:
                multi_date_details = []
                for date_str, time_slot_ids in multi_date_slots.items():
                    reservation_date = datetime.fromisoformat(date_str).date()
                    time_slots = TimeSlot.objects.filter(id__in=time_slot_ids)
                    multi_date_details.append({
                        'date': reservation_date,
                        'date_str': date_str,
                        'time_slots': time_slots,
                    })
            
            return render(request, 'reservations/reservation_form.html', {
                'form': form,
                'title': '新規予約',
                'initial_time_slot_ids': [],
                'is_multi_date': is_multi_date,
                'multi_date_slots': multi_date_slots,
                'multi_date_details': multi_date_details,
            })
    else:
        # GETリクエストの場合：URLパラメータからlocationとdateを取得
        location_id = request.GET.get('location')
        date_str = request.GET.get('date')
        time_slots_str = request.GET.get('time_slots')  # 週間カレンダーから選択された時間枠（旧形式）
        multi_date_slots_str = request.GET.get('multi_date_slots')  # 複数日の予約データ（新形式）
        initial_data = {}
        initial_time_slot_ids = []
        multi_date_slots_data = None
        
        if location_id:
            try:
                location = Location.objects.get(id=location_id, is_active=True)
                initial_data['location'] = location
            except Location.DoesNotExist:
                messages.warning(request, f'指定された場所（ID: {location_id}）が見つかりません。')
            except ValueError as e:
                messages.warning(request, '無効な場所IDが指定されました。')
            except Exception as e:
                messages.warning(request, f'場所の読み込み中にエラーが発生しました: {str(e)}')
        
        # 複数日の予約データを処理（新形式）
        if multi_date_slots_str:
            try:
                import json
                from urllib.parse import unquote
                # URLエンコードされているのでデコード
                decoded_str = unquote(multi_date_slots_str)
                multi_date_slots_data = json.loads(decoded_str)
                # データの形式を確認（辞書形式で、キーが日付文字列、値が時間枠IDのリスト）
                if not isinstance(multi_date_slots_data, dict):
                    raise ValueError('複数日予約データは辞書形式である必要があります。')
                # 最初の日付を初期値として設定（フォーム表示用）
                if multi_date_slots_data:
                    first_date = sorted(multi_date_slots_data.keys())[0]
                    reservation_date = datetime.fromisoformat(first_date).date()
                    initial_data['date'] = reservation_date
                    # 時間枠IDを整数に変換
                    initial_time_slot_ids = [int(id) for id in multi_date_slots_data[first_date] if str(id).isdigit()]
            except (ValueError, TypeError, json.JSONDecodeError) as e:
                import traceback
                print(f"Error parsing multi_date_slots: {e}")
                print(f"Raw data: {multi_date_slots_str}")
                traceback.print_exc()
                messages.warning(request, f'無効な複数日予約データが指定されました: {str(e)}')
                multi_date_slots_data = None
        elif date_str:
            # 旧形式：単一日の予約
            try:
                # YYYY-MM-DD形式の文字列をdateオブジェクトに変換
                reservation_date = datetime.fromisoformat(date_str).date()
                initial_data['date'] = reservation_date
            except (ValueError, TypeError) as e:
                messages.warning(request, '無効な日付が指定されました。')
            except Exception as e:
                messages.warning(request, f'日付の読み込み中にエラーが発生しました: {str(e)}')
        
        # 週間カレンダーから選択された時間枠を取得（旧形式）
        if time_slots_str and not multi_date_slots_str:
            try:
                time_slot_ids = [int(id.strip()) for id in time_slots_str.split(',') if id.strip()]
                initial_time_slot_ids = time_slot_ids
            except (ValueError, TypeError) as e:
                messages.warning(request, '無効な時間枠IDが指定されました。')
        
        # 複数日の予約かどうかをチェック
        session_key = 'reservation_data'
        existing_data = request.session.get(session_key, {})
        is_multi_date = existing_data.get('is_multi_date', False) or (multi_date_slots_data is not None)
        
        form = ReservationForm(initial=initial_data, user=request.user, is_multi_date=is_multi_date)
        
        # 複数日の予約データがある場合は、セッションに保存して予約フォームを表示
        # （お客様情報を入力してもらうため）
        if multi_date_slots_data:
            # セッションに複数日の予約データを保存
            session_key = 'reservation_data'
            cleaned_data = {
                'location': int(location_id),
                'multi_date_slots': multi_date_slots_data,  # {'2026-01-21': [1, 2, 3], '2026-01-22': [4, 5]}
                'is_multi_date': True,
            }
            request.session[session_key] = cleaned_data
            # 予約フォームを表示（お客様情報を入力してもらう）
            # 時間枠は既に選択済みなので、フォームで非表示にする
    
    # セッションから複数日の予約データを取得
    session_key = 'reservation_data'
    existing_data = request.session.get(session_key, {})
    is_multi_date = existing_data.get('is_multi_date', False)
    multi_date_slots = existing_data.get('multi_date_slots', {})
    multi_date_details = None
    
    # 複数日の予約データがある場合、時間枠情報を取得
    if is_multi_date and multi_date_slots:
        multi_date_details = []
        for date_str, time_slot_ids in multi_date_slots.items():
            reservation_date = datetime.fromisoformat(date_str).date()
            time_slots = TimeSlot.objects.filter(id__in=time_slot_ids)
            multi_date_details.append({
                'date': reservation_date,
                'date_str': date_str,
                'time_slots': time_slots,
            })
    
    return render(request, 'reservations/reservation_form.html', {
        'form': form,
        'title': '新規予約',
        'initial_time_slot_ids': initial_time_slot_ids,
        'is_multi_date': is_multi_date,
        'multi_date_slots': multi_date_slots,
        'multi_date_details': multi_date_details,
    })

def reservation_confirm(request):
    """予約確認画面"""
    session_key = 'reservation_data'
    reservation_data = request.session.get(session_key)
    
    if not reservation_data:
        messages.warning(request, '予約情報が見つかりません。最初から入力してください。')
        return redirect('reservations:reservation_create')
    
    # 複数日の予約かどうかをチェック
    is_multi_date = reservation_data.get('is_multi_date', False)
    multi_date_slots = reservation_data.get('multi_date_slots', {})
    
    if is_multi_date and multi_date_slots:
        # 複数日の予約処理
        location_id = reservation_data.get('location')
        
        try:
            location = Location.objects.get(id=location_id)
        except Location.DoesNotExist:
            messages.error(request, '予約情報の読み込み中にエラーが発生しました。')
            return redirect('reservations:reservation_create')
        
        price_per_30min = location.price_per_30min or 0
        total_amount = 0
        multi_date_details = []
        
        # 各日付ごとに予約情報を整理
        for date_str, time_slot_ids in sorted(multi_date_slots.items()):
            reservation_date = datetime.fromisoformat(date_str).date()
            time_slots = TimeSlot.objects.filter(id__in=time_slot_ids)
            
            date_total = 0
            date_slot_details = []
            
            for time_slot in time_slots:
                # 開始時間と終了時間の差を計算
                start_datetime = datetime.combine(date.today(), time_slot.start_time)
                end_datetime = datetime.combine(date.today(), time_slot.end_time)
                if end_datetime < start_datetime:
                    end_datetime += timedelta(days=1)
                
                duration = end_datetime - start_datetime
                total_minutes = duration.total_seconds() / 60
                units_30min = int((total_minutes + 29) // 30)
                slot_amount = units_30min * price_per_30min
                
                date_slot_details.append({
                    'time_slot': time_slot,
                    'duration_minutes': int(total_minutes),
                    'units_30min': units_30min,
                    'amount': slot_amount
                })
                date_total += slot_amount
            
            multi_date_details.append({
                'date': reservation_date,
                'time_slots': time_slots,
                'time_slot_details': date_slot_details,
                'date_total': date_total
            })
            total_amount += date_total
        
        context = {
            'location': location,
            'multi_date_details': multi_date_details,
            'customer_name': reservation_data.get('customer_name'),
            'customer_email': reservation_data.get('customer_email'),
            'customer_phone': reservation_data.get('customer_phone'),
            'notes': reservation_data.get('notes', ''),
            'price_per_30min': price_per_30min,
            'total_amount': total_amount,
            'is_multi_date': True,
            'is_edit': False,
        }
        
        return render(request, 'reservations/reservation_confirm_multi.html', context)
    
    # 単一日の予約処理（既存の処理）
    location_id = reservation_data.get('location')
    time_slot_ids = reservation_data.get('time_slot_ids', [])
    reservation_date_str = reservation_data.get('date')
    
    try:
        location = Location.objects.get(id=location_id)
        time_slots = TimeSlot.objects.filter(id__in=time_slot_ids) if time_slot_ids else []
        reservation_date = datetime.fromisoformat(reservation_date_str).date() if reservation_date_str else None
    except (Location.DoesNotExist, ValueError, TypeError) as e:
        messages.error(request, '予約情報の読み込み中にエラーが発生しました。')
        return redirect('reservations:reservation_create')
    
    # 時間枠が選択されていない場合（新規予約の場合）
    if not time_slots:
        messages.warning(request, '時間枠を選択してください。')
        return redirect('reservations:reservation_create')
    
    # 金額を計算（30分単位）
    total_amount = 0
    time_slot_details = []
    price_per_30min = location.price_per_30min or 0
    
    for time_slot in time_slots:
        # 開始時間と終了時間の差を計算
        start_datetime = datetime.combine(date.today(), time_slot.start_time)
        end_datetime = datetime.combine(date.today(), time_slot.end_time)
        if end_datetime < start_datetime:
            # 日をまたぐ場合（例：23:00-01:00）
            end_datetime += timedelta(days=1)
        
        duration = end_datetime - start_datetime
        total_minutes = duration.total_seconds() / 60
        # 30分単位に切り上げ
        units_30min = int((total_minutes + 29) // 30)  # 切り上げ
        slot_amount = units_30min * price_per_30min
        
        time_slot_details.append({
            'time_slot': time_slot,
            'duration_minutes': int(total_minutes),
            'units_30min': units_30min,
            'amount': slot_amount
        })
        total_amount += slot_amount
    
    # 編集モードかどうかをチェック
    is_edit = reservation_data.get('is_edit', False)
    edit_reservation_ids = reservation_data.get('edit_reservation_ids', [])
    
    context = {
        'location': location,
        'time_slots': time_slots,
        'time_slot_details': time_slot_details,
        'date': reservation_date,
        'customer_name': reservation_data.get('customer_name'),
        'customer_email': reservation_data.get('customer_email'),
        'customer_phone': reservation_data.get('customer_phone'),
        'notes': reservation_data.get('notes', ''),
        'price_per_30min': price_per_30min,
        'total_amount': total_amount,
        'is_edit': is_edit,
        'edit_reservation_ids': edit_reservation_ids,
        'is_multi_date': False,
    }
    
    return render(request, 'reservations/reservation_confirm.html', context)

def reservation_confirm_submit(request):
    """予約確定処理"""
    session_key = 'reservation_data'
    reservation_data = request.session.get(session_key)
    
    if not reservation_data:
        messages.warning(request, '予約情報が見つかりません。最初から入力してください。')
        return redirect('reservations:reservation_create')
    
    if request.method != 'POST':
        return redirect('reservations:reservation_confirm')
    
    try:
        # 複数日の予約かどうかをチェック
        is_multi_date = reservation_data.get('is_multi_date', False)
        multi_date_slots = reservation_data.get('multi_date_slots', {})
        
        if is_multi_date and multi_date_slots:
            # 複数日の予約処理
            location_id = reservation_data.get('location')
            location = Location.objects.get(id=location_id)
            price_per_30min = location.price_per_30min or 0
            total_amount = 0
            all_created_reservations = []
            
            # 各日付ごとに予約を作成
            for date_str, time_slot_ids in multi_date_slots.items():
                reservation_date = datetime.fromisoformat(date_str).date()
                time_slots = TimeSlot.objects.filter(id__in=time_slot_ids)
                
                # 日付ごとの金額を計算
                for time_slot in time_slots:
                    start_datetime = datetime.combine(date.today(), time_slot.start_time)
                    end_datetime = datetime.combine(date.today(), time_slot.end_time)
                    if end_datetime < start_datetime:
                        end_datetime += timedelta(days=1)
                    
                    duration = end_datetime - start_datetime
                    total_minutes = duration.total_seconds() / 60
                    units_30min = int((total_minutes + 29) // 30)
                    slot_amount = units_30min * price_per_30min
                    total_amount += slot_amount
                
                # 各時間枠ごとに予約を作成
                for time_slot in time_slots:
                    # 重複チェック
                    duplicate = Reservation.objects.filter(
                        location=location,
                        time_slot=time_slot,
                        date=reservation_date,
                        status__in=['confirmed', 'pending']
                    )
                    
                    if duplicate.exists():
                        continue
                    
                    reservation = Reservation.objects.create(
                        location=location,
                        time_slot=time_slot,
                        date=reservation_date,
                        customer_name=reservation_data.get('customer_name'),
                        customer_email=reservation_data.get('customer_email'),
                        customer_phone=reservation_data.get('customer_phone'),
                        notes=reservation_data.get('notes', ''),
                        status='pending' if total_amount > 0 and SQUARE_AVAILABLE else 'confirmed',
                        created_by=request.user if request.user.is_authenticated else None
                    )
                    all_created_reservations.append(reservation)
            
            # 金額が0より大きい場合はSquare決済リンクを作成
            if total_amount > 0 and SQUARE_AVAILABLE:
                # 決済リンクを作成
                order_id = f"multi_{datetime.now().timestamp()}"
                description = f"{location.name} - 複数日予約"
                payment_result = create_payment_link(request, total_amount, order_id, description)
                
                if payment_result.get('success'):
                    payment_url = payment_result.get('payment_url')
                    # セッションに決済情報を保存
                    request.session['payment_order_id'] = order_id
                    request.session['payment_reservation_ids'] = [r.id for r in all_created_reservations]
                    
                    # セッションの予約データをクリア
                    del request.session[session_key]
                    
                    return redirect(payment_url)
                else:
                    messages.error(request, f'決済リンクの作成に失敗しました: {", ".join(payment_result.get("errors", []))}')
                    return redirect('reservations:reservation_confirm')
            else:
                # 金額が0円の場合は直接予約を確定
                for reservation in all_created_reservations:
                    reservation.status = 'confirmed'
                    reservation.save()
                
                # セッションの予約データをクリア
                del request.session[session_key]
                
                messages.success(request, f'{len(all_created_reservations)}件の予約を作成しました。')
                return redirect('reservations:index')
        
        # 単一日の予約処理（既存の処理）
        location_id = reservation_data.get('location')
        time_slot_ids = reservation_data.get('time_slot_ids', [])
        reservation_date_str = reservation_data.get('date')
        
        location = Location.objects.get(id=location_id)
        time_slots = TimeSlot.objects.filter(id__in=time_slot_ids) if time_slot_ids else []
        reservation_date = datetime.fromisoformat(reservation_date_str).date() if reservation_date_str else None
        
        if not reservation_date:
            raise ValueError('予約日が不正です。')
        
        # 編集モードかどうかをチェック
        is_edit = reservation_data.get('is_edit', False)
        edit_reservation_ids = reservation_data.get('edit_reservation_ids', [])
        
        # 金額を計算（30分単位）
        total_amount = 0
        price_per_30min = location.price_per_30min or 0
        
        for time_slot in time_slots:
            start_datetime = datetime.combine(date.today(), time_slot.start_time)
            end_datetime = datetime.combine(date.today(), time_slot.end_time)
            if end_datetime < start_datetime:
                end_datetime += timedelta(days=1)
            
            duration = end_datetime - start_datetime
            total_minutes = duration.total_seconds() / 60
            units_30min = int((total_minutes + 29) // 30)
            slot_amount = units_30min * price_per_30min
            total_amount += slot_amount
        
        # 金額が0より大きい場合はSquare決済リンクを作成
        if total_amount > 0 and SQUARE_AVAILABLE:
            # まず予約を作成（pending状態）
            created_reservations = []
            if is_edit and edit_reservation_ids:
                # 編集モード：既存予約を更新/削除/作成
                existing_reservations = Reservation.objects.filter(id__in=edit_reservation_ids)
                
                # 選択解除された既存予約を削除
                deselected_reservation_ids = reservation_data.get('deselected_reservation_ids', [])
                deleted_count = 0
                if deselected_reservation_ids:
                    if request.user.is_superuser:
                        deleted_reservations = Reservation.objects.filter(id__in=deselected_reservation_ids)
                    else:
                        deleted_reservations = Reservation.objects.filter(
                            id__in=deselected_reservation_ids,
                            created_by=request.user
                        )
                    deleted_count = deleted_reservations.delete()[0]
                
                # 削除後の既存予約を再取得
                remaining_reservations = Reservation.objects.filter(id__in=edit_reservation_ids)
                existing_reservation_dict = {r.time_slot.id: r for r in remaining_reservations}
                
                # 各時間枠ごとに予約を更新または作成
                for time_slot in time_slots:
                    existing = existing_reservation_dict.get(time_slot.id)
                    
                    if existing:
                        # 既存予約を更新
                        duplicate = Reservation.objects.filter(
                            location=location,
                            time_slot=time_slot,
                            date=reservation_date,
                            status__in=['confirmed', 'pending']
                        ).exclude(pk=existing.pk)
                        
                        if duplicate.exists():
                            continue
                        
                        existing.location = location
                        existing.date = reservation_date
                        existing.customer_name = reservation_data.get('customer_name')
                        existing.customer_email = reservation_data.get('customer_email')
                        existing.customer_phone = reservation_data.get('customer_phone')
                        existing.notes = reservation_data.get('notes', '')
                        existing.status = 'pending'  # 決済待ち状態
                        existing.save()
                        created_reservations.append(existing)
                    else:
                        # 新規予約を作成
                        duplicate = Reservation.objects.filter(
                            location=location,
                            time_slot=time_slot,
                            date=reservation_date,
                            status__in=['confirmed', 'pending']
                        )
                        
                        if duplicate.exists():
                            continue
                        
                        reservation = Reservation.objects.create(
                            location=location,
                            time_slot=time_slot,
                            date=reservation_date,
                            customer_name=reservation_data.get('customer_name'),
                            customer_email=reservation_data.get('customer_email'),
                            customer_phone=reservation_data.get('customer_phone'),
                            notes=reservation_data.get('notes', ''),
                            status='pending',  # 決済待ち状態
                            created_by=request.user
                        )
                        created_reservations.append(reservation)
            else:
                # 新規予約モード：予約を作成
                deselected_reservation_ids = reservation_data.get('deselected_reservation_ids', [])
                if deselected_reservation_ids and request.user.is_authenticated:
                    Reservation.objects.filter(
                        id__in=deselected_reservation_ids,
                        created_by=request.user
                    ).delete()
                
                for time_slot in time_slots:
                    # 重複チェック
                    duplicate = Reservation.objects.filter(
                        location=location,
                        time_slot=time_slot,
                        date=reservation_date,
                        status__in=['confirmed', 'pending']
                    )
                    
                    if duplicate.exists():
                        continue
                    
                    reservation = Reservation.objects.create(
                        location=location,
                        time_slot=time_slot,
                        date=reservation_date,
                        customer_name=reservation_data.get('customer_name'),
                        customer_email=reservation_data.get('customer_email'),
                        customer_phone=reservation_data.get('customer_phone'),
                        notes=reservation_data.get('notes', ''),
                        status='pending',  # 決済待ち状態
                        created_by=request.user if request.user.is_authenticated else None
                    )
                    created_reservations.append(reservation)
            
            if not created_reservations:
                messages.error(request, '予約の作成に失敗しました。')
                return redirect('reservations:reservation_confirm')
            
            # 決済リンクの説明を作成
            time_slot_str = ', '.join([f"{ts.start_time.strftime('%H:%M')}-{ts.end_time.strftime('%H:%M')}" for ts in time_slots[:3]])
            if len(time_slots) > 3:
                time_slot_str += f" 他{len(time_slots)-3}枠"
            description = f'予約料金 - {location.name} ({reservation_date.strftime("%Y年%m月%d日")} {time_slot_str})'
            
            # 決済リンクを作成
            order_id = f"reservation_edit_{edit_reservation_ids[0]}" if (is_edit and edit_reservation_ids) else f"reservation_{created_reservations[0].id}"
            result = create_payment_link(request, total_amount, order_id, description)
            
            if result['success']:
                # 決済トランザクションを保存（最初の予約に紐付け）
                transaction = PaymentTransaction.objects.create(
                    reservation=created_reservations[0],
                    payment_link_id=result['payment_link_id'],
                    payment_link_url=result['payment_link_url'],
                    square_order_id=result.get('order_id'),
                    amount=total_amount,
                    status='pending'
                )
                
                # セッションから予約データを削除
                del request.session[session_key]
                
                # 予約詳細画面にリダイレクト（決済リンクはテンプレートで新しいタブで開く）
                messages.success(request, '予約を登録しました。決済を完了してください。')
                return render(request, 'reservations/reservation_payment.html', {
                    'reservation': created_reservations[0],
                    'payment_link_url': result['payment_link_url'],
                    'total_amount': total_amount,
                })
            else:
                # Square APIエラーの場合、作成した予約を削除してエラーを表示
                for reservation in created_reservations:
                    reservation.delete()
                error_msg = ', '.join(result.get('errors', ['決済リンクの作成に失敗しました。']))
                messages.error(request, f'決済リンクの作成に失敗しました: {error_msg}')
                return redirect('reservations:reservation_confirm')
        
        # 金額が0円の場合は直接予約を作成
        if is_edit and edit_reservation_ids:
            # 編集モード：既存予約を更新/削除/作成
            existing_reservations = Reservation.objects.filter(id__in=edit_reservation_ids)
            
            # 選択解除された既存予約を削除（最初に削除する）
            deselected_reservation_ids = reservation_data.get('deselected_reservation_ids', [])
            deleted_count = 0
            if deselected_reservation_ids:
                # 編集モードでは、選択解除された予約を削除
                # 権限チェック：自分の予約またはスーパーユーザーの場合のみ削除可能
                if request.user.is_superuser:
                    deleted_reservations = Reservation.objects.filter(id__in=deselected_reservation_ids)
                else:
                    deleted_reservations = Reservation.objects.filter(
                        id__in=deselected_reservation_ids,
                        created_by=request.user
                    )
                
                deleted_count = deleted_reservations.delete()[0]
                if deleted_count > 0:
                    messages.info(request, f'{deleted_count}件の既存予約を削除しました。')
            
            # 削除後の既存予約を再取得（削除された予約を除外）
            remaining_reservations = Reservation.objects.filter(id__in=edit_reservation_ids)
            existing_reservation_dict = {r.time_slot.id: r for r in remaining_reservations}
            
            # 各時間枠ごとに予約を更新または作成
            updated_reservations = []
            for time_slot in time_slots:
                # 既存予約があるかチェック
                existing = existing_reservation_dict.get(time_slot.id)
                
                if existing:
                    # 既存予約を更新（場所、日付、時間枠が変更された場合の重複チェック）
                    duplicate = Reservation.objects.filter(
                        location=location,
                        time_slot=time_slot,
                        date=reservation_date,
                        status__in=['confirmed', 'pending']
                    ).exclude(pk=existing.pk)
                    
                    if duplicate.exists():
                        messages.warning(request, f'時間枠 {time_slot} は既に予約されています。')
                        continue
                    
                    # 既存予約を更新
                    existing.location = location
                    existing.date = reservation_date
                    existing.customer_name = reservation_data.get('customer_name')
                    existing.customer_email = reservation_data.get('customer_email')
                    existing.customer_phone = reservation_data.get('customer_phone')
                    existing.notes = reservation_data.get('notes', '')
                    existing.save()
                    updated_reservations.append(existing)
                else:
                    # 新規予約を作成する前に重複チェック
                    duplicate = Reservation.objects.filter(
                        location=location,
                        time_slot=time_slot,
                        date=reservation_date,
                        status__in=['confirmed', 'pending']
                    )
                    
                    if duplicate.exists():
                        messages.warning(request, f'時間枠 {time_slot} は既に予約されています。')
                        continue
                    
                    # 新規予約を作成
                    reservation = Reservation.objects.create(
                        location=location,
                        time_slot=time_slot,
                        date=reservation_date,
                        customer_name=reservation_data.get('customer_name'),
                        customer_email=reservation_data.get('customer_email'),
                        customer_phone=reservation_data.get('customer_phone'),
                        notes=reservation_data.get('notes', ''),
                        status='pending',
                        created_by=request.user
                    )
                    updated_reservations.append(reservation)
            
            # セッションから予約データを削除
            del request.session[session_key]
            
            if updated_reservations:
                if len(updated_reservations) == 1:
                    messages.success(request, '予約が正常に更新されました。')
                    return redirect('reservations:reservation_detail', pk=updated_reservations[0].pk)
                else:
                    messages.success(request, f'{len(updated_reservations)}件の予約が正常に更新されました。')
                    # 最初の予約の詳細画面にリダイレクト
                    first_reservation = Reservation.objects.filter(
                        date=reservation_date,
                        location=location,
                        customer_email=reservation_data.get('customer_email'),
                        status__in=['confirmed', 'pending']
                    ).order_by('time_slot__start_time').first()
                    
                    if first_reservation:
                        return redirect('reservations:reservation_detail', pk=first_reservation.pk)
                    else:
                        return redirect('reservations:reservation_list')
            else:
                messages.error(request, '予約の更新に失敗しました。')
                return redirect('reservations:reservation_list')
        else:
            # 新規予約モード
            # 金額を計算（30分単位）
            total_amount = 0
            price_per_30min = location.price_per_30min or 0
            
            for time_slot in time_slots:
                start_datetime = datetime.combine(date.today(), time_slot.start_time)
                end_datetime = datetime.combine(date.today(), time_slot.end_time)
                if end_datetime < start_datetime:
                    end_datetime += timedelta(days=1)
                
                duration = end_datetime - start_datetime
                total_minutes = duration.total_seconds() / 60
                units_30min = int((total_minutes + 29) // 30)
                slot_amount = units_30min * price_per_30min
                total_amount += slot_amount
            
            # 金額が0より大きい場合はSquare決済リンクを作成
            if total_amount > 0 and SQUARE_AVAILABLE:
                # 決済リンクの説明を作成
                time_slot_str = ', '.join([f"{ts.start_time.strftime('%H:%M')}-{ts.end_time.strftime('%H:%M')}" for ts in time_slots[:3]])
                if len(time_slots) > 3:
                    time_slot_str += f" 他{len(time_slots)-3}枠"
                description = f'予約料金 - {location.name} ({reservation_date.strftime("%Y年%m月%d日")} {time_slot_str})'
                
                # 決済リンクを作成
                order_id = f"reservation_{datetime.now().timestamp()}"
                result = create_payment_link(request, total_amount, order_id, description)
                
                if result['success']:
                    # 決済トランザクションを保存
                    transaction = PaymentTransaction.objects.create(
                        reservation=None,  # 予約は決済完了後に紐付け
                        payment_link_id=result['payment_link_id'],
                        payment_link_url=result['payment_link_url'],
                        square_order_id=result.get('order_id'),
                        amount=total_amount,
                        status='pending'
                    )
                    
                    # セッションに決済トランザクションIDを保存
                    reservation_data['payment_transaction_id'] = transaction.id
                    request.session[session_key] = reservation_data
                    
                    # Square決済ページにリダイレクト
                    messages.info(request, '決済を完了してください。')
                    return redirect(result['payment_link_url'])
                else:
                    # Square APIエラーの場合、エラーメッセージを表示して予約確認画面に戻る
                    error_msg = ', '.join(result.get('errors', ['決済リンクの作成に失敗しました。']))
                    messages.error(request, f'決済リンクの作成に失敗しました: {error_msg}')
                    return redirect('reservations:reservation_confirm')
            
            # 金額が0円の場合は直接予約を作成
            # 選択解除された既存予約を削除
            deselected_reservation_ids = reservation_data.get('deselected_reservation_ids', [])
            deleted_count = 0
            if deselected_reservation_ids and request.user.is_authenticated:
                deleted_count = Reservation.objects.filter(
                    id__in=deselected_reservation_ids,
                    created_by=request.user
                ).delete()[0]
                if deleted_count > 0:
                    messages.info(request, f'{deleted_count}件の既存予約を削除しました。')
            
            # 各時間枠ごとに予約を作成（既存予約はスキップ）
            created_reservations = []
            for time_slot in time_slots:
                # 既に自分の予約が存在するかチェック
                my_existing = Reservation.objects.filter(
                    location=location,
                    time_slot=time_slot,
                    date=reservation_date,
                    created_by=request.user if request.user.is_authenticated else None,
                    status__in=['confirmed', 'pending']
                )
                if my_existing.exists():
                    # 既存予約はそのまま維持
                    created_reservations.append(my_existing.first())
                    continue
                
                # 他人が予約している場合はスキップ
                others_existing = Reservation.objects.filter(
                    location=location,
                    time_slot=time_slot,
                    date=reservation_date,
                    status__in=['confirmed', 'pending']
                )
                if others_existing.exists():
                    messages.warning(request, f'時間枠 {time_slot} は既に予約されています。')
                    continue
                
                # 新規予約を作成
                reservation = Reservation.objects.create(
                    location=location,
                    time_slot=time_slot,
                    date=reservation_date,
                    customer_name=reservation_data.get('customer_name'),
                    customer_email=reservation_data.get('customer_email'),
                    customer_phone=reservation_data.get('customer_phone'),
                    notes=reservation_data.get('notes', ''),
                    status='pending',
                    created_by=request.user if request.user.is_authenticated else None
                )
                created_reservations.append(reservation)
            
            # セッションから予約データを削除
            del request.session[session_key]
            
            if created_reservations:
                if len(created_reservations) == 1:
                    messages.success(request, '予約が正常に作成されました。')
                    return redirect('reservations:reservation_detail', pk=created_reservations[0].pk)
                else:
                    messages.success(request, f'{len(created_reservations)}件の予約が正常に作成されました。')
                    return redirect('reservations:reservation_list')
            elif deselected_reservation_ids and deleted_count > 0:
                # 既存予約の削除のみの場合
                messages.success(request, '予約の変更が完了しました。')
                return redirect('reservations:reservation_list')
            else:
                messages.error(request, '予約の作成に失敗しました。')
                return redirect('reservations:reservation_create')
            
    except Exception as e:
        print(f"Debug: Error creating reservation - {str(e)}")
        messages.error(request, f'予約の作成中にエラーが発生しました: {str(e)}')
        return redirect('reservations:reservation_confirm')

def reservation_detail(request, pk):
    """予約詳細（連続予約も含む）"""
    reservation = get_object_or_404(Reservation, pk=pk)
    
    # 自分の予約か、スーパーユーザーかチェック（表示権限）
    can_view = True
    if request.user.is_authenticated:
        if request.user.is_superuser:
            can_view = True
        elif reservation.created_by == request.user:
            can_view = True
        elif request.user.email == reservation.customer_email:
            can_view = True
        else:
            # 一般ユーザーは自分の予約のみ閲覧可能
            can_view = False
    else:
        # 未ログインユーザーは閲覧不可
        can_view = False
    
    if not can_view:
        messages.error(request, 'この予約を閲覧する権限がありません。')
        return redirect('reservations:index')
    
    # 連続予約を取得（同じ日付、場所、ユーザーで時間が連続している予約）
    consecutive_reservations = [reservation]
    
    # 連続している予約を検出
    all_reservations = list(Reservation.objects.filter(
        date=reservation.date,
        location=reservation.location,
        customer_email=reservation.customer_email,
        status__in=['confirmed', 'pending']
    ).select_related('time_slot').order_by('time_slot__start_time'))
    
    # 現在の予約の位置を見つける
    current_index = None
    for i, r in enumerate(all_reservations):
        if r.id == reservation.id:
            current_index = i
            break
    
    if current_index is not None:
        # 前方向に連続している予約を追加
        for i in range(current_index - 1, -1, -1):
            prev_reservation = all_reservations[i]
            current_start = consecutive_reservations[0].time_slot.start_time
            prev_end = prev_reservation.time_slot.end_time
            
            # 連続しているかチェック
            if prev_end == current_start or (datetime.combine(date.today(), current_start) - datetime.combine(date.today(), prev_end)).total_seconds() <= 60:
                consecutive_reservations.insert(0, prev_reservation)
            else:
                break
        
        # 後方向に連続している予約を追加
        for i in range(current_index + 1, len(all_reservations)):
            next_reservation = all_reservations[i]
            current_end = consecutive_reservations[-1].time_slot.end_time
            next_start = next_reservation.time_slot.start_time
            
            # 連続しているかチェック
            if current_end == next_start or (datetime.combine(date.today(), next_start) - datetime.combine(date.today(), current_end)).total_seconds() <= 60:
                consecutive_reservations.append(next_reservation)
            else:
                break
    
    # 開始時間と終了時間を計算
    start_time = consecutive_reservations[0].time_slot.start_time
    end_time = consecutive_reservations[-1].time_slot.end_time
    
    # 金額を計算（30分単位）
    total_amount = 0
    time_slot_details = []
    price_per_30min = reservation.location.price_per_30min or 0
    
    for res in consecutive_reservations:
        time_slot = res.time_slot
        # 開始時間と終了時間の差を計算
        start_datetime = datetime.combine(date.today(), time_slot.start_time)
        end_datetime = datetime.combine(date.today(), time_slot.end_time)
        if end_datetime < start_datetime:
            # 日をまたぐ場合（例：23:00-01:00）
            end_datetime += timedelta(days=1)
        
        duration = end_datetime - start_datetime
        total_minutes = duration.total_seconds() / 60
        # 30分単位に切り上げ
        units_30min = int((total_minutes + 29) // 30)  # 切り上げ
        slot_amount = units_30min * price_per_30min
        
        time_slot_details.append({
            'time_slot': time_slot,
            'duration_minutes': int(total_minutes),
            'units_30min': units_30min,
            'amount': slot_amount
        })
        total_amount += slot_amount
    
    return render(request, 'reservations/reservation_detail.html', {
        'reservation': reservation,
        'consecutive_reservations': consecutive_reservations,
        'start_time': start_time,
        'end_time': end_time,
        'is_grouped': len(consecutive_reservations) > 1,
        'time_slot_details': time_slot_details,
        'total_amount': total_amount,
        'price_per_30min': price_per_30min,
    })

@login_required
def reservation_edit(request, pk):
    """予約編集（連続予約も含む）"""
    reservation = get_object_or_404(Reservation, pk=pk)
    
    # 自分の予約か、スーパーユーザーかチェック
    is_owner = False
    if request.user.is_superuser:
        is_owner = True
    elif reservation.created_by == request.user:
        is_owner = True
    elif request.user.is_authenticated and request.user.email == reservation.customer_email:
        is_owner = True
    
    if not is_owner:
        messages.error(request, 'この予約を編集する権限がありません。')
        return redirect('reservations:reservation_detail', pk=pk)
    
    # 連続予約を取得
    consecutive_reservations = [reservation]
    all_reservations = list(Reservation.objects.filter(
        date=reservation.date,
        location=reservation.location,
        customer_email=reservation.customer_email,
        status__in=['confirmed', 'pending']
    ).select_related('time_slot').order_by('time_slot__start_time'))
    
    current_index = None
    for i, r in enumerate(all_reservations):
        if r.id == reservation.id:
            current_index = i
            break
    
    if current_index is not None:
        # 前方向に連続している予約を追加
        for i in range(current_index - 1, -1, -1):
            prev_reservation = all_reservations[i]
            current_start = consecutive_reservations[0].time_slot.start_time
            prev_end = prev_reservation.time_slot.end_time
            if prev_end == current_start or (datetime.combine(date.today(), current_start) - datetime.combine(date.today(), prev_end)).total_seconds() <= 60:
                consecutive_reservations.insert(0, prev_reservation)
            else:
                break
        
        # 後方向に連続している予約を追加
        for i in range(current_index + 1, len(all_reservations)):
            next_reservation = all_reservations[i]
            current_end = consecutive_reservations[-1].time_slot.end_time
            next_start = next_reservation.time_slot.start_time
            if current_end == next_start or (datetime.combine(date.today(), next_start) - datetime.combine(date.today(), current_end)).total_seconds() <= 60:
                consecutive_reservations.append(next_reservation)
            else:
                break
    
    if request.method == 'POST':
        form = ReservationForm(request.POST, user=request.user, instance=reservation)
        if form.is_valid():
            # セッションに編集データを保存して確認画面に遷移
            session_key = 'reservation_data'
            cleaned_data = form.cleaned_data.copy()
            
            # locationオブジェクトをIDに変換
            if 'location' in cleaned_data and cleaned_data['location']:
                cleaned_data['location'] = cleaned_data['location'].id
            
            # dateを文字列に変換
            if 'date' in cleaned_data and cleaned_data['date']:
                cleaned_data['date'] = cleaned_data['date'].isoformat()
            
            # 時間枠IDを保存
            selected_time_slots = cleaned_data.get('time_slots', [])
            cleaned_data['time_slot_ids'] = [ts.id for ts in selected_time_slots]
            # time_slotsオブジェクトはセッションに保存できないので削除
            if 'time_slots' in cleaned_data:
                del cleaned_data['time_slots']
            
            # 編集フラグと既存予約IDを保存
            cleaned_data['is_edit'] = True
            cleaned_data['edit_reservation_ids'] = [r.id for r in consecutive_reservations]
            
            # 選択解除された予約IDを保存（確定時に削除するため）
            selected_time_slot_ids = cleaned_data['time_slot_ids']
            deselected_reservation_ids = []
            for existing_reservation in consecutive_reservations:
                if existing_reservation.time_slot.id not in selected_time_slot_ids:
                    deselected_reservation_ids.append(existing_reservation.id)
            cleaned_data['deselected_reservation_ids'] = deselected_reservation_ids
            
            request.session[session_key] = cleaned_data
            return redirect('reservations:reservation_confirm')
    else:
        # 初期データを設定（連続予約のすべての時間枠を選択）
        initial_data = {
            'location': reservation.location,
            'date': reservation.date,
            'customer_name': reservation.customer_name,
            'customer_email': reservation.customer_email,
            'customer_phone': reservation.customer_phone,
            'notes': reservation.notes,
        }
        form = ReservationForm(initial=initial_data, user=request.user, instance=reservation)
        # 連続予約の時間枠を初期選択
        form.fields['time_slots'].initial = [r.time_slot for r in consecutive_reservations]
    
    return render(request, 'reservations/reservation_form.html', {
        'form': form,
        'title': '予約編集',
        'reservation': reservation,
        'consecutive_reservations': consecutive_reservations,
        'is_grouped': len(consecutive_reservations) > 1,
        'initial_time_slot_ids': [r.time_slot.id for r in consecutive_reservations]
    })

@login_required
def reservation_delete(request, pk):
    """予約削除"""
    reservation = get_object_or_404(Reservation, pk=pk)
    
    # 自分の予約か、スーパーユーザーかチェック
    is_owner = False
    if request.user.is_superuser:
        is_owner = True
    elif reservation.created_by == request.user:
        is_owner = True
    elif request.user.is_authenticated and request.user.email == reservation.customer_email:
        is_owner = True
    
    if not is_owner:
        messages.error(request, 'この予約を削除する権限がありません。')
        return redirect('reservations:reservation_detail', pk=pk)
    
    if request.method == 'POST':
        reservation.delete()
        messages.success(request, '予約が正常に削除されました。')
        if request.user.is_superuser:
            return redirect('reservations:reservation_list')
        else:
            return redirect('reservations:index')
    
    return render(request, 'reservations/reservation_confirm_delete.html', {
        'reservation': reservation
    })

@login_required
@superuser_required
def admin_dashboard(request):
    """管理者ダッシュボード"""
    # 今日の予約数
    today = date.today()
    today_reservations = Reservation.objects.filter(date=today).count()
    
    # 今月の予約数
    month_start = today.replace(day=1)
    month_reservations = Reservation.objects.filter(date__gte=month_start).count()
    
    # 最近の予約（最新5件）
    recent_reservations = Reservation.objects.order_by('-created_at')[:5]
    
    # 場所別の予約数
    location_stats = Location.objects.annotate(
        reservation_count=Count('reservation')
    ).order_by('-reservation_count')
    
    # 今週の予約
    week_start = today - timedelta(days=today.weekday())
    week_reservations = Reservation.objects.filter(
        date__gte=week_start,
        date__lte=week_start + timedelta(days=6)
    ).order_by('date', 'time_slot__start_time')
    
    context = {
        'today_reservations': today_reservations,
        'month_reservations': month_reservations,
        'recent_reservations': recent_reservations,
        'location_stats': location_stats,
        'week_reservations': week_reservations,
    }
    
    return render(request, 'reservations/admin_dashboard.html', context)

@login_required
@superuser_required
def location_management(request):
    """場所管理（管理者のみ）"""
    try:
        locations = Location.objects.all().order_by('name')
        return render(request, 'reservations/location_management.html', {
            'locations': locations
        })
    except Exception as e:
        print(f"Debug: Error in location_management - {str(e)}")
        messages.error(request, f'場所管理画面の読み込み中にエラーが発生しました: {str(e)}')
        return redirect('reservations:admin_dashboard')

@login_required
@superuser_required
def location_add(request):
    """場所追加（管理者のみ）"""
    if request.method == 'POST':
        form = LocationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, '場所が正常に追加されました。')
            return redirect('reservations:location_management')
    else:
        form = LocationForm()
    
    return render(request, 'reservations/location_form.html', {
        'form': form,
        'title': '場所追加'
    })

@login_required
@superuser_required
def location_edit(request, pk):
    """場所編集（管理者のみ）"""
    location = get_object_or_404(Location, pk=pk)
    if request.method == 'POST':
        form = LocationForm(request.POST, instance=location)
        if form.is_valid():
            form.save()
            messages.success(request, '場所が正常に更新されました。')
            return redirect('reservations:location_management')
    else:
        form = LocationForm(instance=location)
    
    return render(request, 'reservations/location_form.html', {
        'form': form,
        'title': '場所編集',
        'location': location
    })

@login_required
@superuser_required
def location_delete(request, pk):
    """場所削除（管理者のみ）"""
    location = get_object_or_404(Location, pk=pk)
    if request.method == 'POST':
        location.delete()
        messages.success(request, '場所が正常に削除されました。')
        return redirect('reservations:location_management')
    
    return render(request, 'reservations/location_confirm_delete.html', {
        'location': location
    })

def check_availability(request):
    """場所と時間の空き状況をチェック（AJAX）"""
    if request.method == 'GET':
        location_id = request.GET.get('location')
        date_str = request.GET.get('date')
        
        if location_id and date_str:
            try:
                location = Location.objects.get(id=location_id, is_active=True)
                reservation_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                
                # その日の予約済み時間枠を取得
                all_reservations = Reservation.objects.filter(
                    location=location,
                    date=reservation_date,
                    status__in=['confirmed', 'pending']
                ).select_related('time_slot', 'created_by')
                
                # ログイン済みユーザーの既存予約を取得
                my_reservation_slot_ids = []
                if request.user.is_authenticated:
                    my_reservations = all_reservations.filter(created_by=request.user)
                    my_reservation_slot_ids = list(my_reservations.values_list('time_slot_id', flat=True))
                
                # 他人が予約している時間枠IDを取得
                others_booked_slot_ids = []
                if request.user.is_authenticated:
                    others_reservations = all_reservations.exclude(created_by=request.user)
                else:
                    others_reservations = all_reservations
                others_booked_slot_ids = list(others_reservations.values_list('time_slot_id', flat=True))
                
                # すべての予約済み時間枠ID
                all_booked_slot_ids = list(all_reservations.values_list('time_slot_id', flat=True))
                
                # 利用可能な時間枠を取得（他人が予約している時間枠は除外）
                available_slots = TimeSlot.objects.filter(
                    is_active=True
                ).exclude(id__in=others_booked_slot_ids)
                
                # 自分の既存予約の詳細情報
                my_reservations_data = []
                if request.user.is_authenticated:
                    for reservation in all_reservations.filter(created_by=request.user):
                        my_reservations_data.append({
                            'id': reservation.id,
                            'time_slot_id': reservation.time_slot.id,
                            'time_slot': {
                                'id': reservation.time_slot.id,
                                'start_time': reservation.time_slot.start_time.strftime('%H:%M'),
                                'end_time': reservation.time_slot.end_time.strftime('%H:%M')
                            }
                        })
                
                return JsonResponse({
                    'available_slots': list(available_slots.values('id', 'start_time', 'end_time')),
                    'booked_slots': list(all_booked_slot_ids),
                    'my_reservation_slot_ids': my_reservation_slot_ids,
                    'my_reservations': my_reservations_data,
                    'others_booked_slot_ids': others_booked_slot_ids
                })
            except (Location.DoesNotExist, ValueError):
                return JsonResponse({'error': '無効なリクエストです。'}, status=400)
        
        return JsonResponse({'error': '必要なパラメータが不足しています。'}, status=400)
    
    return JsonResponse({'error': 'GETメソッドのみサポートしています。'}, status=405)

def reservation_weekly_calendar(request):
    """週間カレンダーで予約を選択する画面"""
    location_id = request.GET.get('location')
    
    if not location_id:
        messages.warning(request, '場所を選択してください。')
        return redirect('reservations:reservation_create')
    
    try:
        location = Location.objects.get(id=location_id, is_active=True)
    except Location.DoesNotExist:
        messages.error(request, '指定された場所が見つかりません。')
        return redirect('reservations:reservation_create')
    
    # 週の開始日を取得（デフォルトは今日、またはURLパラメータから）
    week_start_str = request.GET.get('week_start')
    if week_start_str:
        try:
            week_start = datetime.strptime(week_start_str, '%Y-%m-%d').date()
        except ValueError:
            week_start = date.today()
    else:
        week_start = date.today()
    
    # 週の開始日を月曜日に調整（または指定された日から7日間）
    # 画像を見ると土曜日から始まっているので、選択された日から7日間を表示
    week_dates = [week_start + timedelta(days=i) for i in range(7)]
    
    # すべての時間枠を取得
    all_time_slots = TimeSlot.objects.filter(is_active=True).order_by('start_time')
    
    # 週間の予約状況を取得
    week_reservations = Reservation.objects.filter(
        location=location,
        date__in=week_dates,
        status__in=['confirmed', 'pending']
    ).select_related('time_slot', 'created_by')
    
    # 日付と時間枠ごとの予約状況を整理（テンプレートでアクセスしやすい形式）
    availability_data = []
    for slot in all_time_slots:
        slot_data = {
            'slot': slot,
            'dates': []
        }
        for d in week_dates:
            # その日のその時間枠の予約を取得
            reservations = week_reservations.filter(date=d, time_slot=slot)
            
            # 週間カレンダーでは、ログインユーザーに依存せず予約状況のみを反映
            # 予約があれば予約済み（利用不可）、なければ利用可能
            has_reservation = reservations.exists()
            
            slot_data['dates'].append({
                'date': d,
                'is_available': not has_reservation,
                'is_my_reservation': False,  # 週間カレンダーでは区別しない
                'is_booked_by_others': has_reservation
            })
        availability_data.append(slot_data)
    
    context = {
        'location': location,
        'week_start': week_start,
        'week_dates': week_dates,
        'time_slots': all_time_slots,
        'availability_data': availability_data,
        'prev_week': week_start - timedelta(days=7),
        'next_week': week_start + timedelta(days=7),
    }
    
    return render(request, 'reservations/reservation_weekly_calendar.html', context)

def check_weekly_availability(request):
    """週間の空き状況をチェック（AJAX）"""
    if request.method == 'GET':
        location_id = request.GET.get('location')
        week_start_str = request.GET.get('week_start')
        
        if location_id and week_start_str:
            try:
                location = Location.objects.get(id=location_id, is_active=True)
                week_start = datetime.strptime(week_start_str, '%Y-%m-%d').date()
                
                # 週の日付リスト
                week_dates = [week_start + timedelta(days=i) for i in range(7)]
                
                # すべての時間枠を取得
                all_time_slots = TimeSlot.objects.filter(is_active=True).order_by('start_time')
                
                # 週間の予約状況を取得
                week_reservations = Reservation.objects.filter(
                    location=location,
                    date__in=week_dates,
                    status__in=['confirmed', 'pending']
                ).select_related('time_slot', 'created_by')
                
                # 日付と時間枠ごとの予約状況を整理
                availability_data = {}
                for d in week_dates:
                    date_str = d.isoformat()
                    availability_data[date_str] = {}
                    
                    for slot in all_time_slots:
                        reservations = week_reservations.filter(date=d, time_slot=slot)
                        is_booked_by_others = False
                        is_my_reservation = False
                        
                        if request.user.is_authenticated:
                            my_reservation = reservations.filter(created_by=request.user).first()
                            if my_reservation:
                                is_my_reservation = True
                            else:
                                is_booked_by_others = reservations.exists()
                        else:
                            is_booked_by_others = reservations.exists()
                        
                        availability_data[date_str][slot.id] = {
                            'is_available': not is_booked_by_others,
                            'is_my_reservation': is_my_reservation,
                            'is_booked_by_others': is_booked_by_others
                        }
                
                return JsonResponse({
                    'availability': availability_data,
                    'time_slots': [
                        {
                            'id': slot.id,
                            'start_time': slot.start_time.strftime('%H:%M'),
                            'end_time': slot.end_time.strftime('%H:%M')
                        }
                        for slot in all_time_slots
                    ]
                })
            except (Location.DoesNotExist, ValueError) as e:
                return JsonResponse({'error': f'無効なリクエストです: {str(e)}'}, status=400)
        
        return JsonResponse({'error': '必要なパラメータが不足しています。'}, status=400)
    
    return JsonResponse({'error': 'GETメソッドのみサポートしています。'}, status=405)

@login_required
@superuser_required
def time_slot_management(request):
    """時間枠管理"""
    time_slots = TimeSlot.objects.all().order_by('start_time')
    return render(request, 'reservations/time_slot_management.html', {
        'time_slots': time_slots
    })

@login_required
@superuser_required
def time_slot_add(request):
    """時間枠追加"""
    if request.method == 'POST':
        form = TimeSlotForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, '時間枠を追加しました。')
            return redirect('reservations:time_slot_management')
    else:
        form = TimeSlotForm()
    
    return render(request, 'reservations/time_slot_form.html', {
        'form': form,
        'title': '時間枠追加'
    })

@login_required
@superuser_required
def time_slot_edit(request, pk):
    """時間枠編集"""
    time_slot = get_object_or_404(TimeSlot, pk=pk)
    
    if request.method == 'POST':
        form = TimeSlotForm(request.POST, instance=time_slot)
        if form.is_valid():
            form.save()
            messages.success(request, '時間枠を更新しました。')
            return redirect('reservations:time_slot_management')
    else:
        form = TimeSlotForm(instance=time_slot)
    
    return render(request, 'reservations/time_slot_form.html', {
        'form': form,
        'title': '時間枠編集',
        'time_slot': time_slot
    })

@login_required
@superuser_required
def time_slot_delete(request, pk):
    """時間枠削除"""
    time_slot = get_object_or_404(TimeSlot, pk=pk)
    
    # 既存の予約があるかチェック
    existing_reservations = Reservation.objects.filter(time_slot=time_slot)
    
    if request.method == 'POST':
        if existing_reservations.exists():
            messages.error(request, f'この時間枠には {existing_reservations.count()} 件の予約があります。削除できません。')
        else:
            time_slot.delete()
            messages.success(request, '時間枠を削除しました。')
        return redirect('reservations:time_slot_management')
    
    return render(request, 'reservations/time_slot_confirm_delete.html', {
        'time_slot': time_slot,
        'existing_reservations': existing_reservations
    })

@login_required
@superuser_required
def plan_management(request):
    """プラン管理（管理者のみ）"""
    try:
        plans = Plan.objects.all().order_by('price')
        return render(request, 'reservations/plan_management.html', {
            'plans': plans
        })
    except Exception as e:
        print(f"Debug: Error in plan_management - {str(e)}")
        messages.error(request, f'プラン管理画面の読み込み中にエラーが発生しました: {str(e)}')
        return redirect('reservations:admin_dashboard')

@login_required
@superuser_required
def plan_add(request):
    """プラン追加（管理者のみ）"""
    if request.method == 'POST':
        form = PlanForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'プランが正常に追加されました。')
            return redirect('reservations:plan_management')
    else:
        form = PlanForm()
    
    return render(request, 'reservations/plan_form.html', {
        'form': form,
        'title': 'プラン追加'
    })

@login_required
@superuser_required
def plan_edit(request, pk):
    """プラン編集（管理者のみ）"""
    plan = get_object_or_404(Plan, pk=pk)
    if request.method == 'POST':
        form = PlanForm(request.POST, instance=plan)
        if form.is_valid():
            form.save()
            messages.success(request, 'プランが正常に更新されました。')
            return redirect('reservations:plan_management')
    else:
        form = PlanForm(instance=plan)
    
    return render(request, 'reservations/plan_form.html', {
        'form': form,
        'title': 'プラン編集',
        'plan': plan
    })

@login_required
@superuser_required
def plan_delete(request, pk):
    """プラン削除（管理者のみ）"""
    plan = get_object_or_404(Plan, pk=pk)
    
    # 既存の会員プロファイルがあるかチェック
    existing_profiles = MemberProfile.objects.filter(plan=plan)
    
    if request.method == 'POST':
        if existing_profiles.exists():
            messages.error(request, f'このプランを使用している会員が {existing_profiles.count()} 名います。削除できません。')
        else:
            plan.delete()
            messages.success(request, 'プランが正常に削除されました。')
        return redirect('reservations:plan_management')
    
    return render(request, 'reservations/plan_confirm_delete.html', {
        'plan': plan,
        'existing_profiles': existing_profiles
    })


def member_registration(request):
    """会員登録ウィザード"""
    # セッションキー
    session_key = 'member_registration_data'
    
    # ステップを取得
    step = int(request.GET.get('step', 1))
    
    # セッションからデータを取得
    registration_data = request.session.get(session_key, {})
    
    if step == 1:
        # Step1: 基本情報
        if request.method == 'POST':
            form = MemberRegistrationStep1Form(request.POST)
            if form.is_valid():
                # セッションに保存
                cleaned_data = form.cleaned_data.copy()
                registration_data['step1'] = cleaned_data
                request.session[session_key] = registration_data
                return redirect(f"{reverse('reservations:member_registration')}?step=2")
        else:
            # セッションからデータを復元
            initial_data = registration_data.get('step1', {}).copy()
            form = MemberRegistrationStep1Form(initial=initial_data)
        
        return render(request, 'reservations/member_registration_step1.html', {
            'form': form,
            'step': 1,
            'total_steps': 4
        })
    
    elif step == 2:
        # Step1のデータが必要
        if 'step1' not in registration_data:
            messages.warning(request, '最初から入力してください。')
            return redirect(f"{reverse('reservations:member_registration')}?step=1")
        
        # Step2: プラン選択
        if request.method == 'POST':
            form = MemberRegistrationStep2Form(request.POST)
            if form.is_valid():
                # セッションに保存（PlanオブジェクトをIDに変換）
                cleaned_data = form.cleaned_data.copy()
                if 'plan' in cleaned_data and cleaned_data['plan']:
                    cleaned_data['plan_id'] = cleaned_data['plan'].id
                    del cleaned_data['plan']  # Planオブジェクトを削除
                registration_data['step2'] = cleaned_data
                request.session[session_key] = registration_data
                return redirect(f"{reverse('reservations:member_registration')}?step=3")
        else:
            # セッションからデータを復元（IDからPlanオブジェクトに変換）
            initial_data = registration_data.get('step2', {}).copy()
            if 'plan_id' in initial_data:
                try:
                    initial_data['plan'] = Plan.objects.get(id=initial_data['plan_id'])
                    del initial_data['plan_id']
                except Plan.DoesNotExist:
                    pass
            # セッションにデータがない場合は、フォームのデフォルト値を使用
            form = MemberRegistrationStep2Form(initial=initial_data)
        
        return render(request, 'reservations/member_registration_step2.html', {
            'form': form,
            'step': 2,
            'total_steps': 4,
            'plans': Plan.objects.filter(is_active=True)
        })
    
    elif step == 3:
        # Step1とStep2のデータが必要
        if 'step1' not in registration_data or 'step2' not in registration_data:
            messages.warning(request, '最初から入力してください。')
            return redirect(f"{reverse('reservations:member_registration')}?step=1")
        
        # Step3: 顔写真登録
        if request.method == 'POST':
            form = MemberRegistrationStep3Form(request.POST, request.FILES)
            # フォーム検証を緩和（Base64データの場合は検証不要）
            step3_data = {}
            if 'photo_base64' in request.POST and request.POST.get('photo_base64'):
                # Base64データ（ファイルアップロードまたはカメラ撮影）
                photo_base64 = request.POST.get('photo_base64')
                step3_data = {
                    'photo_type': 'base64',
                    'photo_base64': photo_base64
                }
                registration_data['step3'] = step3_data
                request.session[session_key] = registration_data
                return redirect(f"{reverse('reservations:member_registration')}?step=4")
            elif form.is_valid():
                # フォームが有効な場合は次へ（オプション）
                registration_data['step3'] = {}
                request.session[session_key] = registration_data
                return redirect(f"{reverse('reservations:member_registration')}?step=4")
        else:
            form = MemberRegistrationStep3Form()
        
        # アップロード済みの写真がある場合
        photo_data = registration_data.get('step3', {})
        
        return render(request, 'reservations/member_registration_step3.html', {
            'form': form,
            'step': 3,
            'total_steps': 4,
            'photo_data': photo_data
        })
    
    elif step == 4:
        # Step1、Step2、Step3のデータが必要
        if 'step1' not in registration_data or 'step2' not in registration_data:
            messages.warning(request, '最初から入力してください。')
            return redirect(f"{reverse('reservations:member_registration')}?step=1")
        
        # Step4: クレジットカード情報
        if request.method == 'POST':
            form = MemberRegistrationStep4Form(request.POST)
            if form.is_valid():
                registration_data['step4'] = form.cleaned_data
                request.session[session_key] = registration_data
                
                # すべてのステップが完了したら、会員を作成
                try:
                    step1_data = registration_data['step1']
                    step2_data = registration_data['step2']
                    step3_data = registration_data.get('step3', {})
                    step4_data = registration_data['step4']
                    
                    # ユーザー作成
                    user = User.objects.create_user(
                        username=step1_data['email'],
                        email=step1_data['email'],
                        password=step1_data['password']
                    )
                    
                    # Planオブジェクトを取得
                    plan = None
                    if 'plan_id' in step2_data:
                        plan = Plan.objects.get(id=step2_data['plan_id'])
                    elif 'plan' in step2_data:
                        plan = step2_data['plan']
                    
                    profile = MemberProfile.objects.create(
                        user=user,
                        full_name=step1_data['full_name'],
                        gender=step1_data['gender'],
                        phone=step1_data['phone'],
                        postal_code=step1_data.get('postal_code', ''),
                        address=step1_data.get('address', ''),
                        plan=plan
                    )
                    
                    # 顔写真の保存
                    if step3_data.get('photo_type') == 'file':
                        # ファイルアップロードの場合はStep4で受け取れないので、セッションに保存された情報からは取得できない
                        # この場合、Step3で一時的に保存するか、Step4で再アップロードが必要
                        pass
                    elif step3_data.get('photo_type') == 'base64':
                        # Base64から画像を保存
                        photo_base64 = step3_data.get('photo_base64', '')
                        if photo_base64:
                            try:
                                # data:image/jpeg;base64, の部分を除去
                                if ',' in photo_base64:
                                    photo_base64 = photo_base64.split(',')[1]
                                image_data = base64.b64decode(photo_base64)
                                image_file = ContentFile(image_data, name='photo.jpg')
                                profile.photo = image_file
                                profile.save()
                            except Exception as e:
                                print(f"Error saving photo: {e}")
                                # エラーが発生しても続行
                    
                    # クレジットカード情報（簡易実装：実際には暗号化すべき）
                    # ここではセッションから取得したデータをそのまま保存（非推奨）
                    card_number = step4_data['card_number'].replace('-', '').replace(' ', '')
                    profile.card_number_encrypted = base64.b64encode(card_number.encode()).decode()
                    profile.card_expiry_month = step4_data['card_expiry_month']
                    profile.card_expiry_year = step4_data['card_expiry_year']
                    profile.card_cvc_encrypted = base64.b64encode(step4_data['card_cvc'].encode()).decode()
                    profile.save()
                    
                    # プランの料金がある場合はSquare決済にリダイレクト
                    if plan and plan.price > 0:
                        # セッションにユーザーIDを保存（決済完了後に会員登録を完了させるため）
                        request.session['pending_registration_user_id'] = user.id
                        
                        # Square決済リンクを作成
                        result = create_payment_link(
                            request,
                            amount=plan.price,
                            order_id=f"member_registration_{user.id}",
                            description=f'会員登録料金 - {plan.name}'
                        )
                        
                        if result['success']:
                            # 決済トランザクションを保存
                            transaction = PaymentTransaction.objects.create(
                                member_profile=profile,
                                payment_link_id=result['payment_link_id'],
                                payment_link_url=result['payment_link_url'],
                                square_order_id=result.get('order_id'),
                                amount=plan.price,
                                status='pending'
                            )
                            
                            # セッションをクリア（決済完了まで保持）
                            # del request.session[session_key]  # 決済完了まで保持
                            
                            # Square決済ページにリダイレクト
                            return redirect(result['payment_link_url'])
                        else:
                            # 決済リンク作成失敗時はエラーメッセージを表示
                            messages.error(request, f'決済リンクの作成に失敗しました: {", ".join(result["errors"])}')
                            # ユーザーとプロフィールを削除（ロールバック）
                            profile.delete()
                            user.delete()
                            return redirect(f"{reverse('reservations:member_registration')}?step=1")
                    else:
                        # 料金が0の場合は会員登録を完了
                        # セッションをクリア
                        del request.session[session_key]
                        
                        # 自動ログイン
                        login(request, user)
                        
                        # 会員登録完了メールを送信
                        try:
                            subject = '会員登録が完了しました'
                            message = render_to_string('reservations/emails/registration_complete.html', {
                                'user': user,
                                'profile': profile,
                                'site_url': request.build_absolute_uri('/')
                            })
                            send_mail(
                                subject,
                                '',  # プレーンテキストメールは空（HTMLメールのみ）
                                settings.DEFAULT_FROM_EMAIL,
                                [user.email],
                                html_message=message,
                                fail_silently=False,
                            )
                        except Exception as e:
                            # メール送信エラーはログに記録するが、登録処理は続行
                            print(f"メール送信エラー: {e}")
                        
                        messages.success(request, '会員登録が完了しました。')
                        return redirect('reservations:index')
                
                except Exception as e:
                    messages.error(request, f'会員登録中にエラーが発生しました: {str(e)}')
                    return redirect(f"{reverse('reservations:member_registration')}?step=1")
        else:
            form = MemberRegistrationStep4Form()
        
        return render(request, 'reservations/member_registration_step4.html', {
            'form': form,
            'step': 4,
            'total_steps': 4
        })
    
    else:
        messages.error(request, '無効なステップです。')
        return redirect(f"{reverse('reservations:member_registration')}?step=1")


@login_required
def user_profile(request):
    """ユーザー情報表示"""
    try:
        profile = MemberProfile.objects.get(user=request.user)
    except MemberProfile.DoesNotExist:
        profile = None
    
    return render(request, 'reservations/user_profile.html', {
        'profile': profile
    })


from .models import PaymentTransaction

try:
    from square import Square
    from square.environment import SquareEnvironment
    SQUARE_AVAILABLE = True
except ImportError:
    SQUARE_AVAILABLE = False
    Square = None
    SquareEnvironment = None


def get_square_client():
    """Square APIクライアントを取得"""
    if not SQUARE_AVAILABLE:
        raise ImportError('Square SDK is not installed')
    
    from django.conf import settings
    
    environment = SquareEnvironment.SANDBOX if settings.SQUARE_ENVIRONMENT == 'sandbox' else SquareEnvironment.PRODUCTION
    
    client = Square(
        token=settings.SQUARE_ACCESS_TOKEN,
        environment=environment
    )
    
    return client


def create_payment_link(request, amount, order_id=None, description=''):
    """Square決済リンクを作成"""
    try:
        client = get_square_client()
        from django.conf import settings
        
        # location_idを取得（必須）
        location_id = settings.SQUARE_LOCATION_ID
        if not location_id:
            return {
                'success': False,
                'errors': ['SQUARE_LOCATION_IDが設定されていません。']
            }
        
        # 決済リンクの作成
        result = client.checkout.payment_links.create(
            idempotency_key=f"{order_id}_{datetime.now().timestamp()}" if order_id else f"payment_{datetime.now().timestamp()}",
            quick_pay={
                'name': description or '決済',
                'price_money': {
                    'amount': int(amount),
                    'currency': 'JPY'
                },
                'location_id': location_id
            }
        )
        
        # レスポンスのエラーチェック
        if hasattr(result, 'errors') and result.errors:
            errors = result.errors
            return {
                'success': False,
                'errors': [str(error) for error in errors]
            }
        
        # レスポンスボディから決済リンク情報を取得
        if hasattr(result, 'body') and result.body:
            payment_link = result.body.payment_link if hasattr(result.body, 'payment_link') else result.body
            return {
                'success': True,
                'payment_link_id': payment_link.id if hasattr(payment_link, 'id') else None,
                'payment_link_url': payment_link.url if hasattr(payment_link, 'url') else None,
                'order_id': payment_link.order_id if hasattr(payment_link, 'order_id') else None
            }
        elif hasattr(result, 'payment_link'):
            # レスポンスが直接payment_linkを持っている場合
            payment_link = result.payment_link
            return {
                'success': True,
                'payment_link_id': payment_link.id if hasattr(payment_link, 'id') else None,
                'payment_link_url': payment_link.url if hasattr(payment_link, 'url') else None,
                'order_id': payment_link.order_id if hasattr(payment_link, 'order_id') else None
            }
        else:
            return {
                'success': False,
                'errors': ['決済リンクの作成に失敗しました。レスポンス形式が不明です。']
            }
    
    except Exception as e:
        return {
            'success': False,
            'errors': [str(e)]
        }


@login_required
def payment_create(request, reservation_id=None):
    """決済リンク作成（予約または会員登録用）"""
    if reservation_id:
        reservation = get_object_or_404(Reservation, pk=reservation_id)
        amount = 1000  # 予約料金（仮）
        description = f'予約料金 - {reservation.location.name}'
        order_id = f"reservation_{reservation.id}"
    else:
        # 会員登録料金
        try:
            profile = MemberProfile.objects.get(user=request.user)
            if profile.plan:
                amount = int(profile.plan.price)
            else:
                amount = 0
        except MemberProfile.DoesNotExist:
            amount = 0
        description = '会員登録料金'
        order_id = f"member_{request.user.id}"
    
    if amount <= 0:
        messages.warning(request, '決済する金額がありません。')
        return redirect('reservations:index')
    
    # 決済リンクを作成
    result = create_payment_link(request, amount, order_id, description)
    
    if result['success']:
        # 決済トランザクションを保存
        try:
            member_profile = MemberProfile.objects.get(user=request.user) if not reservation_id else None
        except MemberProfile.DoesNotExist:
            member_profile = None
        
        transaction = PaymentTransaction.objects.create(
            reservation=reservation if reservation_id else None,
            member_profile=member_profile,
            payment_link_id=result['payment_link_id'],
            payment_link_url=result['payment_link_url'],
            square_order_id=result.get('order_id'),
            amount=amount,
            status='pending'
        )
        
        # 決済リンクにリダイレクト
        return redirect(result['payment_link_url'])
    else:
        messages.error(request, f'決済リンクの作成に失敗しました: {", ".join(result["errors"])}')
        return redirect('reservations:index')


def payment_complete(request):
    """決済完了後のリダイレクト先"""
    payment_link_id = request.GET.get('payment_link_id')
    order_id = request.GET.get('order_id')
    
    transaction = None
    if payment_link_id:
        try:
            transaction = PaymentTransaction.objects.get(payment_link_id=payment_link_id)
        except PaymentTransaction.DoesNotExist:
            pass
    
    if not transaction and order_id:
        try:
            transaction = PaymentTransaction.objects.filter(square_order_id=order_id).first()
        except:
            pass
    
    if transaction:
        if transaction.status == 'completed':
            # 決済完了
            if transaction.member_profile:
                # 会員登録の場合は自動ログイン
                user = transaction.member_profile.user
                login(request, user)
                messages.success(request, '決済が完了しました。会員登録が完了しました。')
                return redirect('reservations:index')
            elif transaction.reservation:
                # 予約の場合は予約詳細ページへ
                messages.success(request, '決済が完了しました。予約が確定しました。')
                return redirect('reservations:reservation_detail', pk=transaction.reservation.id)
            else:
                # 予約がまだ作成されていない場合、セッションから予約を作成
                session_key = 'reservation_data'
                reservation_data = request.session.get(session_key)
                
                if reservation_data and reservation_data.get('payment_transaction_id') == transaction.id:
                    # 予約を作成
                    location_id = reservation_data.get('location')
                    time_slot_ids = reservation_data.get('time_slot_ids', [])
                    reservation_date_str = reservation_data.get('date')
                    
                    try:
                        location = Location.objects.get(id=location_id)
                        time_slots = TimeSlot.objects.filter(id__in=time_slot_ids) if time_slot_ids else []
                        reservation_date = datetime.fromisoformat(reservation_date_str).date() if reservation_date_str else None
                        
                        if reservation_date and time_slots:
                            # 各時間枠ごとに予約を作成
                            created_reservations = []
                            for time_slot in time_slots:
                                # 重複チェック
                                duplicate = Reservation.objects.filter(
                                    location=location,
                                    time_slot=time_slot,
                                    date=reservation_date,
                                    status__in=['confirmed', 'pending']
                                )
                                
                                if duplicate.exists():
                                    continue
                                
                                # 新規予約を作成
                                reservation = Reservation.objects.create(
                                    location=location,
                                    time_slot=time_slot,
                                    date=reservation_date,
                                    customer_name=reservation_data.get('customer_name'),
                                    customer_email=reservation_data.get('customer_email'),
                                    customer_phone=reservation_data.get('customer_phone'),
                                    notes=reservation_data.get('notes', ''),
                                    status='confirmed',
                                    created_by=request.user if request.user.is_authenticated else None
                                )
                                created_reservations.append(reservation)
                            
                            # 最初の予約にトランザクションを紐付け
                            if created_reservations:
                                transaction.reservation = created_reservations[0]
                                transaction.save()
                                
                                # セッションから予約データを削除
                                del request.session[session_key]
                                
                                messages.success(request, '決済が完了しました。予約が確定しました。')
                                return redirect('reservations:reservation_detail', pk=created_reservations[0].pk)
                    except Exception as e:
                        print(f"Error creating reservation in payment_complete: {e}")
                        messages.error(request, '予約の作成中にエラーが発生しました。')
                        return redirect('reservations:index')
                
                messages.info(request, '決済処理中です。しばらくお待ちください。')
                return redirect('reservations:index')
        else:
            messages.info(request, '決済処理中です。しばらくお待ちください。')
            return redirect('reservations:index')
    else:
        messages.error(request, '決済情報が見つかりませんでした。')
        return redirect('reservations:index')


@require_http_methods(["POST"])
def square_webhook(request):
    """Square Webhookエンドポイント"""
    from django.conf import settings
    from decouple import config as decouple_config
    
    # Webhook署名の検証（本番環境では必須）
    signature = request.headers.get('X-Square-Signature', '')
    webhook_secret = decouple_config('SQUARE_WEBHOOK_SECRET', default='')
    
    if webhook_secret:
        # 署名検証（簡易実装）
        body = request.body
        expected_signature = hmac.new(
            webhook_secret.encode('utf-8'),
            body,
            hashlib.sha256
        ).hexdigest()
        
        if not hmac.compare_digest(signature, expected_signature):
            return JsonResponse({'error': 'Invalid signature'}, status=401)
    
    try:
        data = json.loads(request.body)
        event_type = data.get('type')
        event_data = data.get('data', {})
        
        if event_type == 'payment.created' or event_type == 'payment.updated':
            # 決済イベントの処理
            payment = event_data.get('object', {}).get('payment', {})
            payment_id = payment.get('id')
            order_id = payment.get('order_id')
            status = payment.get('status')
            
            # トランザクションを更新（payment_link_idまたはsquare_payment_idで検索）
            transaction = None
            if order_id:
                # order_idで検索（決済リンクから作成された場合）
                transaction = PaymentTransaction.objects.filter(
                    square_order_id=order_id
                ).first()
            
            if not transaction and payment_id:
                # square_payment_idで検索
                transaction = PaymentTransaction.objects.filter(
                    square_payment_id=payment_id
                ).first()
            
            if transaction:
                # トランザクションを更新
                transaction.square_payment_id = payment_id
                transaction.status = 'completed' if status == 'COMPLETED' else 'failed'
                transaction.save()
                
                # 関連する予約を確定
                if transaction.reservation:
                    transaction.reservation.status = 'confirmed'
                    transaction.reservation.save()
                elif not transaction.reservation:
                    # セッションから予約データを取得して予約を作成
                    # 注意: Webhookは非同期で実行されるため、セッションにアクセスできない可能性がある
                    # そのため、トランザクションに予約情報を保存するか、別の方法で処理する必要がある
                    pass
            else:
                # 新規トランザクションを作成
                amount = int(payment.get('amount_money', {}).get('amount', 0))
                if amount > 0:
                    # JPYの場合はそのまま（セント単位ではない）
                    amount_yen = amount if amount < 10000 else amount / 100
                    PaymentTransaction.objects.create(
                        square_payment_id=payment_id,
                        square_order_id=order_id,
                        amount=amount_yen,
                        status='completed' if status == 'COMPLETED' else 'failed'
                    )
        
        return JsonResponse({'status': 'success'})
    
    except Exception as e:
        print(f"Webhook error: {e}")
        return JsonResponse({'error': str(e)}, status=400)
