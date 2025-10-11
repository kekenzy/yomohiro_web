# Gunicorn設定ファイル

# サーバーソケット
bind = "127.0.0.1:8000"

# ワーカープロセス数（推奨: CPU数 x 2 + 1）
workers = 2

# ワーカークラス
worker_class = "sync"

# タイムアウト
timeout = 120

# アクセスログ
accesslog = "/home/ubuntu/yomohiro_web/logs/gunicorn_access.log"
errorlog = "/home/ubuntu/yomohiro_web/logs/gunicorn_error.log"

# ログレベル
loglevel = "info"

# プロセス名
proc_name = "yomohiro_reservation"

# デーモン化（systemdで管理する場合はFalse）
daemon = False

