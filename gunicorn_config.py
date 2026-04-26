# Gunicorn 設定ファイル（Oracle Cloud / 本番環境用）
bind = "0.0.0.0:5000"
workers = 2
timeout = 120          # yfinance の取得に時間がかかるため長めに設定
worker_class = "sync"
accesslog = "-"
errorlog = "-"
loglevel = "info"
