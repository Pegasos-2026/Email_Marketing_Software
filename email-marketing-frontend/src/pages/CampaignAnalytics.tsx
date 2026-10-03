import React, { useCallback, useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';
import { campaignService } from '../services/campaignService';
import { CampaignAnalytics } from '../types';
import { useAnalyticsStream } from '../hooks/useAnalyticsStream';
import { useToast } from '../context/ToastContext';
import PageShell from '../components/ui/PageShell';
import StatCard from '../components/ui/StatCard';
import BarChart from '../components/ui/BarChart';
import DonutChart from '../components/ui/DonutChart';
import '../styles/analytics.css';

const STATUS_LABELS: Record<string, string> = {
    pending: 'Pending',
    sent: 'Sent',
    delivered: 'Delivered',
    opened: 'Opened',
    clicked: 'Clicked',
    bounced: 'Bounced',
    failed: 'Failed',
    spam: 'Spam',
    unsubscribed: 'Unsubscribed',
};

const CampaignAnalyticsPage: React.FC = () => {
    const { campaignId } = useParams<{ campaignId: string }>();
    const id = Number(campaignId);
    const { showToast } = useToast();

    const fetchAnalytics = useCallback(() => campaignService.getCampaignAnalytics(id), [id]);

    const { data: analytics, loading, live, error, lastUpdated, refresh } =
        useAnalyticsStream<CampaignAnalytics>(
            `/campaigns/analytics/campaign/${id}/stream/`,
            fetchAnalytics,
            [id]
        );

    const [scheduleAt, setScheduleAt] = useState('');
    const [actionLoading, setActionLoading] = useState(false);
    const [statusFilter, setStatusFilter] = useState('all');
    const [recipientSearch, setRecipientSearch] = useState('');

    const charts = analytics?.charts;
    const isSent = analytics?.campaign.status === 'sent' || analytics?.campaign.status === 'sending';

    const funnelData = useMemo(
        () => charts?.funnel?.map((d) => ({ label: d.label, value: d.value })) ?? [],
        [charts]
    );

    const hourlyOpens = useMemo(
        () => charts?.hourly_opens?.map((d) => ({ label: d.label, value: d.value })) ?? [],
        [charts]
    );

    const breakdownSegments = useMemo(
        () =>
            (charts?.engagement_breakdown ?? [])
                .filter((d) => d.value > 0)
                .map((d) => ({
                    label: d.label,
                    value: d.value,
                    color: d.color || 'var(--brand)',
                })),
        [charts]
    );

    const deviceSegments = useMemo(
        () =>
            (analytics?.device_breakdown ?? [])
                .filter((d) => d.count > 0)
                .map((d) => ({
                    label: d.device_type || 'Unknown',
                    value: d.count,
                    color: 'var(--brand)',
                })),
        [analytics?.device_breakdown]
    );

    const filteredRecipients = useMemo(() => {
        const rows = analytics?.recipients ?? [];
        const query = recipientSearch.trim().toLowerCase();
        return rows.filter((row) => {
            const matchesStatus =
                statusFilter === 'all' || row.delivery_status === statusFilter;
            const matchesSearch =
                !query ||
                row.email.toLowerCase().includes(query) ||
                (row.name || '').toLowerCase().includes(query);
            return matchesStatus && matchesSearch;
        });
    }, [analytics?.recipients, recipientSearch, statusFilter]);

    const handleSendNow = async () => {
        setActionLoading(true);
        try {
            await campaignService.sendCampaign(id);
            showToast('Campaign sent. Metrics updating live.', 'success');
            await refresh();
        } catch (err: any) {
            showToast(err.response?.data?.error || 'Failed to send campaign', 'error');
        } finally {
            setActionLoading(false);
        }
    };

    const handleSchedule = async () => {
        if (!scheduleAt) {
            showToast('Select a date and time.', 'error');
            return;
        }
        setActionLoading(true);
        try {
            await campaignService.scheduleCampaign(id, scheduleAt);
            showToast('Campaign scheduled.', 'success');
            await refresh();
        } catch (err: any) {
            showToast(err.response?.data?.error || 'Failed to schedule', 'error');
        } finally {
            setActionLoading(false);
        }
    };

    if (loading && !analytics) {
        return <div className="loading-spinner">Loading analytics…</div>;
    }

    if (!analytics) {
        return (
            <PageShell title="Campaign analytics">
                <div className="alert alert-error">{error || 'No data available'}</div>
            </PageShell>
        );
    }

    return (
        <PageShell
            title={analytics.campaign.name}
            subtitle={`${analytics.campaign.subject} · ${analytics.campaign.status}`}
            live={live}
            lastUpdated={lastUpdated}
            onRefresh={refresh}
        >
            {error && <div className="alert alert-error">{error}</div>}

            {!isSent && (
                <section className="card-panel">
                    <div className="analytics-toolbar">
                        <p className="analytics-toolbar-meta">
                            {analytics.campaign.sent_at
                                ? `Sent ${new Date(analytics.campaign.sent_at).toLocaleString()}`
                                : 'This campaign has not been sent yet.'}
                        </p>
                        <div className="analytics-toolbar-actions">
                            <button
                                type="button"
                                className="btn-primary btn-small"
                                onClick={handleSendNow}
                                disabled={actionLoading}
                            >
                                Send now
                            </button>
                            <input
                                type="datetime-local"
                                value={scheduleAt}
                                onChange={(e) => setScheduleAt(e.target.value)}
                                aria-label="Schedule date"
                            />
                            <button
                                type="button"
                                className="btn-secondary btn-small"
                                onClick={handleSchedule}
                                disabled={actionLoading}
                            >
                                Schedule
                            </button>
                        </div>
                    </div>
                </section>
            )}

            {isSent && (
                <section className="card-panel">
                    <p className="analytics-toolbar-meta">
                        Sent{' '}
                        {analytics.campaign.sent_at
                            ? new Date(analytics.campaign.sent_at).toLocaleString()
                            : '—'}
                        {' · '}
                        {live
                            ? 'Live updates — metrics refresh automatically as recipients interact with your email.'
                            : 'Polling every 5 seconds — connect with a public SITE_URL for instant SSE updates.'}
                    </p>
                </section>
            )}

            <section className="card-panel">
                <h2 className="section-heading">Key metrics</h2>
                <div className="metrics-grid-ui">
                    <StatCard label="Total sent" value={analytics.sending.total_sent} tone="brand" />
                    <StatCard
                        label="Delivered"
                        value={analytics.sending.total_delivered}
                        hint={`${analytics.sending.delivery_rate.toFixed(1)}% delivery rate`}
                        tone="success"
                    />
                    <StatCard label="Failed / undelivered" value={analytics.sending.total_failed} tone="danger" />
                    <StatCard
                        label="Open rate"
                        value={`${analytics.engagement.open_rate.toFixed(1)}%`}
                        hint={`${analytics.engagement.unique_opens} unique opens`}
                    />
                    <StatCard
                        label="Click rate (CTR)"
                        value={`${analytics.engagement.click_rate.toFixed(1)}%`}
                        hint={`${analytics.engagement.unique_clicks} unique clicks`}
                    />
                    <StatCard
                        label="Click-to-open"
                        value={`${analytics.engagement.click_to_open_rate.toFixed(1)}%`}
                        hint={`${analytics.engagement.total_clicked} total clicks`}
                    />
                    <StatCard
                        label="Bounced"
                        value={analytics.negative.total_bounced}
                        hint={`${analytics.negative.bounce_rate.toFixed(1)}% bounce rate`}
                        tone="warning"
                    />
                    <StatCard label="Spam reports" value={analytics.negative.total_spam_reports} tone="danger" />
                    <StatCard label="Unsubscribes" value={analytics.negative.total_unsubscribes} />
                </div>
            </section>

            <div className="charts-row">
                <section className="card-panel">
                    <h2 className="section-heading">Campaign funnel</h2>
                    {funnelData.length > 0 ? (
                        <BarChart data={funnelData} />
                    ) : (
                        <p className="text-muted">Send the campaign to see funnel data.</p>
                    )}
                </section>
                <section className="card-panel">
                    <h2 className="section-heading">Engagement breakdown</h2>
                    {breakdownSegments.length > 0 ? (
                        <DonutChart segments={breakdownSegments} />
                    ) : (
                        <p className="text-muted">No engagement events recorded yet.</p>
                    )}
                </section>
            </div>

            {(hourlyOpens.length > 0 || deviceSegments.length > 0) && (
                <div className="charts-row">
                    {hourlyOpens.length > 0 && (
                        <section className="card-panel">
                            <h2 className="section-heading">Opens over time</h2>
                            <BarChart data={hourlyOpens} />
                        </section>
                    )}
                    {deviceSegments.length > 0 && (
                        <section className="card-panel">
                            <h2 className="section-heading">Opens by device</h2>
                            <DonutChart segments={deviceSegments} />
                        </section>
                    )}
                </div>
            )}

            {analytics.top_links && analytics.top_links.length > 0 && (
                <section className="card-panel">
                    <h2 className="section-heading">Top clicked links</h2>
                    <ul className="analytics-links">
                        {analytics.top_links.map((link) => (
                            <li key={link.url}>
                                <span className="link-url">{link.url}</span>
                                <span>
                                    {link.unique_clicks} unique · {link.total_clicks} total
                                </span>
                            </li>
                        ))}
                    </ul>
                </section>
            )}

            {analytics.recipients && analytics.recipients.length > 0 && (
                <section className="card-panel">
                    <div className="recipient-table-header">
                        <h2 className="section-heading">Recipient delivery status</h2>
                        <div className="recipient-table-filters">
                            <input
                                type="search"
                                placeholder="Search email or name…"
                                value={recipientSearch}
                                onChange={(e) => setRecipientSearch(e.target.value)}
                                aria-label="Search recipients"
                            />
                            <select
                                value={statusFilter}
                                onChange={(e) => setStatusFilter(e.target.value)}
                                aria-label="Filter by status"
                            >
                                <option value="all">All statuses</option>
                                {Object.entries(STATUS_LABELS).map(([value, label]) => (
                                    <option key={value} value={value}>
                                        {label}
                                    </option>
                                ))}
                            </select>
                        </div>
                    </div>
                    <div className="recipient-table-wrap">
                        <table className="recipient-table">
                            <thead>
                                <tr>
                                    <th>Recipient</th>
                                    <th>Status</th>
                                    <th>Sent at</th>
                                    <th>Last activity</th>
                                    <th>Engagement</th>
                                </tr>
                            </thead>
                            <tbody>
                                {filteredRecipients.map((row) => (
                                    <tr key={row.id}>
                                        <td>
                                            <span className="recipient-email">{row.email}</span>
                                            {row.name && (
                                                <span className="recipient-name">{row.name}</span>
                                            )}
                                            {row.error_message && (
                                                <span className="recipient-error">{row.error_message}</span>
                                            )}
                                        </td>
                                        <td>
                                            <span
                                                className={`delivery-badge delivery-badge--${row.delivery_status}`}
                                            >
                                                {STATUS_LABELS[row.delivery_status] || row.delivery_status}
                                            </span>
                                        </td>
                                        <td>
                                            {row.sent_at
                                                ? new Date(row.sent_at).toLocaleString()
                                                : '—'}
                                        </td>
                                        <td>
                                            {row.last_event_at ? (
                                                <>
                                                    <span className={`event-pill event-pill--${row.last_event_type}`}>
                                                        {row.last_event_type}
                                                    </span>
                                                    <time className="event-feed-time">
                                                        {new Date(row.last_event_at).toLocaleString()}
                                                    </time>
                                                </>
                                            ) : (
                                                '—'
                                            )}
                                        </td>
                                        <td>
                                            <div className="engagement-flags">
                                                {row.opened && <span className="engagement-flag">Opened</span>}
                                                {row.clicked && <span className="engagement-flag">Clicked</span>}
                                                {row.bounced && <span className="engagement-flag engagement-flag--warn">Bounced</span>}
                                                {row.spam_reported && (
                                                    <span className="engagement-flag engagement-flag--warn">Spam</span>
                                                )}
                                                {row.unsubscribed && (
                                                    <span className="engagement-flag engagement-flag--warn">Unsubscribed</span>
                                                )}
                                                {!row.opened &&
                                                    !row.clicked &&
                                                    !row.bounced &&
                                                    !row.spam_reported &&
                                                    !row.unsubscribed &&
                                                    row.delivery_status !== 'failed' &&
                                                    row.delivery_status !== 'pending' && (
                                                        <span className="text-muted">—</span>
                                                    )}
                                            </div>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                    <p className="field-hint">
                        Showing {filteredRecipients.length} of {analytics.recipients.length} recipient(s).
                        {live ? ' Updates in real time.' : ''}
                    </p>
                </section>
            )}

            {analytics.timeline && analytics.timeline.length > 0 && (
                <section className="card-panel">
                    <h2 className="section-heading">Live event feed</h2>
                    <ul className="event-feed">
                        {analytics.timeline.map((event, index) => (
                            <li key={`${event.timestamp}-${event.email}-${index}`} className="event-feed-item">
                                <div className="event-feed-row">
                                    <span className={`event-pill event-pill--${event.event_type}`}>
                                        {event.event_type}
                                    </span>
                                    <div className="event-feed-body">
                                        <span className="event-feed-email">{event.email}</span>
                                        <time className="event-feed-time">
                                            {new Date(event.timestamp).toLocaleString()}
                                        </time>
                                        {event.device_type && (
                                            <span className="text-muted" style={{ fontSize: '0.75rem' }}>
                                                {event.device_type}
                                            </span>
                                        )}
                                        {event.clicked_url && (
                                            <span className="text-muted" style={{ fontSize: '0.75rem' }}>
                                                {event.clicked_url}
                                            </span>
                                        )}
                                    </div>
                                </div>
                            </li>
                        ))}
                    </ul>
                </section>
            )}
        </PageShell>
    );
};

export default CampaignAnalyticsPage;
