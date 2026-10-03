import React, { useEffect, useState, useCallback, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import { dripService } from '../services/dripService';
import { contactService } from '../services/contactService';
import '../styles/drip.css';

const TRIGGER_LABELS: Record<string, string> = {
    manual: 'Manual enrollment',
    contact_added: 'Contact added',
    tag_added: 'Tag added',
    webhook: 'Webhook event',
};

const DripDetail: React.FC = () => {
    const { id } = useParams<{ id: string }>();
    const [campaign, setCampaign] = useState<any | null>(null);
    const [contacts, setContacts] = useState<any[]>([]);
    const [lists, setLists] = useState<any[]>([]);
    const [selectedContactId, setSelectedContactId] = useState('');
    const [selectedListId, setSelectedListId] = useState('');
    const [emailInput, setEmailInput] = useState('');
    const [newListName, setNewListName] = useState('');
    const [importListId, setImportListId] = useState('');
    const [importFile, setImportFile] = useState<File | null>(null);
    const [enrolling, setEnrolling] = useState(false);
    const [message, setMessage] = useState('');
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(true);
    const fileInputRef = useRef<HTMLInputElement>(null);

    const loadCampaign = useCallback(async () => {
        if (!id) return;
        setLoading(true);
        try {
            const data = await dripService.getDripCampaign(Number(id));
            setCampaign(data);
        } catch (err) {
            console.error(err);
            setError('Failed to load campaign');
        } finally {
            setLoading(false);
        }
    }, [id]);

    const refreshContactsAndLists = useCallback(async () => {
        try {
            const [contactData, listData] = await Promise.all([
                contactService.getContacts(),
                contactService.getContactLists(),
            ]);
            setContacts(contactData);
            setLists(listData);
        } catch {
            // non-blocking
        }
    }, []);

    useEffect(() => {
        loadCampaign();
        refreshContactsAndLists();
    }, [loadCampaign, refreshContactsAndLists]);

    const handleActivate = async () => {
        setError('');
        setMessage('');
        try {
            const result = await dripService.activate(Number(id));
            setMessage(
                `${result.message}${result.enrolled_count ? ` (${result.enrolled_count} contacts enrolled)` : ''}`
            );
            await loadCampaign();
        } catch (err: any) {
            setError(err?.response?.data?.error || 'Failed to activate campaign');
        }
    };

    const handlePause = async () => {
        setError('');
        setMessage('');
        try {
            const result = await dripService.pause(Number(id));
            setMessage(result.message);
            await loadCampaign();
        } catch (err: any) {
            setError(err?.response?.data?.error || 'Failed to pause campaign');
        }
    };

    const handleEnrollByEmail = async () => {
        const email = emailInput.trim().toLowerCase();
        if (!email) {
            setError('Enter an email address.');
            return;
        }
        setEnrolling(true);
        setError('');
        setMessage('');
        try {
            const result = await dripService.enrollContacts(Number(id), { email });
            setMessage(result.message || `${email} enrolled successfully.`);
            setEmailInput('');
            await Promise.all([loadCampaign(), refreshContactsAndLists()]);
        } catch (err: any) {
            setError(err?.response?.data?.error || err?.response?.data?.email?.[0] || 'Failed to enroll contact');
        } finally {
            setEnrolling(false);
        }
    };

    const handleEnrollContact = async () => {
        if (!selectedContactId) return;
        setEnrolling(true);
        setError('');
        setMessage('');
        try {
            const result = await dripService.enrollContacts(Number(id), {
                contact_id: Number(selectedContactId),
            });
            setMessage(result.message);
            await loadCampaign();
        } catch (err: any) {
            setError(err?.response?.data?.error || 'Failed to enroll contact');
        } finally {
            setEnrolling(false);
        }
    };

    const handleEnrollList = async () => {
        if (!selectedListId) return;
        setEnrolling(true);
        setError('');
        setMessage('');
        try {
            const result = await dripService.enrollContacts(Number(id), {
                list_id: Number(selectedListId),
            });
            setMessage(result.message);
            await loadCampaign();
        } catch (err: any) {
            setError(err?.response?.data?.error || 'Failed to enroll list');
        } finally {
            setEnrolling(false);
        }
    };

    const handleImportAndEnroll = async () => {
        if (!importFile) {
            setError('Choose a CSV file to import.');
            return;
        }
        setEnrolling(true);
        setError('');
        setMessage('');
        try {
            let targetListId = importListId ? Number(importListId) : undefined;

            if (newListName.trim()) {
                const created = await contactService.createContactList({
                    name: newListName.trim(),
                    description: `Imported for drip campaign ${campaign?.name || ''}`.trim(),
                });
                targetListId = created.id;
                setImportListId(String(created.id));
            }

            const importResult = await contactService.importContacts(importFile, targetListId);
            const summary = importResult.summary || importResult;
            const importedIds: number[] = summary.contact_ids || [];

            let enrollMessage = '';
            if (targetListId) {
                const enrollResult = await dripService.enrollContacts(Number(id), {
                    list_id: targetListId,
                });
                enrollMessage = enrollResult.message;
            } else if (importedIds.length > 0) {
                const enrollResult = await dripService.enrollContacts(Number(id), {
                    contact_ids: importedIds,
                });
                enrollMessage = enrollResult.message;
            }

            setMessage(
                `Imported ${summary.created ?? 0} new, ${summary.updated ?? 0} updated contact(s). ${enrollMessage}`
            );
            setImportFile(null);
            setNewListName('');
            if (fileInputRef.current) {
                fileInputRef.current.value = '';
            }
            await Promise.all([loadCampaign(), refreshContactsAndLists()]);
        } catch (err: any) {
            setError(err?.response?.data?.error || 'Failed to import and enroll contacts');
        } finally {
            setEnrolling(false);
        }
    };

    if (loading) return <div>Loading…</div>;
    if (!campaign) return <div>{error || 'Campaign not found'}</div>;

    const stepCount = campaign.total_steps ?? (campaign.steps || []).length;

    return (
        <div className="drip-detail">
            <div className="drip-detail-header">
                <div>
                    <h1>{campaign.name}</h1>
                    <p className="drip-meta">
                        Status: <strong>{campaign.status}</strong>
                        {' · '}
                        Trigger: <strong>{TRIGGER_LABELS[campaign.trigger_type] || campaign.trigger_type}</strong>
                        {campaign.trigger_tag_name && (
                            <> · Tag: <strong>{campaign.trigger_tag_name}</strong></>
                        )}
                        {campaign.trigger_webhook_event && (
                            <> · Event: <strong>{campaign.trigger_webhook_event}</strong></>
                        )}
                        {' · '}
                        Steps: <strong>{stepCount}</strong>
                        {' · '}
                        Enrolled: <strong>{campaign.total_enrollments ?? 0}</strong>
                    </p>
                </div>
                <div className="drip-actions">
                    <Link to={`/drip/${campaign.id}/builder`} className="btn-primary">Open Builder</Link>
                    {campaign.status === 'draft' || campaign.status === 'paused' ? (
                        <button type="button" className="btn-secondary" onClick={handleActivate}>
                            Activate
                        </button>
                    ) : null}
                    {campaign.status === 'active' ? (
                        <button type="button" className="btn-secondary" onClick={handlePause}>
                            Pause
                        </button>
                    ) : null}
                </div>
            </div>

            {message && <div className="success-message">{message}</div>}
            {error && <div className="error-message">{error}</div>}

            {campaign.description && <p>{campaign.description}</p>}

            {stepCount === 0 && (
                <div className="error-message">
                    This campaign has no steps yet. Open the Builder, click &quot;Add Step&quot;, fill in the email, then Save.
                </div>
            )}

            {campaign.status === 'active' && (
                <div className="timeline-card campaign-settings">
                    <h2 className="section-heading">Enroll contacts</h2>
                    <div className="timeline-card-body">
                        <label>Add single contact by email</label>
                        <div className="enroll-row">
                            <input
                                type="email"
                                placeholder="e.g. john@example.com"
                                value={emailInput}
                                onChange={(e) => setEmailInput(e.target.value)}
                            />
                            <button
                                type="button"
                                className="btn-secondary"
                                onClick={handleEnrollByEmail}
                                disabled={enrolling}
                            >
                                Add &amp; Enroll
                            </button>
                        </div>
                        <p className="form-hint">Creates the contact if it does not exist, then enrolls them in this drip.</p>

                        <label>Or pick an existing contact</label>
                        <div className="enroll-row">
                            <select value={selectedContactId} onChange={(e) => setSelectedContactId(e.target.value)}>
                                <option value="">Select contact…</option>
                                {contacts.map((c) => (
                                    <option key={c.id} value={c.id}>{c.email}</option>
                                ))}
                            </select>
                            <button
                                type="button"
                                className="btn-secondary"
                                onClick={handleEnrollContact}
                                disabled={enrolling}
                            >
                                Enroll
                            </button>
                        </div>

                        <hr className="enroll-divider" />

                        <label>Import multiple contacts (CSV)</label>
                        <p className="form-hint">
                            CSV must include an <strong>email</strong> column. Optional: name, is_subscribed.
                        </p>
                        <input
                            ref={fileInputRef}
                            type="file"
                            accept=".csv,text/csv"
                            onChange={(e) => setImportFile(e.target.files?.[0] || null)}
                        />
                        <label>Save imported contacts to list (optional)</label>
                        <select value={importListId} onChange={(e) => setImportListId(e.target.value)}>
                            <option value="">No list — enroll imported contacts only</option>
                            {lists.map((l) => (
                                <option key={l.id} value={l.id}>{l.name}</option>
                            ))}
                        </select>
                        <label>Or create a new list</label>
                        <input
                            type="text"
                            placeholder="New list name"
                            value={newListName}
                            onChange={(e) => setNewListName(e.target.value)}
                        />
                        <div className="enroll-row">
                            <button
                                type="button"
                                className="btn-primary"
                                onClick={handleImportAndEnroll}
                                disabled={enrolling || !importFile}
                            >
                                {enrolling ? 'Importing…' : 'Import & Enroll'}
                            </button>
                        </div>

                        <label>Or enroll an existing list</label>
                        <div className="enroll-row">
                            <select value={selectedListId} onChange={(e) => setSelectedListId(e.target.value)}>
                                <option value="">Select list…</option>
                                {lists.map((l) => (
                                    <option key={l.id} value={l.id}>{l.name} ({l.contact_count ?? 0})</option>
                                ))}
                            </select>
                            <button
                                type="button"
                                className="btn-secondary"
                                onClick={handleEnrollList}
                                disabled={enrolling}
                            >
                                Enroll list
                            </button>
                        </div>
                    </div>
                </div>
            )}

            <h3>Email steps</h3>
            <div className="steps-list">
                {(campaign.steps || []).length === 0 ? (
                    <p className="form-hint">No steps configured.</p>
                ) : (
                    (campaign.steps || []).map((s: any, i: number) => (
                        <div key={s.id || i} className="step-card">
                            <div className="step-meta">
                                Step {i + 1} · Delay: {s.delay_days || 0} day(s), {s.delay_hours || 0} hour(s)
                            </div>
                            <div className="step-subject">{s.subject}</div>
                            <div className="step-content" dangerouslySetInnerHTML={{ __html: s.html_content || '' }} />
                        </div>
                    ))
                )}
            </div>
        </div>
    );
};

export default DripDetail;
