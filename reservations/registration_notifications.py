"""会員登録完了時のメール（会員本人・管理者）。"""
from django.conf import settings
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.template.loader import render_to_string


def registration_notify_recipients():
    """
    管理者向け通知の宛先。
    REGISTRATION_NOTIFY_EMAILS が空でなければその一覧、空なら is_superuser かつメールありのユーザー。
    """
    configured = getattr(settings, 'REGISTRATION_NOTIFY_EMAILS', None) or []
    if configured:
        return list(configured)
    return list(
        User.objects.filter(is_superuser=True, is_active=True)
        .exclude(email__in=('', None))
        .values_list('email', flat=True)
        .distinct()
    )


def send_registration_mails(request, user, profile, *, send_user_mail=True, send_admin_mail=True):
    """
    会員登録完了メールを会員本人と（設定に応じて）管理者へ送る。
    送信失敗時も例外は握りつぶし、登録処理自体は継続できるようにする。
    """
    site_url = request.build_absolute_uri('/')
    ctx = {'user': user, 'profile': profile, 'site_url': site_url}

    if send_user_mail:
        try:
            subject = '会員登録が完了しました'
            html = render_to_string('reservations/emails/registration_complete.html', ctx)
            send_mail(
                subject,
                '',
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                html_message=html,
                fail_silently=False,
            )
        except Exception as e:
            print(f'会員向け登録完了メール送信エラー: {e}')

    if send_admin_mail:
        recipients = registration_notify_recipients()
        if not recipients:
            return
        try:
            subject = '[会員登録] 新規会員が登録されました'
            html = render_to_string('reservations/emails/registration_admin_notice.html', ctx)
            send_mail(
                subject,
                '',
                settings.DEFAULT_FROM_EMAIL,
                recipients,
                html_message=html,
                fail_silently=False,
            )
        except Exception as e:
            print(f'管理者向け会員登録通知メール送信エラー: {e}')
