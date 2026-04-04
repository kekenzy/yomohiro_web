from allauth.socialaccount.adapter import DefaultSocialAccountAdapter

from .member_utils import get_default_regular_member_plan
from .models import MemberProfile


class MemberSocialAccountAdapter(DefaultSocialAccountAdapter):
    """LINE 等のソーシャル初回ログイン時に MemberProfile を作成する。"""

    def save_user(self, request, sociallogin, form=None):
        user = super().save_user(request, sociallogin, form)
        if MemberProfile.objects.filter(user=user).exists():
            return user

        plan = get_default_regular_member_plan()
        data = sociallogin.account.extra_data or {}
        name = (
            data.get('name')
            or data.get('displayName')
            or (user.get_full_name() or '').strip()
            or (user.email or '').split('@')[0]
            or user.username
            or 'LINEユーザー'
        )
        name = str(name)[:100]

        MemberProfile.objects.create(
            user=user,
            full_name=name,
            gender='other',
            phone='',
            postal_code='',
            address='',
            plan=plan,
        )
        return user
