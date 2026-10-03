from celery import shared_task
from .scheduler import run_all_schedulers

@shared_task(name='run_all_schedulers')
def run_all_schedulers_task():
    run_all_schedulers()