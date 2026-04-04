from django.conf import settings


def line_login(request):
    """ログイン画面で LINE ボタン表示可否"""
    return {
        'line_login_enabled': bool(
            getattr(settings, 'LINE_CHANNEL_ID', '') and getattr(settings, 'LINE_CHANNEL_SECRET', '')
        ),
    }
