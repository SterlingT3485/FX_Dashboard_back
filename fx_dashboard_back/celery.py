# import os
# from fx_dashboard_back.celery import Celery

# # set Django's default settings module
# os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fx_dashboard_back.settings')

# app = Celery('fx_dashboard_back')

# # read Celery configuration from Django settings
# app.config_from_object('django.conf:settings', namespace='CELERY')

# # automatically discover all tasks.py files in Django applications
# app.autodiscover_tasks()