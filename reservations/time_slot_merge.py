"""予約の時間枠表示用: 終了＝次の開始でつながる枠を1行にまとめる。"""


def merge_consecutive_time_slot_details(time_slot_details):
    """
    time_slot_details: [{'time_slot', 'duration_minutes', 'units_30min', 'amount'}, ...]

    隣接する枠（前枠の終了時刻＝次枠の開始時刻）を1行にまとめ、次を追加する:
      - range_start_time / range_end_time: 表示用の合算レンジ
      - duration_minutes, units_30min, amount は合算
    """
    if not time_slot_details:
        return []

    sorted_details = sorted(
        time_slot_details,
        key=lambda d: d['time_slot'].start_time,
    )
    out = []
    group = [sorted_details[0]]

    for d in sorted_details[1:]:
        prev_end = group[-1]['time_slot'].end_time
        cur_start = d['time_slot'].start_time
        if prev_end == cur_start:
            group.append(d)
        else:
            out.append(_merge_time_slot_detail_group(group))
            group = [d]
    out.append(_merge_time_slot_detail_group(group))
    return out


def _merge_time_slot_detail_group(group):
    first = group[0]['time_slot']
    last = group[-1]['time_slot']
    return {
        'time_slot': first,
        'range_start_time': first.start_time,
        'range_end_time': last.end_time,
        'duration_minutes': sum(x['duration_minutes'] for x in group),
        'units_30min': sum(x['units_30min'] for x in group),
        'amount': sum(x['amount'] for x in group),
    }


def merge_consecutive_time_slots_for_display(time_slots):
    """
    TimeSlot モデルの iterable。隣接枠（前の end_time == 次の start_time）をまとめ、
    テンプレート用に [{'start': time, 'end': time}, ...] を返す。
    """
    slots = list(time_slots)
    if not slots:
        return []
    slots.sort(key=lambda ts: ts.start_time)
    groups = []
    group = [slots[0]]
    for ts in slots[1:]:
        if group[-1].end_time == ts.start_time:
            group.append(ts)
        else:
            groups.append(group)
            group = [ts]
    groups.append(group)
    return [{'start': g[0].start_time, 'end': g[-1].end_time} for g in groups]
