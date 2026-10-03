from django.contrib import admin
from django.utils.html import format_html
from .models import Campaign,Contact,CampaignContent,ContactList,CampaignRecipient,CampaignAnalytics,EmailEvent
@admin.register(Campaign)
class CamapignAdmin(admin.ModelAdmin):
    list_display=['name','subject','status','scheduled_at','created_at']
    list_filter=['status','created_at']
    search_fields=['name','subject']
    date_hierarchy='created_at'
@admin.register(CampaignContent)
class CampaignContentAdmin(admin.ModelAdmin):
    list_display=['campaign','created_at']
@admin.register(ContactList)
class ContactListAdmin(admin.ModelAdmin):
    list_display=['name','created_at']
    search_fields=['name']
@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display=['email','name','is_subscribed','created_at']
    list_filter=['is_subscribed','lists']
    search_fields=['email','name']
@admin.register(CampaignRecipient)
class CampaignRecipientAdmin(admin.ModelAdmin):
    list_display=['campaign','contact','status','sent_at']
    list_filter=['status','campaign']
    search_fields=['contact_email']
@admin.register(CampaignAnalytics)
class CampaignAnalyticsAdmin(admin.ModelAdmin):
    list_display=[
        'campaign_name','total_sent','delivery_rate_badge','open_rate_badge','click_rate_badge','performance_score','last_updated',
    ]
    list_filter=['last_updated']
    search_fields=['campaign_name']
    readonly_fields=[
        'campaign','total_recipients','total_sent','total_delivered','total_failed','unique_opens','total_opened','unique_clicks','total_clicked',
        'total_bounced','total_spam_reports','delivery_rate','open_rate','click_rate','click_to_open_rate','bounce_rate',
    ]
    fieldsets=(
        ('Campaign',{
            'fields':(
                'total_recipients','total_sent','total_delivered',
                'total_failed','delivery_rate'
            )
        }),
        ('Engagement Stats',{
            'fields':(
                'unique_opens','total_opened','open_rate',
                'unique_clicks','total_clicked','click_rate',
                'click_to_open_rate'
            )
        }),
        ('Negative Stats',{
            'fields':(
                'total_bounced','bounce_rate',
                'total_spam_reports','total_unsubscribes'
            )
        }),
    )
    def campaign_name(self,obj):
        return obj.campaign.name
    campaign_name.short_description='Campaign'
    def delivery_rate_badge(self,obj):
        return self._rate_badge(obj.delivery_rate,'#198754')
    delivery_rate_badge.short_description='Delivery'
    def open_rate_badge(self,obj):
        return self._rate_badge(obj.open_rate,'#0dcaf0')
    open_rate_badge.short_description='Open Rate'
    def click_rate_badge(self,obj):
        return self._rate_badge(obj.click_rate,'#ffc107')
    click_rate_badge.short_description='Click Rate'
    def _rate_badge(self,rate,color):
        return format_html(
            '<span style="background:{}; color:white;padding:5px 10px;'
            'border-radius:12px;font-weight:bold;display:inline-block;'
            'min-width:60px; text-align:center;">{:.1f}%</span>',
            color,rate
        )
    def performance_score(self,obj):
        """Calculate overall performance score"""
        #weighted score:open_rate *0.5 +click_rate*0.5
        score=(obj.open_rate*0.5)+(obj.click_rate*0.5)
        if score >=25:
            color='#198754'
            label='Excellent'
        elif score >=15:
            color='#0dcaf0'
            label='Good'
        elif score>=8:
            color='#ffc107'
            label='Average'
        else:
            color='#dc3545'
            label='Poor'
        return format_html(
            '<span style="background:{}; color:white;padding:5px 15px;'
            'border-radius:15px; font-weight:bold;">{:.1f}-{}</span>',
            color,score,label
        )
    performance_score.short_description='Score'
    def performance_score(self, obj):
        """Calculate overall performance score"""
        # Weighted score: open_rate * 0.5 + click_rate * 0.5
        score = (obj.open_rate * 0.5) + (obj.click_rate * 0.5)
        
        if score >= 25:
            color = '#198754'
            label = 'Excellent'
        elif score >= 15:
            color = '#0dcaf0'
            label = 'Good'
        elif score >= 8:
            color = '#ffc107'
            label = 'Average'
        else:
            color = '#dc3545'
            label = 'Poor'
        
        return format_html(
            '<span style="background: {}; color: white; padding: 5px 15px; '
            'border-radius: 15px; font-weight: bold;">{:.1f} - {}</span>',
            color, score, label
        )
    performance_score.short_description = 'Score'
    
    def performance_visualization(self, obj):
        """Visual performance chart"""
        html = '<div style="background: #f8f9fa; padding: 20px; border-radius: 10px;">'
        html += '<h3 style="margin-top: 0; color: #333;">📊 Performance Metrics</h3>'
        
        # Create progress bars
        metrics = [
            ('Delivery Rate', obj.delivery_rate, '#198754'),
            ('Open Rate', obj.open_rate, '#0dcaf0'),
            ('Click Rate', obj.click_rate, '#ffc107'),
            ('Click-to-Open Rate', obj.click_to_open_rate, '#6f42c1'),
            ('Bounce Rate', obj.bounce_rate, '#dc3545'),
        ]
        
        for label, value, color in metrics:
            html += self._progress_bar(label, value, color)
        
        # Add summary stats
        html += '<div style="margin-top: 20px; padding: 15px; background: white; border-radius: 8px;">'
        html += '<h4 style="margin-top: 0;">Quick Stats</h4>'
        html += '<div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px;">'
        html += f'<div><strong>Sent:</strong> {obj.total_sent}</div>'
        html += f'<div><strong>Opened:</strong> {obj.unique_opens}</div>'
        html += f'<div><strong>Clicked:</strong> {obj.unique_clicks}</div>'
        html += '</div>'
        html += '</div>'
        
        html += '</div>'
        return format_html(html)
    performance_visualization.short_description = 'Performance Dashboard'
    
    def _progress_bar(self, label, value, color):
        return (
            f'<div style="margin: 15px 0;">'
            f'<div style="display: flex; justify-content: space-between; margin-bottom: 5px;">'
            f'<strong style="color: #555;">{label}</strong>'
            f'<span style="font-weight: bold; color: {color};">{value:.1f}%</span>'
            f'</div>'
            f'<div style="width: 100%; background: #e9ecef; border-radius: 10px; '
            f'overflow: hidden; height: 24px; box-shadow: inset 0 1px 3px rgba(0,0,0,0.1);">'
            f'<div style="width: {min(value, 100):.1f}%; background: {color}; height: 100%; '
            f'transition: width 0.5s ease; display: flex; align-items: center; '
            f'justify-content: flex-end; padding-right: 8px; color: white; font-size: 11px; '
            f'font-weight: bold;"></div>'
            f'</div>'
            f'</div>'
        )


