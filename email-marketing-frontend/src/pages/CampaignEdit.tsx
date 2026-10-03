import React, { useEffect, useState } from 'react';
import { useHistory, useParams } from 'react-router-dom';
import { campaignService } from '../services/campaignService';
import '../styles/campaigns.css';

const CampaignEdit: React.FC = () => {
    const { campaignId } = useParams<{ campaignId: string }>();
    const [formData, setFormData] = useState({
        name: '',
        subject: '',
        preview_text: '',
        from_email: '',
        from_name: '',
        reply_to: '',
        scheduled_at: '',
    });
    const [htmlContent, setHtmlContent] = useState('');
    const [plainText, setPlainText] = useState('');
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState('');
    const [success, setSuccess] = useState('');
    const history = useHistory();

    useEffect(() => {
        const loadCampaign = async () => {
            try {
                const campaign = await campaignService.getCampaign(Number(campaignId));
                setFormData({
                    name: campaign.name || '',
                    subject: campaign.subject || '',
                    preview_text: campaign.preview_text || '',
                    from_email: campaign.from_email || '',
                    from_name: campaign.from_name || '',
                    reply_to: campaign.reply_to || '',
                    scheduled_at: campaign.scheduled_at
                        ? new Date(campaign.scheduled_at).toISOString().slice(0, 16)
                        : '',
                });
                setHtmlContent(campaign.content?.html_content || '');
                setPlainText(campaign.content?.plain_text_content || '');
            } catch (err: any) {
                setError(err.response?.data?.detail || err.response?.data?.error || 'Failed to load campaign');
            } finally {
                setLoading(false);
            }
        };
        loadCampaign();
    }, [campaignId]);

    const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
        const { name: fieldName, value } = e.target;
        setFormData((prev) => ({
            ...prev,
            [fieldName]: value,
        }));
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');
        setSuccess('');
        setSaving(true);
        try {
            await campaignService.updateCampaign(Number(campaignId), {
                ...formData,
                content: {
                    html_content: htmlContent,
                    plain_text_content: plainText,
                },
            });
            setSuccess('Campaign updated successfully.');
            history.push(`/campaigns/${campaignId}`);
        } catch (err: any) {
            setError(err.response?.data?.detail || err.response?.data?.error || 'Failed to update campaign');
        } finally {
            setSaving(false);
        }
    };

    if (loading) {
        return <div className="loading">Loading campaign...</div>;
    }

    return (
        <div className="create-campaign-container">
            <h1>Edit Campaign</h1>

            {error && <div className="error-message">{error}</div>}
            {success && <div className="success-message">{success}</div>}

            <form onSubmit={handleSubmit} className="campaign-form">
                <fieldset>
                    <legend>Campaign Details</legend>

                    <div className="form-group">
                        <label htmlFor="name">Campaign Name *</label>
                        <input
                            id="name"
                            name="name"
                            type="text"
                            value={formData.name}
                            onChange={handleChange}
                            required
                            placeholder="e.g., Spring Newsletter"
                        />
                    </div>

                    <div className="form-row">
                        <div className="form-group">
                            <label htmlFor="subject">Email Subject *</label>
                            <input
                                id="subject"
                                name="subject"
                                type="text"
                                value={formData.subject}
                                onChange={handleChange}
                                required
                                placeholder="e.g., Check out our latest updates"
                            />
                        </div>
                        <div className="form-group">
                            <label htmlFor="preview_text">Preview Text</label>
                            <input
                                id="preview_text"
                                name="preview_text"
                                type="text"
                                value={formData.preview_text}
                                onChange={handleChange}
                                placeholder="Preview text shown in email client"
                            />
                        </div>
                    </div>
                </fieldset>

                <fieldset>
                    <legend>Sender Information</legend>

                    <div className="form-row">
                        <div className="form-group">
                            <label htmlFor="from_email">From Email *</label>
                            <input
                                id="from_email"
                                name="from_email"
                                type="email"
                                value={formData.from_email}
                                onChange={handleChange}
                                required
                                placeholder="sender@example.com"
                            />
                        </div>
                        <div className="form-group">
                            <label htmlFor="from_name">From Name</label>
                            <input
                                id="from_name"
                                name="from_name"
                                type="text"
                                value={formData.from_name}
                                onChange={handleChange}
                                placeholder="Your Company Name"
                            />
                        </div>
                    </div>

                    <div className="form-group">
                        <label htmlFor="reply_to">Reply-To Email</label>
                        <input
                            id="reply_to"
                            name="reply_to"
                            type="email"
                            value={formData.reply_to}
                            onChange={handleChange}
                            placeholder="support@example.com"
                        />
                    </div>
                </fieldset>

                <fieldset>
                    <legend>Schedule</legend>
                    <div className="form-group">
                        <label htmlFor="scheduled_at">Send Date & Time</label>
                        <input
                            id="scheduled_at"
                            name="scheduled_at"
                            type="datetime-local"
                            value={formData.scheduled_at}
                            onChange={handleChange}
                            className="form-input"
                        />
                    </div>
                </fieldset>

                <fieldset>
                    <legend>Email Content</legend>

                    <div className="form-group">
                        <label htmlFor="htmlContent">HTML Content *</label>
                        <textarea
                            id="htmlContent"
                            value={htmlContent}
                            onChange={(e) => setHtmlContent(e.target.value)}
                            required
                            placeholder="<html>...</html>"
                            rows={10}
                        />
                    </div>

                    <div className="form-group">
                        <label htmlFor="plainText">Plain Text Content</label>
                        <textarea
                            id="plainText"
                            value={plainText}
                            onChange={(e) => setPlainText(e.target.value)}
                            placeholder="Plain text version"
                            rows={10}
                        />
                    </div>
                </fieldset>

                <div className="form-actions">
                    <button type="submit" disabled={saving} className="btn-primary">
                        {saving ? 'Saving...' : 'Save Changes'}
                    </button>
                    <button
                        type="button"
                        onClick={() => history.push(`/campaigns/${campaignId}`)}
                        className="btn-secondary"
                    >
                        Cancel
                    </button>
                </div>
            </form>
        </div>
    );
};

export default CampaignEdit;
