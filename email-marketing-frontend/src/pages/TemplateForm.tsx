import React, { useEffect, useState } from 'react';
import { useHistory, useParams } from 'react-router-dom';
import { templateService } from '../services/templateService';
import { getApiErrorMessage } from '../utils/apiError';
import '../styles/templates.css';

const templateCategories = [
    'newsletter',
    'promotional',
    'event',
    'welcome',
    'announcement',
];

const TemplateForm: React.FC = () => {
    const { templateId } = useParams<{ templateId?: string }>();
    const history = useHistory();
    const isEditing = Boolean(templateId);
    const [templateData, setTemplateData] = useState({
        name: '',
        subject: '',
        category: 'newsletter',
        html_content: '',
        plain_text_content: '',
        is_active: true,
    });
    const [loading, setLoading] = useState(isEditing);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState('');
    const [success, setSuccess] = useState('');

    useEffect(() => {
        if (!isEditing) {
            return;
        }

        const loadTemplate = async () => {
            setLoading(true);
            try {
                const template = await templateService.getTemplate(Number(templateId));
                setTemplateData({
                    name: template.name || '',
                    subject: template.subject || '',
                    category: template.category || 'newsletter',
                    html_content: template.html_content || '',
                    plain_text_content: template.plain_text_content || '',
                    is_active: template.is_active ?? true,
                });
            } catch (err: any) {
                setError(getApiErrorMessage(err, 'Failed to load template'));
            } finally {
                setLoading(false);
            }
        };

        loadTemplate();
    }, [isEditing, templateId]);

    const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
        const target = e.target as HTMLInputElement;
        const { name, value, type } = target;
        const checked = target.type === 'checkbox' ? target.checked : undefined;

        setTemplateData((prev) => ({
            ...prev,
            [name]: type === 'checkbox' ? checked : value,
        }));
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');
        setSuccess('');
        setSaving(true);

        try {
            if (isEditing) {
                await templateService.updateTemplate(Number(templateId), templateData);
                setSuccess('Template updated successfully.');
            } else {
                await templateService.createTemplate(templateData);
                setSuccess('Template created successfully.');
            }
            history.push('/templates');
        } catch (err: any) {
            setError(getApiErrorMessage(err, 'Failed to save template'));
        } finally {
            setSaving(false);
        }
    };

    if (loading) {
        return <div className="loading">Loading template...</div>;
    }

    return (
        <div className="template-form-page">
            <h1>{isEditing ? 'Edit Template' : 'Create Template'}</h1>

            {error && <div className="error-message">{error}</div>}
            {success && <div className="success-message">{success}</div>}

            <form onSubmit={handleSubmit} className="template-form">
                <div className="form-group">
                    <label htmlFor="name">Template Name *</label>
                    <input
                        type="text"
                        id="name"
                        name="name"
                        value={templateData.name}
                        onChange={handleChange}
                        required
                        placeholder="Template name"
                    />
                </div>

                <div className="form-row">
                    <div className="form-group">
                        <label htmlFor="subject">Subject *</label>
                        <input
                            type="text"
                            id="subject"
                            name="subject"
                            value={templateData.subject}
                            onChange={handleChange}
                            required
                            placeholder="Email subject"
                        />
                    </div>
                    <div className="form-group">
                        <label htmlFor="category">Category</label>
                        <select id="category" name="category" value={templateData.category} onChange={handleChange}>
                            {templateCategories.map((category) => (
                                <option key={category} value={category}>
                                    {category.charAt(0).toUpperCase() + category.slice(1)}
                                </option>
                            ))}
                        </select>
                    </div>
                </div>

                <div className="form-group">
                    <label htmlFor="html_content">HTML Content *</label>
                    <textarea
                        id="html_content"
                        name="html_content"
                        value={templateData.html_content}
                        onChange={handleChange}
                        required
                        rows={12}
                        placeholder="HTML body content"
                    />
                </div>

                <div className="form-group">
                    <label htmlFor="plain_text_content">Plain Text Content</label>
                    <textarea
                        id="plain_text_content"
                        name="plain_text_content"
                        value={templateData.plain_text_content}
                        onChange={handleChange}
                        rows={8}
                        placeholder="Plain text body content"
                    />
                </div>

                <div className="form-actions">
                    <button type="submit" className="btn-primary" disabled={saving}>
                        {saving ? 'Saving...' : isEditing ? 'Update Template' : 'Create Template'}
                    </button>
                    <button
                        type="button"
                        className="btn-secondary"
                        onClick={() => history.push('/templates')}
                    >
                        Cancel
                    </button>
                </div>
            </form>
        </div>
    );
};

export default TemplateForm;
