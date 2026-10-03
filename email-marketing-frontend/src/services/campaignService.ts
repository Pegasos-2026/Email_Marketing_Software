import api from './api';
import { Campaign, CampaignAnalytics, DashboardAnalytics } from '../types';

export const campaignService = {
    async getCampaigns(): Promise<Campaign[]> {
        const response = await api.get('/campaigns/campaigns/');
        return response.data;
    },

    async getCampaign(id: number): Promise<Campaign> {
        const response = await api.get(`/campaigns/campaigns/${id}/`);
        return response.data;
    },

    async createCampaign(campaignData: Partial<Campaign> & { contact_ids?: number[] }): Promise<Campaign> {
        const response = await api.post('/campaigns/campaigns/', campaignData);
        return response.data.data || response.data;
    },

    async updateCampaign(id: number, campaignData: Partial<Campaign>): Promise<Campaign> {
        const response = await api.put(`/campaigns/campaigns/${id}/`, campaignData);
        return response.data.data || response.data;
    },

    async deleteCampaign(id: number): Promise<void> {
        await api.delete(`/campaigns/campaigns/${id}/`);
    },

    async sendCampaign(id: number): Promise<{
        message: string;
        async?: boolean;
        campaign_id?: number;
        result?: {
            total?: number;
            success: number;
            failed: number;
            pending_remaining?: number;
            message?: string;
            deliverability_note?: string;
            sent_emails?: string[];
            failures?: Array<{ email: string; error: string }>;
            warmup?: {
                enabled?: boolean;
                daily_limit?: number;
                sent_today?: number;
                remaining_today?: number;
                deferred?: number;
            };
        };
    }> {
        const response = await api.post(
            `/campaigns/campaigns/${id}/send/`,
            { async: true },
            { timeout: 120000 },
        );
        return response.data;
    },

    async scheduleCampaign(id: number, scheduledAt: string): Promise<void> {
        await api.post(`/campaigns/campaigns/${id}/schedule/`, { scheduled_at: scheduledAt });
    },

    async getDashboardAnalytics(): Promise<DashboardAnalytics> {
        const response = await api.get('/campaigns/analytics/dashboard/');
        return response.data;
    },

    async getCampaignAnalytics(id: number): Promise<CampaignAnalytics> {
        const response = await api.get(`/campaigns/analytics/campaign/${id}/`);
        return response.data;
    },

    async refreshCampaignAnalytics(id: number): Promise<CampaignAnalytics> {
        const response = await api.post(`/campaigns/analytics/campaign/${id}/refresh/`);
        return response.data;
    },

    async createCampaignFromTemplate(data: {
        template_id: number;
        name: string;
        subject?: string;
        from_email: string;
        from_name?: string;
        reply_to?: string;
        scheduled_at?: string;
        contact_list_ids?: number[];
    }): Promise<Campaign> {
        const response = await api.post('/campaigns/campaigns/create-from-template/', data);
        return response.data.campaign || response.data;
    }
};
