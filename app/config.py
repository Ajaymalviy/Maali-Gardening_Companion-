
# config.py
class Config:
    CELERY_BROKER_URL = 'redis://localhost:6380/0'
    CELERY_RESULT_BACKEND = 'redis://localhost:6380/0'

    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = 'ajeymalviya143@gmail.com'
    MAIL_PASSWORD = 'mcia proh orkd uvpd'  # Use an app password if using Gmail


GOOGLE_CLIENT_ID = '745426787344-1o3tnk39j9s84vtif2gbn8v277e0ks6r.apps.googleusercontent.com'
GOOGLE_CLIENT_SECRET = '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'
GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"

