#!/usr/bin/env python
"""
Background scheduler for email marketing automation tasks.

Usage:
    python run_scheduler.py [check_interval_minutes]
"""
import os
import sys
import time
from datetime import timedelta

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from django.core.management import call_command
from django.utils import timezone


def log_message(message, level='INFO'):
    timestamp = timezone.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f'[{timestamp}] [{level}] {message}')


def run_scheduler(check_interval=5):
    log_message(f'Starting scheduler (check every {check_interval} minutes)')
    log_message('Press Ctrl+C to stop')
    cycle = 0
    try:
        while True:
            cycle += 1
            log_message(f'--- Cycle {cycle}: running scheduled tasks ---')
            try:
                call_command('send_scheduled_campaigns', verbosity=1)
            except Exception as exc:
                log_message(f'Cycle {cycle} error: {exc}', 'ERROR')
            next_run = timezone.now() + timedelta(minutes=check_interval)
            log_message(
                f'Cycle {cycle} complete. Sleeping {check_interval} min '
                f'(next run at {next_run.strftime("%H:%M:%S")})'
            )
            time.sleep(check_interval * 60)
    except KeyboardInterrupt:
        log_message('Scheduler stopped', 'INFO')
        sys.exit(0)


if __name__ == '__main__':
    interval = 5
    if len(sys.argv) > 1:
        try:
            interval = int(sys.argv[1])
        except ValueError:
            log_message(f'Invalid interval: {sys.argv[1]}. Using 5 minutes.', 'WARNING')
    run_scheduler(interval)
