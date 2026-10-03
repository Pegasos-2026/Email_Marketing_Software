import React, { useEffect, useMemo, useState } from 'react';
import { Link, useHistory, useParams } from 'react-router-dom';
import { campaignService } from '../services/campaignService';
import { Campaign } from '../types';
import { useToast } from '../context/ToastContext';
import { buildCampaignPreviewHtml } from '../utils/emailPlainText';
import PageShell from '../components/ui/PageShell';
import '../styles/campaigns.css';

const CampaignDetail: React.FC = () => {
    const { campaignId } = useParams<{ campaignId: string }>();
    const history = useHistory();
    const id = Number(campaignId);
    const { showToast } = useToast();
    const [campaign, setCampaign] = useState<Campaign | null>(null);
    const [loading, setLoading] = useState(true);
    const [retryLoading, setRetryLoading] = useState(false);
    const [error, setError] = useState('');

    const loadCampaign = async () => {
        try {
            const data = await campaignService.getCampaign(id);
            setCampaign(data);
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Unable to load campaign details');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadCampaign();
    }, [id]);

    useEffect(() => {
        if (campaign?.status !== 'sending') {
            return undefined;
        }
        const timer = window.setInterval(() => {
            loadCampaign();
        }, 5000);
        return () => window.clearInterval(timer);
    }, [campaign?.status, id]);

    const handleRetrySend = async () => {
        setRetryLoading(true);
        try {
            const result = await campaignService.sendCampaign(id);
            showToast(result.message || 'Sending continued in the background.', 'success');
            await loadCampaign();
            history.push(`/campaigns/${id}/analytics`);
        } catch (err: any) {
            showToast(err.response?.data?.error || 'Failed to send campaign', 'error');
        } finally {
            setRetryLoading(false);
        }
    };

    const deliverySummary = campaign?.delivery_summary;
    const pendingCount = deliverySummary?.pending ?? 0;
    const failedCount = deliverySummary?.failed ?? 0;
    const sentCount = deliverySummary?.sent ?? 0;

    const showAnalyticsAction = campaign?.status === 'sent' || campaign?.status === 'sending';
    const canEdit = campaign?.status === 'draft' || campaign?.status === 'scheduled';
    const canContinueSending =
        campaign?.status === 'sending' && (pendingCount > 0 || failedCount > 0);
    const canRetrySend =
        (campaign?.status === 'draft' || campaign?.status === 'sent') &&
        failedCount > 0 &&
        sentCount === 0;
    const deliveryFailures = deliverySummary?.failures ?? [];
    const hasNetworkFailures = deliveryFailures.some((failure) =>
        /getaddrinfo|urlopen error|10051|11001|network|timeout/i.test(failure.error || ''),
    );

    const previewDocument = useMemo(() => {
        if (!campaign?.content) {
            return { html: '', mode: 'standard' as const };
        }
        return buildCampaignPreviewHtml(
            campaign.content.html_content || '',
            campaign.content.plain_text_content || '',
            campaign.inbox_priority !== false,
            campaign.from_name,
        );
    }, [campaign]);

    if (loading) {
        return <div className="loading-spinner">Loading campaign details…</div>;
    }

    if (!campaign) {
        return (
            <PageShell title="Campaign details">
                <div className="alert alert-error">{error || 'Campaign not found'}</div>
            </PageShell>
        );
    }

    return (
        <PageShell
            title={campaign.name}
            subtitle={`${campaign.subject} · ${campaign.status}`}
            actions={
                <div className="page-actions">
                    {canEdit && (
                        <Link to={`/campaigns/${id}/edit`} className="btn-secondary btn-small">
                            Edit
                        </Link>
                    )}
                    {showAnalyticsAction && (
                        <Link to={`/campaigns/${id}/analytics`} className="btn-primary btn-small">
                            View analytics
                        </Link>
                    )}
                    {canContinueSending && (
                        <button
                            type="button"
                            className="btn-primary btn-small"
                            onClick={handleRetrySend}
                            disabled={retryLoading}
                        >
                            {retryLoading ? 'Sending…' : 'Continue sending'}
                        </button>
                    )}
                    {canRetrySend && (
                        <button
                            type="button"
                            className="btn-secondary btn-small"
                            onClick={handleRetrySend}
                            disabled={retryLoading}
                        >
                            {retryLoading ? 'Retrying…' : 'Retry send'}
                        </button>
                    )}
                </div>
            }
        >
            <section className="card-panel">
                <div className="campaign-detail-grid">
                    <div className="campaign-detail-field">
                        <strong>Status</strong>
                        <span>{campaign.status}</span>
                    </div>
                    <div className="campaign-detail-field">
                        <strong>Delivery</strong>
                        <span>
                            {sentCount} sent · {pendingCount} pending · {failedCount} failed
                        </span>
                    </div>
                    <div className="campaign-detail-field">
                        <strong>Created</strong>
                        <span>{new Date(campaign.created_at).toLocaleString()}</span>
                    </div>
                    {campaign.scheduled_at && (
                        <div className="campaign-detail-field">
                            <strong>Scheduled</strong>
                            <span>{new Date(campaign.scheduled_at).toLocaleString()}</span>
                        </div>
                    )}
                    {campaign.sent_at && (
                        <div className="campaign-detail-field">
                            <strong>Sent</strong>
                            <span>{new Date(campaign.sent_at).toLocaleString()}</span>
                        </div>
                    )}
                    <div className="campaign-detail-field">
                        <strong>From</strong>
                        <span>{campaign.from_name ? `${campaign.from_name} <${campaign.from_email}>` : campaign.from_email}</span>
                    </div>
                    <div className="campaign-detail-field">
                        <strong>Reply-to</strong>
                        <span>{campaign.reply_to || campaign.from_email || 'Not specified'}</span>
                    </div>
                    <div className="campaign-detail-field">
                        <strong>Preview text</strong>
                        <span>{campaign.preview_text || 'None'}</span>
                    </div>
                </div>
            </section>

            {campaign.status === 'sending' && (pendingCount > 0 || failedCount > 0) && (
                <section className="card-panel">
                    <div className="alert alert-error">
                        Sending is in progress or was interrupted. {pendingCount} recipient(s) still
                        pending
                        {failedCount > 0 ? ` and ${failedCount} failed` : ''}. Click{' '}
                        <strong>Continue sending</strong> once your internet connection is stable —
                        do not create a duplicate campaign.
                    </div>
                </section>
            )}

            {deliveryFailures.length > 0 && (
                <section className="card-panel">
                    <h2 className="section-heading">Delivery failures</h2>
                    <div className="alert alert-error">
                        {hasNetworkFailures
                            ? 'Some emails failed due to a temporary network/DNS issue on this PC (not invalid email addresses). Check your internet connection, then click Continue sending to retry failed and pending recipients.'
                            : 'This campaign did not reach all recipients. Check Settings → Email, then click Continue sending to retry.'}
                    </div>
                    <ul className="delivery-failure-list">
                        {deliveryFailures.map((failure) => (
                            <li key={failure.email}>
                                <strong>{failure.email}</strong>: {failure.error}
                            </li>
                        ))}
                    </ul>
                </section>
            )}

            {campaign.content?.plain_text_content && (
                <section className="card-panel">
                    <h2 className="section-heading">Plain text content</h2>
                    <div className="campaign-content-preview">
                        <pre>{campaign.content.plain_text_content}</pre>
                    </div>
                </section>
            )}

            {campaign.content?.html_content && (
                <section className="card-panel">
                    <h2 className="section-heading">Email preview</h2>
                    <div className="preview-iframe-wrap">
                        <iframe
                            title="Campaign email preview"
                            srcDoc={previewDocument.html}
                            className="preview-iframe preview-iframe--auto"
                            sandbox="allow-popups allow-popups-to-escape-sandbox"
                        />
                    </div>
                </section>
            )}
        </PageShell>
    );
};

export default CampaignDetail;
