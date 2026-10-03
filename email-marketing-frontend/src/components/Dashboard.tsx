import React, { useCallback, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { campaignService } from '../services/campaignService';
import { DashboardAnalytics } from '../types';
import { useAnalyticsStream } from '../hooks/useAnalyticsStream';
import PageShell from './ui/PageShell';
import StatCard from './ui/StatCard';
import EmptyState from './ui/EmptyState';
import BarChart from './ui/BarChart';
import DonutChart from './ui/DonutChart';

const segmentColorMap: Record<string, string> = {
    opens: 'rgb(10, 37, 64)',
    clicks: 'rgb(13, 50, 84)',
    delivered: 'rgb(6, 24, 40)',
    bounced: 'rgb(10, 37, 64)',
    unsubscribes: 'rgb(13, 50, 84)',
    'spam reports': 'rgb(6, 24, 40)',
    pending: 'rgb(10, 37, 64)',
    drafts: 'rgb(13, 50, 84)',
    scheduled: 'rgb(6, 24, 40)',
    campaigns: 'rgb(10, 37, 64)',
};

const statCardIcons: Record<string, string> = {
    Campaigns: '📊',
    Sent: '✉️',
    Drafts: '📝',
    Scheduled: '⏰',
    Delivered: '✅',
    Failed: '⚠️',
    Opens: '👁️',
    Clicks: '🖱️',
    Bounced: '🚫',
    Unsubscribes: '🔕',
    'Spam reports': '🛑',
    Pending: '⏳',
};

const getSegmentColor = (label: string) => {
    const key = label.toLowerCase();
    return (
        Object.entries(segmentColorMap).find(([mapKey]) => key.includes(mapKey))?.[1] ||
        '#0f172a'
    );
};

const Dashboard: React.FC = () => {
    const fetchDashboard = useCallback(() => campaignService.getDashboardAnalytics(), []);

    const { data: stats, loading, live, error, lastUpdated, refresh } =
        useAnalyticsStream<DashboardAnalytics>(
            '/campaigns/analytics/dashboard/stream/',
            fetchDashboard,
            []
        );

    const charts = stats?.charts;

    const funnelData = useMemo(
        () => charts?.funnel?.map((d) => ({ label: d.label, value: d.value })) ?? [],
        [charts]
    );

    const breakdownSegments = useMemo(
        () =>
            (charts?.engagement_breakdown ?? [])
                .filter((d) => d.value > 0)
                .map((d) => ({
                    label: d.label,
                    value: d.value,
                    color: getSegmentColor(d.label),
                })),
        [charts]
    );

    if (loading && !stats) {
        return <div className="loading-spinner">Loading dashboard…</div>;
    }

    return (
        <PageShell
            title="Dashboard"
            subtitle="Live performance across campaigns, delivery, and engagement."
            live={live}
            lastUpdated={lastUpdated}
            onRefresh={refresh}
            actions={
                <Link to="/campaigns/create" className="btn-primary">
                    New campaign
                </Link>
            }
        >
            {error && <div className="alert alert-error">{error}</div>}

            <section className="card-panel">
                <h2 className="section-heading">Overview</h2>
                <div className="metrics-grid-ui">
                    <StatCard label="Campaigns" value={stats?.overview.total_campaigns ?? 0} tone="brand" icon={statCardIcons.Campaigns} />
                    <StatCard label="Sent" value={stats?.overview.sent_campaigns ?? 0} tone="success" icon={statCardIcons.Sent} />
                    <StatCard label="Drafts" value={stats?.overview.draft_campaigns ?? 0} icon={statCardIcons.Drafts} />
                    <StatCard label="Scheduled" value={stats?.overview.scheduled_campaigns ?? 0} tone="warning" icon={statCardIcons.Scheduled} />
                </div>
            </section>

            <div className="charts-row">
                <section className="card-panel">
                    <h2 className="section-heading">Engagement funnel</h2>
                    {funnelData.length > 0 ? (
                        <BarChart data={funnelData} />
                    ) : (
                        <p className="text-muted">Send a campaign to see funnel data.</p>
                    )}
                </section>
                <section className="card-panel">
                    <h2 className="section-heading">Engagement mix</h2>
                    {breakdownSegments.length > 0 ? (
                        <>
                            <DonutChart segments={breakdownSegments} />
                            <p className="chart-note">
                                Distinct colors help separate opens from clicks and make campaign engagement easier to scan.
                            </p>
                        </>
                    ) : (
                        <p className="text-muted">No engagement events yet.</p>
                    )}
                </section>
            </div>

            <section className="card-panel">
                <h2 className="section-heading">Delivery & engagement</h2>
                <div className="metrics-grid-ui">
                    <StatCard label="Emails sent" value={stats?.totals.total_emails_sent ?? 0} icon={statCardIcons.Sent} />
                    <StatCard
                        label="Delivered"
                        value={stats?.totals.total_delivered ?? 0}
                        hint={`${stats?.rates?.delivery_rate ?? 0}%`}
                        tone="success"
                        icon={statCardIcons.Delivered}
                    />
                    <StatCard label="Failed" value={stats?.totals.total_failed ?? 0} tone="danger" icon={statCardIcons.Failed} />
                    <StatCard
                        label="Opens"
                        value={stats?.totals.total_opened ?? 0}
                        hint={`${stats?.rates?.open_rate ?? 0}%`}
                        tone="brand"
                        icon={statCardIcons.Opens}
                    />
                    <StatCard
                        label="Clicks"
                        value={stats?.totals.total_clicked ?? 0}
                        hint={`${stats?.rates?.click_through_rate ?? 0}% CTR`}
                        tone="brand"
                        icon={statCardIcons.Clicks}
                    />
                    <StatCard label="Bounced" value={stats?.totals.total_bounced ?? 0} hint={`${stats?.rates?.bounce_rate ?? 0}%`} tone="warning" icon={statCardIcons.Bounced} />
                    <StatCard label="Unsubscribes" value={stats?.totals.total_unsubscribes ?? 0} icon={statCardIcons['Unsubscribes']} />
                    <StatCard label="Spam reports" value={stats?.totals.total_spam_reports ?? 0} tone="danger" icon={statCardIcons['Spam reports']} />
                    <StatCard label="Pending" value={stats?.totals.total_pending ?? 0} icon={statCardIcons.Pending} />
                </div>
            </section>

            <div className="dashboard-split">
                <section className="card-panel">
                    <h2 className="section-heading">Recent campaigns</h2>
                    {stats?.recent_campaigns?.length ? (
                        <ul className="entity-list">
                            {stats.recent_campaigns.map((c) => (
                                <li key={c.id} className="entity-row">
                                    <div className="entity-row-main">
                                        <span className="entity-row-title">{c.name}</span>
                                        <div className="entity-row-meta">
                                            <span>{c.total_sent} sent</span>
                                            <span>Open {c.open_rate.toFixed(1)}%</span>
                                        </div>
                                    </div>
                                    <div className="entity-row-actions">
                                        <Link to={`/campaigns/${c.id}`} className="btn-secondary btn-small">
                                            View
                                        </Link>
                                    </div>
                                </li>
                            ))}
                        </ul>
                    ) : (
                        <EmptyState
                            title="No sent campaigns"
                            description="Launch your first campaign to track live metrics."
                            actionLabel="Create campaign"
                            actionTo="/campaigns/create"
                        />
                    )}
                </section>
                <section className="card-panel">
                    <h2 className="section-heading">Top performers</h2>
                    {stats?.top_performing?.length ? (
                        <ul className="entity-list">
                            {stats.top_performing.map((c) => (
                                <li key={c.id} className="entity-row">
                                    <div className="entity-row-main">
                                        <span className="entity-row-title">{c.name}</span>
                                        <div className="entity-row-metrics">
                                            <span>Open {c.open_rate.toFixed(1)}%</span>
                                            <span>Click {c.click_rate.toFixed(1)}%</span>
                                            <span>{c.total_sent} sent</span>
                                        </div>
                                    </div>
                                    <div className="entity-row-actions">
                                        <Link to={`/campaigns/${c.id}`} className="btn-secondary btn-small">
                                            View
                                        </Link>
                                    </div>
                                </li>
                            ))}
                        </ul>
                    ) : (
                        <p className="text-muted">Rankings appear after campaigns are sent.</p>
                    )}
                </section>
            </div>
        </PageShell>
    );
};

export default Dashboard;
