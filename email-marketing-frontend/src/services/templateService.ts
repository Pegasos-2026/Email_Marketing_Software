import api from './api';
import { EmailTemplate } from '../types';

export const templateService = {
    async getTemplates(): Promise<{ templates: EmailTemplate[]; categories: Record<string, string> }> {
        const response = await api.get('/campaigns/templates/');
        return {
            templates: response.data.templates || [],
            categories: response.data.categories || {},
        };
    },

    async getTemplate(id: number): Promise<EmailTemplate> {
        const response = await api.get(`/campaigns/templates/${id}/`);
        return response.data;
    },

    async createTemplate(templateData: Partial<EmailTemplate>): Promise<EmailTemplate> {
        const response = await api.post('/campaigns/templates/create/', templateData);
        return response.data;
    },

    async updateTemplate(id: number, templateData: Partial<EmailTemplate>): Promise<EmailTemplate> {
        const response = await api.put(`/campaigns/templates/${id}/update`, templateData);
        return response.data;
    },

    async deleteTemplate(id: number): Promise<void> {
        await api.delete(`/campaigns/templates/${id}/delete`);
    },

    async duplicateTemplate(id: number): Promise<EmailTemplate> {
        const response = await api.post(`/campaigns/templates/${id}/duplicate/`);
        return response.data;
    },

    async previewTemplate(id: number, context?: Record<string, any>): Promise<{ html_content: string }> {
        const response = await api.post(`/campaigns/templates/${id}/preview/`, { context });
        return response.data;
    },

    async getPopularTemplates(limit = 10): Promise<EmailTemplate[]> {
        const response = await api.get(`/campaigns/templates/popular?limit=${limit}`);
        return response.data.templates || [];
    },

    async createDefaultTemplates(): Promise<void> {
        await api.post('/campaigns/template/create-defaults/');
    }
};
