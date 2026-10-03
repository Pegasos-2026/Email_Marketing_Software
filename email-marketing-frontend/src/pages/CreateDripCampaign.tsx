import React, { useState } from 'react';
import { useHistory } from 'react-router-dom';
import { dripService } from '../services/dripService';
import '../styles/drip.css';

const TRIGGER_OPTIONS = [
    {
        value: 'manual',
        label: 'Manual enrollment',
        help: 'You enroll contacts yourself from the campaign detail page.',
    },
    {
        value: 'contact_added',
        label: 'Contact added',
        help: 'Starts automatically when a new contact is created or imported.',
    },
    {
        value: 'tag_added',
        label: 'Tag added',
        help: 'Starts when a specific tag is applied to a contact.',
    },
    {
        value: 'webhook',
        label: 'Webhook event',
        help: 'Starts when an external system sends a matching webhook event.',
    },
] as const;

const CAMPAIGN_TYPES = [
    'Lead Nurturing',
    'Customer Onboarding',
    'Follow-up',
    'Re-engagement',
    'Promotional',
];

const CreateDripCampaign: React.FC = () => {
    const [form, setForm] = useState({
        name: '',
        description: '',
        campaign_type: 'Lead Nurturing',
        trigger_type: 'manual',
        trigger_tag_name: '',
        trigger_webhook_event: '',
        status: 'draft',
    });
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const history = useHistory();

    const selectedTrigger = TRIGGER_OPTIONS.find((t) => t.value === form.trigger_type);

    const handleChange = (
        e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>
    ) => {
        const { name, value } = e.target;
        setForm((f) => ({ ...f, [name]: value }));
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');
        setLoading(true);
        try {
            const descriptionParts = [
                form.campaign_type ? `[${form.campaign_type}]` : '',
                form.description.trim(),
            ].filter(Boolean);

            const payload: Record<string, unknown> = {
                name: form.name.trim(),
                description: descriptionParts.join(' ').trim() || null,
                status: form.status || 'draft',
                trigger_type: form.trigger_type,
                steps: [],
            };

            if (form.trigger_type === 'tag_added') {
                payload.trigger_tag_name = form.trigger_tag_name.trim();
            }
            if (form.trigger_type === 'webhook') {
                payload.trigger_webhook_event = form.trigger_webhook_event.trim().toLowerCase();
            }

            const data = await dripService.createDripCampaign(payload);
            history.push(`/drip/${data.id}/builder`);
        } catch (err: any) {
            const resp = err?.response?.data;
            if (resp) {
                if (typeof resp === 'string') {
                    setError(resp);
                } else if (typeof resp === 'object') {
                    const parts: string[] = [];
                    for (const [k, v] of Object.entries(resp)) {
                        if (Array.isArray(v)) parts.push(`${k}: ${v[0]}`);
                        else if (typeof v === 'object') parts.push(`${k}: ${JSON.stringify(v)}`);
                        else parts.push(`${k}: ${v}`);
                    }
                    setError(parts.join(' | '));
                } else {
                    setError(err.message || 'Failed to create drip campaign');
                }
            } else {
                setError(err.message || 'Failed to create drip campaign');
            }
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="drip-create-page">
            <h1>Create Drip Campaign</h1>
            {error && <div className="error-message">{error}</div>}
            <form onSubmit={handleSubmit} className="drip-form">
                <div className="form-group">
                    <label>Name *</label>
                    <input
                        name="name"
                        value={form.name}
                        onChange={handleChange}
                        required
                        placeholder="e.g. Welcome Series"
                    />
                </div>
                <div className="form-group">
                    <label>Description</label>
                    <textarea
                        name="description"
                        value={form.description}
                        onChange={handleChange}
                        placeholder="What is this drip campaign for?"
                    />
                </div>
                <div className="form-group">
                    <label>Campaign Type</label>
                    <select name="campaign_type" value={form.campaign_type} onChange={handleChange}>
                        {CAMPAIGN_TYPES.map((type) => (
                            <option key={type} value={type}>{type}</option>
                        ))}
                    </select>
                </div>
                <div className="form-group">
                    <label>Trigger *</label>
                    <select
                        name="trigger_type"
                        value={form.trigger_type}
                        onChange={handleChange}
                        required
                    >
                        {TRIGGER_OPTIONS.map((option) => (
                            <option key={option.value} value={option.value}>
                                {option.label}
                            </option>
                        ))}
                    </select>
                    {selectedTrigger && (
                        <p className="form-hint">{selectedTrigger.help}</p>
                    )}
                </div>
                {form.trigger_type === 'tag_added' && (
                    <div className="form-group">
                        <label>Trigger tag *</label>
                        <input
                            name="trigger_tag_name"
                            value={form.trigger_tag_name}
                            onChange={handleChange}
                            required
                            placeholder="e.g. newsletter-subscriber"
                        />
                    </div>
                )}
                {form.trigger_type === 'webhook' && (
                    <div className="form-group">
                        <label>Webhook event name *</label>
                        <input
                            name="trigger_webhook_event"
                            value={form.trigger_webhook_event}
                            onChange={handleChange}
                            required
                            placeholder="e.g. user_signed_up"
                        />
                    </div>
                )}
                <div className="form-actions">
                    <button className="btn-primary" type="submit" disabled={loading}>
                        {loading ? 'Creating…' : 'Create & Open Builder'}
                    </button>
                </div>
            </form>
        </div>
    );
};

export default CreateDripCampaign;
