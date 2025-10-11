from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.contrib.auth import authenticate, login
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from django.db.models import Q, Count
from datetime import date, datetime, timedelta
import json
from .models import Location, TimeSlot, Reservation
from .forms import ReservationForm, ReservationSearchForm, LocationForm, TimeSlotForm

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
        
        context.update({
            'today_reservations': today_reservations,
            'month_reservations': month_reservations,
            'location_count': location_count,
            'recent_count': recent_count,
        })
    
    return render(request, 'reservations/index.html', context)

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
        reservations = Reservation.objects.filter(
            date__gte=start_date,
            date__lte=end_date
        ).select_related('location', 'time_slot')
        
        events = []
        for reservation in reservations:
            # 予約の開始時間と終了時間を設定
            start_time = datetime.combine(reservation.date, reservation.time_slot.start_time)
            end_time = datetime.combine(reservation.date, reservation.time_slot.end_time)
            
            # イベントの色を設定（場所によって異なる色を使用）
            colors = ['#ffc107', '#e0a800', '#ff8c00', '#ff6b35', '#f7931e']
            color_index = reservation.location.id % len(colors)
            
            event = {
                'id': reservation.id,
                'title': f"{reservation.customer_name} - {reservation.location.name} - {reservation.time_slot.start_time.strftime('%H:%M')}-{reservation.time_slot.end_time.strftime('%H:%M')}",
                'start': start_time.isoformat(),
                'end': end_time.isoformat(),
                'backgroundColor': colors[color_index],
                'borderColor': colors[color_index],
                'textColor': '#000',
                'extendedProps': {
                    'location': reservation.location.name,
                    'customer_name': reservation.customer_name,
                    'customer_email': reservation.customer_email,
                    'customer_phone': reservation.customer_phone,
                    'status': reservation.status,
                    'notes': reservation.notes or ''
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
def reservation_list(request):
    """予約一覧（管理者のみ）"""
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
    
    # ページネーション
    paginator = Paginator(reservations, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'reservations/reservation_list.html', {
        'page_obj': page_obj,
        'form': form
    })

def reservation_create(request):
    """予約作成"""
    if request.method == 'POST':
        form = ReservationForm(request.POST)
        if form.is_valid():
            try:
                reservation = form.save(commit=False)
                if request.user.is_authenticated:
                    reservation.created_by = request.user
                reservation.save()
                messages.success(request, '予約が正常に作成されました。')
                return redirect('reservations:reservation_detail', pk=reservation.pk)
            except Exception as e:
                print(f"Debug: Error creating reservation - {str(e)}")
                messages.error(request, f'予約の作成中にエラーが発生しました: {str(e)}')
        else:
            print(f"Debug: Form errors - {form.errors}")
            messages.error(request, 'フォームにエラーがあります。以下を確認してください。')
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        # GETリクエストの場合：URLパラメータからlocationを取得
        location_id = request.GET.get('location')
        initial_data = {}
        
        if location_id:
            try:
                # デバッグ情報を追加
                print(f"Debug: location_id = {location_id}")
                location = Location.objects.get(id=location_id, is_active=True)
                print(f"Debug: location found = {location.name}")
                initial_data['location'] = location
            except Location.DoesNotExist:
                print(f"Debug: Location with id {location_id} does not exist")
                messages.warning(request, f'指定された場所（ID: {location_id}）が見つかりません。')
            except ValueError as e:
                print(f"Debug: ValueError - {e}")
                messages.warning(request, '無効な場所IDが指定されました。')
            except Exception as e:
                print(f"Debug: Exception - {e}")
                messages.error(request, f'場所の取得中にエラーが発生しました: {str(e)}')
        
        form = ReservationForm(initial=initial_data)
    
    return render(request, 'reservations/reservation_form.html', {
        'form': form,
        'title': '新規予約'
    })

def reservation_detail(request, pk):
    """予約詳細"""
    reservation = get_object_or_404(Reservation, pk=pk)
    return render(request, 'reservations/reservation_detail.html', {
        'reservation': reservation
    })

@login_required
def reservation_edit(request, pk):
    """予約編集（管理者のみ）"""
    reservation = get_object_or_404(Reservation, pk=pk)
    if request.method == 'POST':
        form = ReservationForm(request.POST, instance=reservation)
        if form.is_valid():
            form.save()
            messages.success(request, '予約が正常に更新されました。')
            return redirect('reservations:reservation_detail', pk=reservation.pk)
    else:
        form = ReservationForm(instance=reservation)
    
    return render(request, 'reservations/reservation_form.html', {
        'form': form,
        'title': '予約編集',
        'reservation': reservation
    })

@login_required
def reservation_delete(request, pk):
    """予約削除（管理者のみ）"""
    reservation = get_object_or_404(Reservation, pk=pk)
    if request.method == 'POST':
        reservation.delete()
        messages.success(request, '予約が正常に削除されました。')
        return redirect('reservations:reservation_list')
    
    return render(request, 'reservations/reservation_confirm_delete.html', {
        'reservation': reservation
    })

@login_required
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
                booked_slots = Reservation.objects.filter(
                    location=location,
                    date=reservation_date,
                    status__in=['confirmed', 'pending']
                ).values_list('time_slot_id', flat=True)
                
                # 利用可能な時間枠を取得
                available_slots = TimeSlot.objects.filter(
                    is_active=True
                ).exclude(id__in=booked_slots)
                
                return JsonResponse({
                    'available_slots': list(available_slots.values('id', 'start_time', 'end_time')),
                    'booked_slots': list(booked_slots)
                })
            except (Location.DoesNotExist, ValueError):
                return JsonResponse({'error': '無効なリクエストです。'}, status=400)
        
        return JsonResponse({'error': '必要なパラメータが不足しています。'}, status=400)
    
    return JsonResponse({'error': 'GETメソッドのみサポートしています。'}, status=405)

@login_required
def time_slot_management(request):
    """時間枠管理"""
    time_slots = TimeSlot.objects.all().order_by('start_time')
    return render(request, 'reservations/time_slot_management.html', {
        'time_slots': time_slots
    })

@login_required
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
