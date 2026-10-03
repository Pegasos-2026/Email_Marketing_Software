import api from './api';
import { Contact, ContactList } from '../types';

export const contactService = {
    async getContacts(): Promise<Contact[]> {
        const response = await api.get('/campaigns/contacts/');
        return response.data;
    },

    async getContact(id: number): Promise<Contact> {
        const response = await api.get(`/campaigns/contacts/${id}/`);
        return response.data;
    },

    async createContact(contactData: Partial<Contact>): Promise<Contact> {
        const response = await api.post('/campaigns/contacts/create/', contactData);
        return response.data.contact || response.data;
    },

    async updateContact(id: number, contactData: Partial<Contact>): Promise<Contact> {
        const response = await api.put(`/campaigns/contacts/${id}/`, contactData);
        return response.data;
    },

    async deleteContact(id: number): Promise<void> {
        await api.delete(`/campaigns/contacts/${id}/`);
    },

    async getContactLists(): Promise<ContactList[]> {
        const response = await api.get('/campaigns/contact-lists/');
        return response.data;
    },

    async getContactList(id: number): Promise<ContactList> {
        const response = await api.get(`/campaigns/contact-lists/${id}/`);
        return response.data;
    },

    async createContactList(listData: Partial<ContactList>): Promise<ContactList> {
        const response = await api.post('/campaigns/contact-lists/', listData);
        return response.data.list || response.data;
    },

    async updateContactList(id: number, listData: Partial<ContactList>): Promise<ContactList> {
        const response = await api.put(`/campaigns/contact-lists/${id}/`, listData);
        return response.data;
    },

    async deleteContactList(id: number): Promise<void> {
        await api.delete(`/campaigns/contact-lists/${id}/`);
    },

    async previewImport(file: File): Promise<any> {
        const formData = new FormData();
        formData.append('file', file);
        const response = await api.post('/campaigns/contacts/import/preview/', formData, {
            headers: { 'Content-Type': 'multipart/form-data' },
        });
        return response.data;
    },

    async importContacts(file: File, listId?: number): Promise<any> {
        const formData = new FormData();
        formData.append('file', file);
        if (listId) {
            formData.append('list_id', listId.toString());
        }

        const response = await api.post('/campaigns/contacts/import/', formData, {
            headers: { 'Content-Type': 'multipart/form-data' },
        });
        return response.data;
    },

    async exportContacts(listId?: number): Promise<Blob> {
        const url = listId ? `/campaigns/contacts/export/?list_id=${listId}` : '/campaigns/contacts/export/';
        const response = await api.get(url, {
            responseType: 'blob',
        });
        return response.data;
    },

    async sendBulkEmail(params: {
        contact_ids?: number[];
        list_id?: number;
        subject: string;
        html_content: string;
        plain_text_content?: string;
    }): Promise<any> {
        const response = await api.post('/campaigns/bulk-send/', params);
        return response.data;
    }
};
