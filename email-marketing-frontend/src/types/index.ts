export interface CampaignDeliveryFailure {
    email: string;
    error: string;
}

export interface CampaignDeliverySummary {
    total: number;
    sent: number;
    failed: number;
    pending: number;
    failures: CampaignDeliveryFailure[];
}

export interface Campaign {
    id: number;
    name: string;
    subject: string;
    preview_text?: string;
    from_email: string;
    from_name?: string;
    reply_to?: string;
    status: 'draft' | 'scheduled' | 'sending' | 'sent' | 'paused';
    scheduled_at?: string;
    sent_at?: string;
    template?: EmailTemplate;
    content?: CampaignContent;
    delivery_summary?: CampaignDeliverySummary;
    inbox_priority?: boolean;
    created_at: string;
    updated_at: string;
}

export interface CampaignContent {
    id?: number;
    campaign?: number;
    html_content: string;
    plain_text_content?: string;
    created_at?: string;
    updated_at?: string;
}

export interface EmailTemplate {
    id: number;
    name: string;
    subject: string;
    html_content: string;
    plain_text_content?: string;
    category?: string;
    is_active: boolean;
    created_at: string;
    updated_at: string;
}

export interface Contact {
    id: number;
    email: string;
    name?: string;
    first_name?: string;
    last_name?: string;
    phone?: string;
    company?: string;
    is_subscribed?: boolean;
    subscribed?: boolean;
    status?: 'active' | 'inactive' | 'bounced';
    created_at: string;
    updated_at: string;
}

export interface ContactList {
    id: number;
    name: string;
    description?: string;
    contact_count?: number;
    contacts: Contact[];
    created_at: string;
    updated_at: string;
}

export interface User {
    id: number;
    username: string;
    email: string;
    first_name?: string;
    last_name?: string;
}

export interface AuthTokens {
    access: string;
    refresh: string;
}

export interface AuthResponse {
    user: User;
    tokens: AuthTokens;
    message: string;
}

export interface DashboardAnalytics {
    overview: {
        total_campaigns: number;
        sent_campaigns: number;
        draft_campaigns: number;
        scheduled_campaigns: number;
    };
    totals: {
        total_emails_sent: number;
        total_delivered: number;
        total_opens: number;
        total_clicks: number;
        total_opened?: number;
        total_clicked?: number;
        total_failed?: number;
        total_bounced?: number;
        total_unsubscribes?: number;
        total_spam_reports?: number;
        total_pending?: number;
    };
    averages: {
        avg_delivery_rate: number;
        avg_open_rate: number;
        avg_click_rate: number;
    };
    rates?: {
        delivery_rate: number;
        open_rate: number;
        click_through_rate: number;
        bounce_rate: number;
    };
    charts?: {
        funnel?: Array<{ label: string; value: number }>;
        engagement_breakdown?: Array<{ label: string; value: number }>;
        campaign_status?: Array<{ label: string; value: number }>;
    };
    recent_campaigns: Array<{
        id: number;
        name: string;
        subject: string;
        sent_at?: string;
        total_sent: number;
        open_rate: number;
        click_rate: number;
    }>;
    top_performing: Array<{
        id: number;
        name: string;
        open_rate: number;
        click_rate: number;
        total_sent: number;
    }>;
}

export interface CampaignAnalytics {
    campaign: {
        id: number;
        name: string;
        subject: string;
        status: string;
        sent_at?: string;
        created_at: string;
    };
    sending: {
        total_recipients: number;
        total_sent: number;
        total_delivered: number;
        total_failed: number;
        delivery_rate: number;
    };
    engagement: {
        total_opened: number;
        unique_opens: number;
        open_rate: number;
        total_clicked: number;
        unique_clicks: number;
        click_rate: number;
        click_to_open_rate: number;
    };
    negative: {
        total_bounced: number;
        bounce_rate: number;
        total_spam_reports: number;
        total_unsubscribes: number;
    };
    charts?: {
        funnel?: Array<{ label: string; value: number }>;
        engagement_breakdown?: Array<{ label: string; value: number; color?: string }>;
        hourly_opens?: Array<{ label: string; value: number }>;
        rates?: {
            delivery_rate: number;
            open_rate: number;
            click_rate: number;
            bounce_rate: number;
            click_to_open_rate: number;
        };
    };
    recipients?: Array<{
        id: number;
        email: string;
        name: string;
        send_status: string;
        delivery_status: string;
        sent_at?: string | null;
        error_message?: string;
        opened: boolean;
        clicked: boolean;
        bounced: boolean;
        spam_reported: boolean;
        unsubscribed: boolean;
        last_event_at?: string | null;
        last_event_type?: string | null;
    }>;
    device_breakdown?: Array<{ device_type: string; count: number }>;
    last_updated?: string;
    timeline?: Array<{
        event_type: string;
        email: string;
        timestamp: string;
        clicked_url?: string;
        device_type?: string;
    }>;
    top_links?: Array<{
        url: string;
        total_clicks: number;
        unique_clicks: number;
    }>;
}
