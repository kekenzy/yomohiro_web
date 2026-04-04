"""入退室管理の共通ロジック"""
import re
import uuid
from datetime import datetime
from decimal import Decimal
from math import ceil

from django.db.models import Q
from django.utils import timezone

from .models import Location, MemberProfile, Reservation, TimeSlot, VisitRecord


def parse_member_qr_payload(raw: str):
    """QR の生文字列から会員 UUID を取り出す。"""
    if not raw:
        return None
    text = raw.strip()
    m = re.search(r'YOMOHIRO_MEMBER:([0-9a-fA-F-]{36})', text)
    if m:
        try:
            return uuid.UUID(m.group(1))
        except ValueError:
            return None
    return None


def get_member_by_qr_token(token_uuid):
    if not token_uuid:
        return None
    return MemberProfile.objects.filter(member_qr_token=token_uuid).select_related('user').first()


def _user_reservation_qs(user, on_date):
    return Reservation.objects.filter(
        date=on_date,
        status__in=['confirmed', 'pending'],
    ).filter(
        Q(customer_email=user.email) | Q(created_by=user)
    ).select_related('location', 'time_slot')


def resolve_time_slot_for_now():
    """現在時刻が含まれる時間枠（なければ最も近い枠）。"""
    now = timezone.localtime()
    t = now.time()
    slots = list(TimeSlot.objects.filter(is_active=True).order_by('start_time'))
    if not slots:
        return None
    for slot in slots:
        if slot.start_time <= t < slot.end_time:
            return slot
    for slot in slots:
        if t < slot.start_time:
            return slot
    return slots[-1]


def resolve_time_slot_for_datetime(dt: datetime):
    """ローカル時刻 dt が含まれる時間枠。"""
    t = timezone.localtime(dt).time()
    slots = list(TimeSlot.objects.filter(is_active=True).order_by('start_time'))
    for slot in slots:
        if slot.start_time <= t < slot.end_time:
            return slot
    return resolve_time_slot_for_now()


def pick_reservation_for_entry(member: MemberProfile, on_date, location_id=None):
    """
    当日の予約から入場に使う1件を選ぶ。
    location_id 指定時はその場所に限定。
    現在時刻が枠内の予約を優先。
    """
    user = member.user
    qs = _user_reservation_qs(user, on_date)
    if location_id:
        qs = qs.filter(location_id=location_id)
    qs = list(qs.order_by('time_slot__start_time'))
    if not qs:
        return None
    now = timezone.localtime()
    t = now.time()
    for r in qs:
        if r.time_slot.start_time <= t < r.time_slot.end_time:
            return r
    return qs[0]


def compute_visit_fee(entry_at: datetime, exit_at: datetime, location: Location) -> Decimal:
    """利用時間に応じた料金（30分単位で切り上げ）。"""
    if not entry_at or not exit_at or exit_at <= entry_at:
        return Decimal('0')
    delta = exit_at - entry_at
    minutes = max(1, int(delta.total_seconds() // 60))
    units = max(1, ceil(minutes / 30))
    price = location.price_per_30min or Decimal('0')
    return Decimal(units) * price


def get_open_visit(member: MemberProfile):
    return VisitRecord.objects.filter(
        member_profile=member,
        exit_at__isnull=True,
    ).order_by('-entry_at').first()
