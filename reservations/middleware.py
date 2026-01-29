from django.shortcuts import redirect
from django.contrib import messages
from django.urls import resolve

class SuperuserRequiredMiddleware:
    """スーパーユーザーのみアクセス可能なURLを制限するミドルウェア"""
    
    # スーパーユーザーのみアクセス可能なURLパターン
    ADMIN_URL_PATTERNS = [
        'reservations:reservation_list',
        'reservations:admin_dashboard',
        'reservations:location_management',
        'reservations:location_add',
        'reservations:location_edit',
        'reservations:location_delete',
        'reservations:time_slot_management',
        'reservations:time_slot_add',
        'reservations:time_slot_edit',
        'reservations:time_slot_delete',
    ]
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # リクエスト処理前のチェック
        if request.user.is_authenticated:
            try:
                # URL名を取得
                resolver_match = resolve(request.path)
                url_name = resolver_match.url_name
                
                # アプリ名を含む完全なURL名を作成
                if resolver_match.app_name:
                    full_url_name = f"{resolver_match.app_name}:{url_name}"
                else:
                    full_url_name = url_name
                
                # 管理URLパターンに一致する場合
                if full_url_name in self.ADMIN_URL_PATTERNS:
                    if not request.user.is_superuser:
                        messages.error(request, 'このページにアクセスする権限がありません。')
                        return redirect('reservations:index')
            except Exception:
                # URL解決に失敗した場合はスキップ
                pass
        
        response = self.get_response(request)
        return response

