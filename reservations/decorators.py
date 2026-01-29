from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.urls import reverse

def superuser_required(view_func):
    """スーパーユーザーのみアクセス可能なデコレータ"""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, 'ログインが必要です。')
            return redirect('reservations:custom_login')
        if not request.user.is_superuser:
            messages.error(request, 'このページにアクセスする権限がありません。')
            return redirect('reservations:index')
        return view_func(request, *args, **kwargs)
    return _wrapped_view







