from django.core.management.base import BaseCommand
from django.utils import timezone
from reservations.models import Location, TimeSlot, Reservation
from datetime import time, date, timedelta

class Command(BaseCommand):
    help = 'サンプルデータを作成します'

    def handle(self, *args, **options):
        self.stdout.write('サンプルデータを作成中...')

        # 場所の作成
        locations = [
            {
                'name': '会議室A',
                'description': '最大10名まで利用可能な会議室です。プロジェクターとホワイトボードが完備されています。',
                'capacity': 10
            },
            {
                'name': '会議室B',
                'description': '最大6名まで利用可能な会議室です。静かで集中できる環境です。',
                'capacity': 6
            },
            {
                'name': 'セミナールーム',
                'description': '最大20名まで利用可能なセミナールームです。音響設備が完備されています。',
                'capacity': 20
            },
            {
                'name': '個別相談室',
                'description': '1-2名用の個別相談室です。プライバシーが保たれた環境です。',
                'capacity': 2
            }
        ]

        for location_data in locations:
            location, created = Location.objects.get_or_create(
                name=location_data['name'],
                defaults=location_data
            )
            if created:
                self.stdout.write(f'場所を作成: {location.name}')
            else:
                self.stdout.write(f'場所は既に存在: {location.name}')

        # 時間枠の作成
        time_slots = [
            {'start_time': time(9, 0), 'end_time': time(10, 0)},
            {'start_time': time(10, 0), 'end_time': time(11, 0)},
            {'start_time': time(11, 0), 'end_time': time(12, 0)},
            {'start_time': time(13, 0), 'end_time': time(14, 0)},
            {'start_time': time(14, 0), 'end_time': time(15, 0)},
            {'start_time': time(15, 0), 'end_time': time(16, 0)},
            {'start_time': time(16, 0), 'end_time': time(17, 0)},
            {'start_time': time(17, 0), 'end_time': time(18, 0)},
        ]

        for time_slot_data in time_slots:
            time_slot, created = TimeSlot.objects.get_or_create(
                start_time=time_slot_data['start_time'],
                end_time=time_slot_data['end_time']
            )
            if created:
                self.stdout.write(f'時間枠を作成: {time_slot.start_time} - {time_slot.end_time}')
            else:
                self.stdout.write(f'時間枠は既に存在: {time_slot.start_time} - {time_slot.end_time}')

        # サンプル予約の作成
        sample_reservations = [
            {
                'customer_name': '田中太郎',
                'customer_email': 'tanaka@example.com',
                'customer_phone': '090-1234-5678',
                'location_name': '会議室A',
                'time_slot_start': time(10, 0),
                'date': date.today() + timedelta(days=1),
                'status': 'confirmed'
            },
            {
                'customer_name': '佐藤花子',
                'customer_email': 'sato@example.com',
                'customer_phone': '090-8765-4321',
                'location_name': '個別相談室',
                'time_slot_start': time(14, 0),
                'date': date.today() + timedelta(days=2),
                'status': 'pending'
            },
            {
                'customer_name': '鈴木一郎',
                'customer_email': 'suzuki@example.com',
                'customer_phone': '090-1111-2222',
                'location_name': 'セミナールーム',
                'time_slot_start': time(9, 0),
                'date': date.today() + timedelta(days=3),
                'status': 'confirmed'
            }
        ]

        for reservation_data in sample_reservations:
            try:
                location = Location.objects.get(name=reservation_data['location_name'])
                time_slot = TimeSlot.objects.get(start_time=reservation_data['time_slot_start'])
                
                reservation, created = Reservation.objects.get_or_create(
                    location=location,
                    time_slot=time_slot,
                    date=reservation_data['date'],
                    defaults={
                        'customer_name': reservation_data['customer_name'],
                        'customer_email': reservation_data['customer_email'],
                        'customer_phone': reservation_data['customer_phone'],
                        'status': reservation_data['status']
                    }
                )
                
                if created:
                    self.stdout.write(f'予約を作成: {reservation.customer_name} - {reservation.location.name} - {reservation.date}')
                else:
                    self.stdout.write(f'予約は既に存在: {reservation.customer_name} - {reservation.location.name} - {reservation.date}')
                    
            except (Location.DoesNotExist, TimeSlot.DoesNotExist) as e:
                self.stdout.write(self.style.ERROR(f'エラー: {e}'))

        self.stdout.write(self.style.SUCCESS('サンプルデータの作成が完了しました！'))
