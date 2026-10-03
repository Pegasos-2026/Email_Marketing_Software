import React, { useEffect, useState } from 'react';
import { useParams, useHistory } from 'react-router-dom';
import { dripService } from '../services/dripService';
import '../styles/drip.css';

const TRIGGER_OPTIONS = [
    { value: 'manual', label: 'Manual enrollment' },
    { value: 'contact_added', label: 'Contact added' },
    { value: 'tag_added', label: 'Tag added' },
    { value: 'webhook', label: 'Webhook event' },
];

const stepKey = (step: any, index: number) => step.id ?? step.uid ?? `step-${index}`;

const DripBuilder: React.FC = () => {
    const { id } = useParams<{ id: string }>();
    const [campaign, setCampaign] = useState<any | null>(null);
    const [loading, setLoading] = useState(false);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState('');
    const history = useHistory();

    useEffect(() => {
        const fetchCampaign = async () => {
            setLoading(true);
            setError('');
            try {
                const data = await dripService.getDripCampaign(Number(id));
                setCampaign({
                    ...data,
                    trigger_type: data.trigger_type || 'manual',
                    trigger_tag_name: data.trigger_tag_name || '',
                    trigger_webhook_event: data.trigger_webhook_event || '',
                    steps: (data.steps || []).map((s: any) => ({
                        ...s,
                        uid: s.id ?? Date.now() + Math.random(),
                    })),
                });
            } catch (err: any) {
                setError(err?.response?.data?.detail || 'Failed to load campaign');
            } finally {
                setLoading(false);
            }
        };

        if (id) fetchCampaign();
    }, [id]);

    const updateCampaign = (patch: Record<string, unknown>) => {
        setCampaign((c: any) => ({ ...c, ...patch }));
    };

    const addStep = () => {
        setCampaign((c: any) => {
            const steps = c?.steps ? [...c.steps] : [];
            const newStep = {
                uid: Date.now(),
                step_number: steps.length + 1,
                action: 'send_email',
                subject: 'New step',
                from_email: 'noreply@example.com',
                from_name: '',
                reply_to: '',
                html_content: '<p>Hello</p>',
                plain_text_content: '',
                delay_hours: 0,
                delay_days: 0,
            };
            return { ...c, steps: [...steps, newStep] };
        });
    };

    const parseApiError = (err: any, fallback: string) => {
        const resp = err?.response?.data;
        if (typeof resp === 'string') return resp;
        if (resp?.error) return resp.error;
        if (resp && typeof resp === 'object') {
            const parts = Object.entries(resp).map(([k, v]) =>
                Array.isArray(v) ? `${v[0]}` : String(v)
            );
            return parts.join(' | ');
        }
        return fallback;
    };

    const ensurePausedForEdit = async (): Promise<boolean> => {
        if (!campaign) return false;
        if (campaign.status === 'archived') {
            setError('Archived campaigns cannot be edited.');
            return false;
        }
        if (campaign.status !== 'active') return true;
        try {
            await dripService.pause(Number(id));
            setCampaign((c: any) => ({ ...c, status: 'paused' }));
            return true;
        } catch (err: any) {
            setError(parseApiError(err, 'Failed to pause campaign for editing.'));
            return false;
        }
    };

    const handlePauseToEdit = async () => {
        setError('');
        if (campaign?.status !== 'active') return;
        await ensurePausedForEdit();
    };

    const saveAndActivate = async () => {
        const wasActive = campaign?.status === 'active';
        const saved = await save(false, wasActive);
        if (!saved) return;
        try {
            await dripService.activate(Number(id));
            history.push(`/drip/${id}`);
        } catch (err: any) {
            setError(parseApiError(err, 'Saved, but activation failed. Open the campaign detail page to activate.'));
        }
    };

    const save = async (redirect = true, reactivateAfterSave = false): Promise<boolean> => {
        if (!campaign) return false;
        setSaving(true);
        setError('');

        const canEdit = await ensurePausedForEdit();
        if (!canEdit) {
            setSaving(false);
            return false;
        }

        if (campaign.trigger_type === 'tag_added' && !campaign.trigger_tag_name?.trim()) {
            setError('Enter a tag name for the Tag Added trigger.');
            setSaving(false);
            return false;
        }
        if (campaign.trigger_type === 'webhook' && !campaign.trigger_webhook_event?.trim()) {
            setError('Enter a webhook event name.');
            setSaving(false);
            return false;
        }

        const steps = (campaign.steps || []).map((s: any, idx: number) => ({
            step_number: idx + 1,
            action: s.action || 'send_email',
            subject: s.subject || '',
            from_email: s.from_email || 'noreply@example.com',
            from_name: s.from_name || '',
            reply_to: s.reply_to || '',
            html_content: s.html_content || '',
            plain_text_content: s.plain_text_content || '',
            delay_hours: s.delay_hours ?? 0,
            delay_days: s.delay_days ?? 0,
            tag: s.tag,
        }));

        const missing = steps.find(
            (st: any) => st.action === 'send_email' && (!st.subject || !st.from_email)
        );
        if (missing) {
            setError('All email steps require a subject and from email.');
            setSaving(false);
            return false;
        }

        const payload: any = {
            name: campaign.name,
            description: campaign.description,
            status: reactivateAfterSave ? 'paused' : (campaign.status === 'active' ? 'paused' : campaign.status || 'draft'),
            trigger_type: campaign.trigger_type || 'manual',
            list_ids: campaign.list_ids || [],
            tag_ids: campaign.tag_ids || [],
            steps,
        };

        if (campaign.trigger_type === 'webhook') {
            payload.trigger_webhook_event = campaign.trigger_webhook_event.trim().toLowerCase();
        }
        if (campaign.trigger_type === 'tag_added') {
            payload.trigger_tag_name = campaign.trigger_tag_name.trim();
        }

        try {
            const updated = await dripService.updateDripCampaign(Number(id), payload);
            setCampaign((c: any) => ({
                ...c,
                ...updated,
                status: updated.status || 'paused',
                steps: (updated.steps || []).map((s: any) => ({
                    ...s,
                    uid: s.id ?? Date.now() + Math.random(),
                })),
            }));
            if (redirect) {
                history.push(`/drip/${id}`);
            }
            return true;
        } catch (err: any) {
            setError(parseApiError(err, 'Failed to save campaign'));
            return false;
        } finally {
            setSaving(false);
        }
    };

    const removeStep = (index: number) => {
        setCampaign((c: any) => ({
            ...c,
            steps: (c.steps || []).filter((_: any, i: number) => i !== index),
        }));
    };

    const moveStep = (index: number, delta: number) => {
        setCampaign((c: any) => {
            const steps = [...(c.steps || [])];
            const newIndex = index + delta;
            if (newIndex < 0 || newIndex >= steps.length) return c;
            const [item] = steps.splice(index, 1);
            steps.splice(newIndex, 0, item);
            return { ...c, steps };
        });
    };

    if (loading) return <div>Loading…</div>;
    if (!campaign) return <div>{error || 'No campaign loaded.'}</div>;

    const isActive = campaign.status === 'active';
    const isArchived = campaign.status === 'archived';

    return (
        <div className="drip-builder">
            <h1>Workflow Builder — {campaign.name}</h1>
            <p className="drip-meta">
                Status: <strong>{campaign.status}</strong>
            </p>
            {isActive && (
                <div className="info-message">
                    This campaign is <strong>active</strong>. Saving will briefly pause it, apply your changes, then you can activate again from the detail page or use Save &amp; Activate.
                    <button type="button" className="btn-secondary info-action" onClick={handlePauseToEdit}>
                        Pause now
                    </button>
                </div>
            )}
            {isArchived && (
                <div className="error-message">Archived campaigns cannot be edited.</div>
            )}
            {error && <div className="error-message">{error}</div>}
            <div className="builder-actions">
                <button type="button" className="btn-primary" onClick={addStep} disabled={isArchived}>Add Step</button>
                <button type="button" className="btn-secondary" onClick={() => save()} disabled={saving || isArchived}>
                    {saving ? 'Saving…' : isActive ? 'Pause & Save' : 'Save Campaign'}
                </button>
                <button type="button" className="btn-secondary" onClick={saveAndActivate} disabled={saving || isArchived}>
                    {isActive ? 'Pause, Save & Activate' : 'Save & Activate'}
                </button>
            </div>

            <div className="timeline-card campaign-settings">
                <h2 className="section-heading">Campaign trigger</h2>
                <div className="timeline-card-body">
                    <label>Trigger type</label>
                    <select
                        value={campaign.trigger_type || 'manual'}
                        onChange={(e) => updateCampaign({ trigger_type: e.target.value })}
                    >
                        {TRIGGER_OPTIONS.map((option) => (
                            <option key={option.value} value={option.value}>{option.label}</option>
                        ))}
                    </select>
                    {campaign.trigger_type === 'tag_added' && (
                        <>
                            <label>Trigger tag *</label>
                            <input
                                value={campaign.trigger_tag_name || ''}
                                onChange={(e) => updateCampaign({ trigger_tag_name: e.target.value })}
                                placeholder="e.g. newsletter-subscriber"
                            />
                        </>
                    )}
                    {campaign.trigger_type === 'webhook' && (
                        <>
                            <label>Webhook event name *</label>
                            <input
                                value={campaign.trigger_webhook_event || ''}
                                onChange={(e) => updateCampaign({ trigger_webhook_event: e.target.value })}
                                placeholder="e.g. user_signed_up"
                            />
                        </>
                    )}
                </div>
            </div>

            <div className="timeline">
                {(campaign.steps || []).length === 0 ? (
                    <p className="form-hint">No steps yet. Click &quot;Add Step&quot; to build your email sequence.</p>
                ) : (
                    (campaign.steps || []).map((step: any, idx: number) => (
                        <div key={stepKey(step, idx)} className="timeline-card">
                            <div className="timeline-card-header">
                                <strong>{step.subject || `Step ${idx + 1}`}</strong>
                                <div className="timeline-actions">
                                    <button type="button" onClick={() => moveStep(idx, -1)}>↑</button>
                                    <button type="button" onClick={() => moveStep(idx, 1)}>↓</button>
                                    <button
                                        type="button"
                                        onClick={() => removeStep(idx)}
                                        className="btn-danger"
                                    >
                                        Delete
                                    </button>
                                </div>
                            </div>
                            <div className="timeline-card-body">
                                <label>Delay (days)</label>
                                <input
                                    type="number"
                                    min={0}
                                    value={step.delay_days ?? 0}
                                    onChange={(e) => {
                                        const val = Number(e.target.value || 0);
                                        setCampaign((c: any) => {
                                            const steps = [...(c.steps || [])];
                                            steps[idx] = { ...steps[idx], delay_days: val };
                                            return { ...c, steps };
                                        });
                                    }}
                                />
                                <label>Delay (hours)</label>
                                <input
                                    type="number"
                                    min={0}
                                    value={step.delay_hours ?? 0}
                                    onChange={(e) => {
                                        const val = Number(e.target.value || 0);
                                        setCampaign((c: any) => {
                                            const steps = [...(c.steps || [])];
                                            steps[idx] = { ...steps[idx], delay_hours: val };
                                            return { ...c, steps };
                                        });
                                    }}
                                />
                                <label>From email</label>
                                <input
                                    value={step.from_email || ''}
                                    onChange={(e) => {
                                        const val = e.target.value;
                                        setCampaign((c: any) => {
                                            const steps = [...(c.steps || [])];
                                            steps[idx] = { ...steps[idx], from_email: val };
                                            return { ...c, steps };
                                        });
                                    }}
                                />
                                <label>Subject</label>
                                <input
                                    value={step.subject || ''}
                                    onChange={(e) => {
                                        const val = e.target.value;
                                        setCampaign((c: any) => {
                                            const steps = [...(c.steps || [])];
                                            steps[idx] = { ...steps[idx], subject: val };
                                            return { ...c, steps };
                                        });
                                    }}
                                />
                                <label>HTML Content</label>
                                <textarea
                                    rows={6}
                                    value={step.html_content || ''}
                                    onChange={(e) => {
                                        const val = e.target.value;
                                        setCampaign((c: any) => {
                                            const steps = [...(c.steps || [])];
                                            steps[idx] = { ...steps[idx], html_content: val };
                                            return { ...c, steps };
                                        });
                                    }}
                                />
                            </div>
                        </div>
                    ))
                )}
            </div>
        </div>
    );
};

export default DripBuilder;
