import api from './api';

export interface SendEmailData {
    subject: string;
    html_content: string;
    to_email?: string;
}

export interface EmailSettingsData {
    provider: string;
    api_key?: string;
    smtp_host?: string;
    smtp_port?: number;
    smtp_user?: string;
    smtp_password?: string;
    from_name?: string;
    from_email?: string;
    sending_domain?: string;
    domain_verified?: boolean;
    smtp_password_configured?: boolean;
    api_key_configured?: boolean;
    site_url?: string;
    site_url_public?: boolean;
}

export interface DomainVerificationData {
    domain: string;
    dns_records: Array<{
        type: string;
        name: string;
        value: string;
    }>;
}

export const emailService = {
    async sendEmail(data: SendEmailData): Promise<{ message: string }> {
        const response = await api.post('/emails/send-email/', data);
        return response.data;
    },

    async getSettings(): Promise<EmailSettingsData> {
        const response = await api.get('/emails/settings/');
        return response.data;
    },

    async updateSettings(data: EmailSettingsData): Promise<EmailSettingsData> {
        const response = await api.put('/emails/settings/', data);
        return response.data;
    },

    async verifyDomain(): Promise<DomainVerificationData> {
        const response = await api.post('/emails/verify-domain/');
        return response.data;
    },

    async checkDomainStatus(): Promise<{ domain_verified: boolean; domain?: string; message: string }> {
        const response = await api.post('/emails/check-domain-status/');
        return response.data;
    },
};
