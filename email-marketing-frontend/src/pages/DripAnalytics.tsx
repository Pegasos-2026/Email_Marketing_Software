import React, { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { dripService } from '../services/dripService';
import PageShell from '../components/ui/PageShell';
import '../styles/drip.css';

interface DripAnalyticsData {
    campaign_name?: string;
    status?: string;
    trigger_type?: string;
    total_enrolled?: number;
    active_count?: number;
    completed_count?: number;
    stopped_count?: number;
    total_emails_sent?: number;
    total_emails_opened?: number;
}

const DripAnalytics: React.FC = () => {
    const { id } = useParams<{ id: string }>();
    const [analytics, setAnalytics] = useState<DripAnalyticsData | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchAnalytics = async () => {
            try {
                const data = await dripService.getAnalytics(Number(id));
                setAnalytics(data);
            } catch (err) {
                console.error(err);
            } finally {
                setLoading(false);
            }
        };

        if (id) fetchAnalytics();
    }, [id]);

    if (loading) return <div className="loading-spinner">Loading analytics…</div>;
    if (!analytics) return <div className="alert alert-error">Unable to load analytics</div>;

    const openRate = analytics.total_emails_sent
        ? Math.round(((analytics.total_emails_opened || 0) / analytics.total_emails_sent) * 100)
        : 0;

    return (
        <PageShell
            title={analytics.campaign_name || 'Drip analytics'}
            subtitle={`${analytics.status || ''} · trigger: ${analytics.trigger_type || '—'}`}
            actions={
                <Link to={`/drip/${id}`} className="btn-secondary btn-small">
                    Back to campaign
                </Link>
            }
        >
            <section className="card-panel analytics-summary">
                <div className="stat-grid">
                    <div>Enrolled: <strong>{analytics.total_enrolled ?? 0}</strong></div>
                    <div>Active: <strong>{analytics.active_count ?? 0}</strong></div>
                    <div>Completed: <strong>{analytics.completed_count ?? 0}</strong></div>
                    <div>Stopped: <strong>{analytics.stopped_count ?? 0}</strong></div>
                </div>
            </section>

            <section className="card-panel">
                <h2 className="section-heading">Email performance</h2>
                <div className="stat-grid">
                    <div>Emails sent: <strong>{analytics.total_emails_sent ?? 0}</strong></div>
                    <div>Emails opened: <strong>{analytics.total_emails_opened ?? 0}</strong></div>
                    <div>Open rate: <strong>{openRate}%</strong></div>
                </div>
            </section>
        </PageShell>
    );
};

export default DripAnalytics;
