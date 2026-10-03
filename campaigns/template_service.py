from campaigns.models import EmailTemplate
import os
from django.conf import settings
from django.db.models import Q
class TemplateService:
    """Service for managing email templates"""
    def __init__(self,user):
        self.user=user
    def get_available_templates(self,category=None):
        """Get templates available to user
        (own templates + public templates)"""
        templates=EmailTemplate.objects.filter(
            Q(user=self.user) | Q(is_public=True),
            is_active=True
        )
        if category:
            templates=templates.filter(category=category)
        return templates.order_by('-created_at')
    def get_template(self,template_id):
        """Get specific template"""
        return EmailTemplate.objects.get(
            Q(user=self.user) | Q(is_public=True),
            id=template_id,
            is_active=True
        )
    def create_template(self,data):
        """Create new template"""
        template=EmailTemplate.objects.create(
            user=self.user,
            name=data['name'],
            category=data.get('category','newsletter'),
            description=data.get('description',''),
            subject=data['subject'],
            preview_text=data.get('preview_text',''),
            html_content=data['html_content'],
            plain_text_content=data.get('plain_text_content',''),
            available_variables=data.get('available_variables',['name','email']),
            is_public=False #user template are private by default
        )
        return template
    def update_template(self,template_id,data):
        """Update existing template"""
        template=EmailTemplate.objects.get(user=self.user, #only own templates 
                                           id=template_id)
        for field,value in data.items():
            if hasattr(template,field):
                setattr(template,field,value)
        template.save()
        return template
    def delete_template(self,template_id):
        """Delete template(soft delete-mark inactive)"""
        template=EmailTemplate.objects.get(
            user=self.user,
            id=template_id
        )
        template.is_active=False
        template.save()
        return True
    def duplicate_template(self,template_id):
        """Duplicate existing template"""
        original=self.get_template(template_id)
        duplicate=EmailTemplate.objects.create(
            user=self.user,
            name=f"{original.name} (Copy)",
            category=original.category,
            description=original.description,
            subject=original.subject,
            preview_text=original.preview_text,
            html_content=original.html_content,
            plain_text_content=original.plain_text_content,
            available_variables=original.available_variables,
            is_public=False
        )
        return duplicate
    def render_template(self,template_id,context):
        """Render template with context
        Args:
           template_id:Template ID
           context:Dict with variable value {'name':'John','email':john@example.com}
           Returns:Dict with rendered subject and content"""
        template=self.get_template(template_id)
        #render subject
        rendered_subject=template.subject
        for key,value in context.items():
            rendered_subject=rendered_subject.replace(f"{{{{{key}}}}}",str(value))
        #Render html content
        rendered_html=template.html_content
        for key,value in context.items():
            rendered_html=rendered_html.replace(f"{{{{{key}}}}}",str(value))
        #Render plain text
        rendered_plain=template.plain_text_content or ''
        for key,value in context.items():
            rendered_plain=rendered_plain.replace(f"{{{{{key}}}}}",str(value))
        return {
            'subject':rendered_subject,
            'html_content':rendered_html,
            'plain_text_content':rendered_plain
        }
    def get_popular_templates(self,limit=10):
        """Get most used templates"""
        return EmailTemplate.objects.filter(
            Q(user=self.user) | Q(is_public=True),
            is_active=True
        ).order_by('-usage_count')[:limit]
    def get_categories(self):
        """Get Available template categories"""
        return EmailTemplate.CATEGORY_CHOICES
class DefaultTemplateService:
    """Service for creating default/starter templates"""
    #Templates files path define
    TEMPLATE_DIR=os.path.join(settings.BASE_DIR,'app','campaigns','email_templates')
    @staticmethod
    def load_html_file(filename):
        """READ HTML FILE"""
        try:
            file_path=os.path.join(DefaultTemplateService.TEMPLATE_DIR,filename)
            with open(file_path,'r',encoding='utf-8') as file:
                return file.read()
        except FileNotFoundError:
            print(f"Template file not found:{filename}")
            return None 
    @staticmethod
    def create_default_template(user):
        templates=[
            {
                'name':'Promotional Sale',
                'category':'promotional',
                'description':'Eye-catching promotional template',
                'subject':'Special offer just for You!',
                'preview_text':'Limited time discount-Don\'t miss out!',
                'html_content':DefaultTemplateService.load_html_file('promotional.html'),
                'plain_text_content':'Hi {{name}}! Special offer:50% OFF with code SAVE50',
                'available_variables':['name','email','unsubscribe_url']
            },
            {
                'name':'Welcome Email',
                'category':'welcome',
                'description':'Friendly welcome message for new subscribers',
                'subject':'Welcome to Our Community!',
                'preview_text':'We\'re excited to have you here',
                'html_content':DefaultTemplateService.load_html_file('welcome.html'),
                'plain_text_content':'Welcome {{name}}! We\'re excited to have you.',
                'available_variables':['name','email','unsubscribe_url']
            },
            {
                'name':'Event',
                'category':'event',
                'description':'new event taking place in mumbai',
                'subject':'Be the next one to become the part of our event',
                'preview_text':'we are excited to see you as the member of our community',
                'html_content':DefaultTemplateService.load_html_file('event.html'),
                'plain_text_content':'Hi {{name}} , please do registration',
                'available_variables':['name','email','unsusbcribe_url']
            },
            {
                'name':'Announcement',
                'category':'announcement',
                'description':'Important Announcemnet',
                'subject':'Big News!Here whats new',
                'preview_text':'We are excited to share an important update with you.Take a look inside',
                'html_content':DefaultTemplateService.load_html_file('announcement.html'),
                'plain_text_content':'We have an important announcement to share with you.',
                'available_variables':['name','email','unsubscribe_url']
            }
        ]
        created_templates=[]
        for template_data in templates:
            if template_data['html_content'] is None:
                print(f"Skipping template:{template_data['name']}- HTML file not found")
                continue
            template=EmailTemplate.objects.create(user=user,
                                                  **template_data)
            created_templates.append(template)
        return created_templates