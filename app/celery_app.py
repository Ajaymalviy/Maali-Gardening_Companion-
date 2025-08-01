from celery import Celery
from app.config import Config

celery = Celery(__name__)
celery.conf.broker_url = Config.CELERY_BROKER_URL
celery.conf.result_backend = Config.CELERY_RESULT_BACKEND

# 👇 This line ensures Celery knows your tasks
celery.autodiscover_tasks(['app'])
