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
from .models import Location, TimeSlot, Reservation, Plan, MemberProfile
from .forms import (
    ReservationForm, ReservationSearchForm, LocationForm, TimeSlotForm,
    MemberRegistrationStep1Form, MemberRegistrationStep2Form,
    MemberRegistrationStep3Form, MemberRegistrationStep4Form
)

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
                # セッションに保存（dateオブジェクトを文字列に変換）
                cleaned_data = form.cleaned_data.copy()
                if 'birth_date' in cleaned_data and cleaned_data['birth_date']:
                    cleaned_data['birth_date'] = cleaned_data['birth_date'].isoformat()
                registration_data['step1'] = cleaned_data
                request.session[session_key] = registration_data
                return redirect(f"{reverse('reservations:member_registration')}?step=2")
        else:
            # セッションからデータを復元（文字列をdateオブジェクトに変換）
            initial_data = registration_data.get('step1', {}).copy()
            if 'birth_date' in initial_data and isinstance(initial_data['birth_date'], str):
                initial_data['birth_date'] = datetime.fromisoformat(initial_data['birth_date']).date()
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
                    
                    # プロフィール作成（birth_dateをdateオブジェクトに変換、plan_idからPlanオブジェクトを取得）
                    birth_date = step1_data['birth_date']
                    if isinstance(birth_date, str):
                        birth_date = datetime.fromisoformat(birth_date).date()
                    
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
                        birth_date=birth_date,
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
        
        # 決済リンクの作成
        result = client.checkout.payment_links.create(
            idempotency_key=f"{order_id}_{datetime.now().timestamp()}" if order_id else f"payment_{datetime.now().timestamp()}",
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
                'payment_link_id': payment_link.id if hasattr(payment_link, 'id') else None,
                'payment_link_url': payment_link.url if hasattr(payment_link, 'url') else None,
                'order_id': payment_link.order_id if hasattr(payment_link, 'order_id') else None
            }
        else:
            errors = result.errors if result.errors else []
            return {
                'success': False,
                'errors': [str(error) for error in errors]
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
    
    if payment_link_id:
        try:
            transaction = PaymentTransaction.objects.get(payment_link_id=payment_link_id)
            
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
            
            messages.info(request, '決済処理中です。しばらくお待ちください。')
            return redirect('reservations:index')
        except PaymentTransaction.DoesNotExist:
            messages.error(request, '決済情報が見つかりませんでした。')
            return redirect('reservations:index')
    
    messages.error(request, '決済情報が不正です。')
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
            
            # トランザクションを更新
            try:
                transaction = PaymentTransaction.objects.get(square_payment_id=payment_id)
                transaction.status = 'completed' if status == 'COMPLETED' else 'failed'
                transaction.save()
                
                # 関連する予約や会員登録のステータスを更新
                if transaction.reservation:
                    transaction.reservation.status = 'confirmed'
                    transaction.reservation.save()
                
            except PaymentTransaction.DoesNotExist:
                # 新規トランザクションを作成
                PaymentTransaction.objects.create(
                    square_payment_id=payment_id,
                    square_order_id=order_id,
                    amount=int(payment.get('amount_money', {}).get('amount', 0)) / 100,  # セントから円に変換
                    status='completed' if status == 'COMPLETED' else 'failed'
                )
        
        return JsonResponse({'status': 'success'})
    
    except Exception as e:
        print(f"Webhook error: {e}")
        return JsonResponse({'error': str(e)}, status=400)
