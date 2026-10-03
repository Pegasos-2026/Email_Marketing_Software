import api from './api';

export const dripService = {
    async getDripCampaigns() {
        const response = await api.get('/campaigns/drip/campaigns/');
        return response.data;
    },

    async getDripCampaign(id: number) {
        const response = await api.get(`/campaigns/drip/campaigns/${id}/`);
        return response.data;
    },

    async createDripCampaign(data: any) {
        const response = await api.post('/campaigns/drip/campaigns/', data);
        return response.data;
    },

    async updateDripCampaign(id: number, data: any) {
        const response = await api.put(`/campaigns/drip/campaigns/${id}/`, data);
        return response.data;
    },

    async deleteDripCampaign(id: number) {
        const response = await api.delete(`/campaigns/drip/campaigns/${id}/`);
        return response.data;
    },

    async activate(id: number) {
        const response = await api.post(`/campaigns/drip/campaigns/${id}/activate/`);
        return response.data;
    },

    async pause(id: number) {
        const response = await api.post(`/campaigns/drip/campaigns/${id}/pause/`);
        return response.data;
    },

    async getAnalytics(id: number) {
        const response = await api.get(`/campaigns/drip/campaigns/${id}/analytics/`);
        return response.data;
    },

    async getEnrollments(id: number, status?: string) {
        const url = status
            ? `/campaigns/drip/campaigns/${id}/enrollments/?status=${status}`
            : `/campaigns/drip/campaigns/${id}/enrollments/`;
        const response = await api.get(url);
        return response.data;
    },

    async enrollContacts(id: number, payload: {
        contact_id?: number;
        contact_ids?: number[];
        list_id?: number;
        email?: string;
        emails?: string[];
    }) {
        const response = await api.post(`/campaigns/drip/campaigns/${id}/enroll/`, payload);
        return response.data;
    },
};

export default dripService;