@admin.register(EmailEvent)
class EmailEventAdmin(admin.ModelAdmin):
    list_display = [
        'event_icon',
        'event_type',
        'contact_email',
        'campaign_name',
        'device_badge',
        'timestamp_display',
    ]
    
    list_filter = [
        'event_type',
        'device_type',
        'timestamp',
    ]
    
    search_fields = [
        'campaign_recipient__contact__email',
        'campaign_recipient__campaign__name',
    ]
    
    readonly_fields = [
        'campaign_recipient', 'event_type', 'clicked_url',
        'user_agent', 'ip_address', 'device_type',
        'event_data', 'timestamp',
    ]
    
    date_hierarchy = 'timestamp'
    
    def event_icon(self, obj):
        icons = {
            'sent': '📤',
            'delivered': '✅',
            'opened': '👁️',
            'clicked': '🖱️',
            'bounced': '⚠️',
            'spam': '🚫',
            'unsubscribed': '❌',
            'failed': '❌',
        }
        icon = icons.get(obj.event_type, '📧')
        return format_html(
            '<span style="font-size: 24px;" title="{}">{}</span>',
            obj.event_type, icon
        )
    event_icon.short_description = ''
    
    def contact_email(self, obj):
        return obj.campaign_recipient.contact.email
    contact_email.short_description = 'Contact'
    
    def campaign_name(self, obj):
        return obj.campaign_recipient.campaign.name
    campaign_name.short_description = 'Campaign'
    
    def device_badge(self, obj):
        if not obj.device_type:
            return format_html('<span style="color: #999;">N/A</span>')
        
        icons = {
            'mobile': '📱',
            'desktop': '🖥️',
            'tablet': '📲',
        }
        
        icon = icons.get(obj.device_type, '📧')
        return format_html(
            '<span style="background: #e7f3ff; padding: 3px 8px; border-radius: 10px; '
            'font-size: 11px;">{} {}</span>',
            icon, obj.device_type.capitalize()
        )
    device_badge.short_description = 'Device'
    
    def timestamp_display(self, obj):
        return obj.timestamp.strftime('%b %d, %I:%M %p')
    timestamp_display.short_description = 'Time'
    timestamp_display.admin_order_field = 'timestamp'
    
    def has_add_permission(self, request):
        return False # Events are created automatically
    
    def has_change_permission(self, request, obj=None):
        return False # Events are read-only
