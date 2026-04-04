"""会員プランなどの共通ヘルパー（views とソーシャル認証アダプタから利用）"""
from .models import Plan


def get_default_regular_member_plan():
    """
    簡易登録などで用いる「通常会員」相当のプラン。
    管理画面で is_default=True のプランを優先し、なければ名前に「通常」を含む有効プラン、
    それもなければ最も安い有効プランを返す。
    """
    plan = Plan.objects.filter(is_default=True, is_active=True).first()
    if plan:
        return plan
    plan = Plan.objects.filter(is_active=True, name__icontains='通常').first()
    if plan:
        return plan
    return Plan.objects.filter(is_active=True).order_by('price').first()
