from campaigns.models import EmailTemplate
from campaigns.template_loader import load_html_template
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
            availablr_variables=original.available_variables,
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
    @staticmethod
    def create_default_template(user):
        templates=[
            {
                'name':'Promotional',
                'category':'promotional',
                'html_file':'promotiona.html'
            },
            {
                'name':'Welcome Email',
                'category':'welcome',
                'html_file':'welcome.html'
            }
        ]
        created=[]
        for t in templates:
            html_content=load_html_template(t.pop('html_file'))
            template=EmailTemplate.objects.create(user=user,
                                                  html_content=html_content**t)
            created.append(template)
        return created