import os
from django.conf import settings
def load_html_template(filename):
    """Load HTML email template from file system"""
    path=os.path.join(settings.BASE_DIR,
                      'campaigns',
                      'email_templates',filename)
    if not os.path.exists(path):
        raise FileNotFoundError(f"Template file not found: {filename}")
    with open(path,'r',encoding='utf-8') as f:
        return f.read()