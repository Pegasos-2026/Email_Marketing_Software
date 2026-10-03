import React, { useCallback, useMemo, useState } from 'react';
import * as XLSX from 'xlsx';
import { campaignService } from '../services/campaignService';
import { useAnalyticsStream } from '../hooks/useAnalyticsStream';
import { DashboardAnalytics } from '../types';
import PageShell from '../components/ui/PageShell';
import '../styles/reports.css';

interface CampaignReport {
    id: number;
    name: string;
    status: string;
    sent_at?: string;
    analytics?: {
        sending: { total_sent: number };
        engagement: {
            total_opened: number;
            total_clicked: number;
            open_rate: number;
            click_rate: number;
        };
        negative?: {
            bounce_rate?: number;
        };
    };
}

type SortDirection = 'asc' | 'desc';

type SortKey = 'name' | 'status' | 'sent' | 'opens' | 'clicks' | 'openRate' | 'clickRate';

const Reports: React.FC = () => {
    const [selectedCampaign, setSelectedCampaign] = useState<number | null>(null);
    const [campaignAnalytics, setCampaignAnalytics] = useState<any>(null);
    const [detailError, setDetailError] = useState('');
    const [campaigns, setCampaigns] = useState<CampaignReport[]>([]);
    const [loading, setLoading] = useState(true);
    const [listError, setListError] = useState('');
    const [searchTerm, setSearchTerm] = useState('');
    const [statusFilter, setStatusFilter] = useState('all');
    const [currentPage, setCurrentPage] = useState(1);
    const [sortKey, setSortKey] = useState<SortKey>('name');
    const [sortDirection, setSortDirection] = useState<SortDirection>('asc');

    const fetchReports = useCallback(async () => {
        const campaignsResponse = await campaignService.getCampaigns();
        return Promise.all(
            campaignsResponse.map(async (campaign) => {
                try {
                    const analyticsData = await campaignService.getCampaignAnalytics(campaign.id);
                    return { ...campaign, analytics: analyticsData };
                } catch {
                    return campaign as CampaignReport;
                }
            })
        );
    }, []);

    const fetchDashboard = useCallback(() => campaignService.getDashboardAnalytics(), []);

    const {
        data: dashboard,
        live,
        lastUpdated,
        refresh: refreshDashboard,
    } = useAnalyticsStream<DashboardAnalytics>(
        '/campaigns/analytics/dashboard/stream/',
        fetchDashboard,
        []
    );

    const loadCampaignList = useCallback(async () => {
        try {
            const list = await fetchReports();
            setCampaigns(list);
            setListError('');
        } catch (err: any) {
            setListError(err.response?.data?.detail || 'Failed to load reports');
        } finally {
            setLoading(false);
        }
    }, [fetchReports]);

    React.useEffect(() => {
        loadCampaignList();
        const t = setInterval(loadCampaignList, 10000);
        return () => clearInterval(t);
    }, [loadCampaignList]);

    React.useEffect(() => {
        if (dashboard) loadCampaignList();
    }, [dashboard, loadCampaignList]);

    const formatRate = (rate?: number) =>
        rate != null && !Number.isNaN(rate) ? `${rate.toFixed(1)}%` : 'N/A';

    const fetchCampaignAnalytics = async (campaignId: number) => {
        setDetailError('');
        try {
            const response = await campaignService.getCampaignAnalytics(campaignId);
            setCampaignAnalytics(response);
            setSelectedCampaign(campaignId);
        } catch (err: any) {
            setDetailError(err.response?.data?.detail || 'Failed to load details');
        }
    };

    const toggleSort = (key: SortKey) => {
        if (sortKey === key) {
            setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
        } else {
            setSortKey(key);
            setSortDirection('asc');
        }
    };

    const filteredCampaigns = useMemo(() => {
        const normalizedSearch = searchTerm.trim().toLowerCase();
        return campaigns
            .filter((campaign) => {
                const matchSearch = campaign.name.toLowerCase().includes(normalizedSearch);
                const matchStatus = statusFilter === 'all' || campaign.status === statusFilter;
                return matchSearch && matchStatus;
            })
            .sort((left, right) => {
                const getMetric = (item: CampaignReport, key: SortKey) => {
                    switch (key) {
                        case 'status':
                            return item.status || '';
                        case 'sent':
                            return item.analytics?.sending?.total_sent ?? 0;
                        case 'opens':
                            return item.analytics?.engagement?.total_opened ?? 0;
                        case 'clicks':
                            return item.analytics?.engagement?.total_clicked ?? 0;
                        case 'openRate':
                            return item.analytics?.engagement?.open_rate ?? 0;
                        case 'clickRate':
                            return item.analytics?.engagement?.click_rate ?? 0;
                        default:
                            return item.name || '';
                    }
                };

                const leftValue = getMetric(left, sortKey);
                const rightValue = getMetric(right, sortKey);

                if (typeof leftValue === 'string' && typeof rightValue === 'string') {
                    return sortDirection === 'asc'
                        ? leftValue.localeCompare(rightValue)
                        : rightValue.localeCompare(leftValue);
                }

                return sortDirection === 'asc'
                    ? (leftValue as number) - (rightValue as number)
                    : (rightValue as number) - (leftValue as number);
            });
    }, [campaigns, searchTerm, statusFilter, sortDirection, sortKey]);

    const pageSize = 8;
    const totalPages = Math.max(1, Math.ceil(filteredCampaigns.length / pageSize));

    React.useEffect(() => {
        setCurrentPage(1);
    }, [searchTerm, statusFilter, sortKey, sortDirection]);

    const currentCampaigns = filteredCampaigns.slice((currentPage - 1) * pageSize, currentPage * pageSize);

    const exportRows = filteredCampaigns.map((campaign) => ({
        Campaign: campaign.name,
        Status: campaign.status,
        Sent: campaign.analytics?.sending?.total_sent ?? 0,
        Opens: campaign.analytics?.engagement?.total_opened ?? 0,
        Clicks: campaign.analytics?.engagement?.total_clicked ?? 0,
        'Open %': formatRate(campaign.analytics?.engagement?.open_rate),
        'Click %': formatRate(campaign.analytics?.engagement?.click_rate),
    }));

    const handleExportCsv = () => {
        const headers = Object.keys(exportRows[0] || {});
        const csv = [headers.join(',')]
            .concat(
                exportRows.map((row) =>
                    headers.map((key) => String(row[key as keyof typeof row] ?? '')).join(',')
                )
            )
            .join('\n');
        const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = `reports_export_${new Date().toISOString().slice(0, 10)}.csv`;
        link.click();
    };

    const handleExportExcel = () => {
        const worksheet = XLSX.utils.json_to_sheet(exportRows);
        const workbook = XLSX.utils.book_new();
        XLSX.utils.book_append_sheet(workbook, worksheet, 'Reports');
        XLSX.writeFile(workbook, `reports_export_${new Date().toISOString().slice(0, 10)}.xlsx`);
    };

    const statusOptions = ['all', 'draft', 'sent', 'scheduled', 'sending'];

    if (loading && campaigns.length === 0) {
        return <div className="loading-spinner">Loading reports…</div>;
    }

    return (
        <PageShell
            title="Reports"
            subtitle="Campaign-level performance with account-wide live metrics."
            actions={
                <>
                    <button type="button" className="btn-secondary" onClick={handleExportCsv}>
                        Export CSV
                    </button>
                    <button type="button" className="btn-secondary" onClick={handleExportExcel}>
                        Export Excel
                    </button>
                </>
            }
            live={live}
            lastUpdated={lastUpdated}
            onRefresh={() => {
                refreshDashboard();
                loadCampaignList();
            }}
        >
            <div className="reports-page">
                {listError && <div className="alert alert-error">{listError}</div>}
                {detailError && <div className="alert alert-error">{detailError}</div>}

            <div className="reports-toolbar">
                <div className="reports-toolbar-left">
                    <div className="field-group">
                        <label htmlFor="report-search">Search campaigns</label>
                        <input
                            id="report-search"
                            type="text"
                            placeholder="Search by campaign name"
                            value={searchTerm}
                            onChange={(event) => setSearchTerm(event.target.value)}
                        />
                    </div>
                    <div className="field-group">
                        <label htmlFor="report-status">Filter status</label>
                        <select
                            id="report-status"
                            value={statusFilter}
                            onChange={(event) => setStatusFilter(event.target.value)}
                        >
                            {statusOptions.map((status) => (
                                <option key={status} value={status}>
                                    {status === 'all' ? 'All statuses' : status}
                                </option>
                            ))}
                        </select>
                    </div>
                </div>
                <div className="reports-toolbar-right">
                    <div className="report-label">
                        Showing {filteredCampaigns.length} campaign{filteredCampaigns.length === 1 ? '' : 's'}
                    </div>
                </div>
            </div>

            {dashboard && (
                <section className="card-panel reports-summary">
                    <h2 className="section-heading">Account snapshot</h2>
                    <div className="reports-summary-grid">
                        <div>
                            <strong>{dashboard.totals.total_emails_sent}</strong>
                            <span>Sent</span>
                        </div>
                        <div>
                            <strong>{dashboard.totals.total_opened}</strong>
                            <span>Opens</span>
                        </div>
                        <div>
                            <strong>{dashboard.totals.total_clicked}</strong>
                            <span>Clicks</span>
                        </div>
                        <div>
                            <strong>{dashboard.rates ? formatRate(dashboard.rates.open_rate) : 'N/A'}</strong>
                            <span>Avg open</span>
                        </div>
                        <div>
                            <strong>{dashboard.rates ? formatRate(dashboard.rates.click_through_rate) : 'N/A'}</strong>
                            <span>Avg click</span>
                        </div>
                    </div>
                </section>
            )}

            <section className="card-panel">
                <div className="reports-section-header">
                    <h2 className="section-heading">Campaign performance</h2>
                    <span className="section-note">Sorted by {sortKey.replace(/([A-Z])/g, ' $1').toLowerCase()}</span>
                </div>

                {currentCampaigns.length > 0 ? (
                    <div className="table-wrap">
                        <table className="data-table">
                            <thead>
                                <tr>
                                    <th onClick={() => toggleSort('name')}>
                                        Campaign {sortKey === 'name' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}
                                    </th>
                                    <th onClick={() => toggleSort('status')}>
                                        Status {sortKey === 'status' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}
                                    </th>
                                    <th onClick={() => toggleSort('sent')}>
                                        Sent {sortKey === 'sent' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}
                                    </th>
                                    <th onClick={() => toggleSort('opens')}>
                                        Opens {sortKey === 'opens' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}
                                    </th>
                                    <th onClick={() => toggleSort('clicks')}>
                                        Clicks {sortKey === 'clicks' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}
                                    </th>
                                    <th onClick={() => toggleSort('openRate')}>
                                        Open % {sortKey === 'openRate' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}
                                    </th>
                                                    <th onClick={() => toggleSort('clickRate')}>
                                        Click % {sortKey === 'clickRate' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}
                                    </th>
                                </tr>
                            </thead>
                            <tbody>
                                {currentCampaigns.map((campaign) => (
                                    <tr key={campaign.id} className="clickable-row" onClick={() => fetchCampaignAnalytics(campaign.id)}>
                                        <td>{campaign.name}</td>
                                        <td>
                                            <span className={`status-badge status-${campaign.status}`}>
                                                {campaign.status}
                                            </span>
                                        </td>
                                        <td>{campaign.analytics?.sending?.total_sent ?? 0}</td>
                                        <td>{campaign.analytics?.engagement?.total_opened ?? 0}</td>
                                        <td>{campaign.analytics?.engagement?.total_clicked ?? 0}</td>
                                        <td>{formatRate(campaign.analytics?.engagement?.open_rate)}</td>
                                        <td>{formatRate(campaign.analytics?.engagement?.click_rate)}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                ) : (
                    <div className="empty-state">
                        <h3>No matching campaigns</h3>
                        <p>Try a different search term or reset the status filter to see more results.</p>
                    </div>
                )}

                {filteredCampaigns.length > pageSize && (
                    <div className="reports-pagination">
                        <div className="page-summary">
                            Showing {(currentPage - 1) * pageSize + 1}–
                            {Math.min(currentPage * pageSize, filteredCampaigns.length)} of {filteredCampaigns.length}
                        </div>
                        <div className="pagination-controls">
                            <button
                                type="button"
                                className="btn-secondary btn-small"
                                onClick={() => setCurrentPage((prev) => Math.max(prev - 1, 1))}
                                disabled={currentPage === 1}
                            >
                                Previous
                            </button>
                            <span>
                                Page {currentPage} of {totalPages}
                            </span>
                            <button
                                type="button"
                                className="btn-secondary btn-small"
                                onClick={() => setCurrentPage((prev) => Math.min(prev + 1, totalPages))}
                                disabled={currentPage === totalPages}
                            >
                                Next
                            </button>
                        </div>
                    </div>
                )}
            </section>



            {selectedCampaign && campaignAnalytics && (
                <section className="card-panel">
                    <h2 className="section-heading">Campaign detail</h2>
                    <div className="reports-detail-grid">
                        <div>
                            <span>Sent</span>
                            <strong>{campaignAnalytics.sending?.total_sent ?? 0}</strong>
                        </div>
                        <div>
                            <span>Opens</span>
                            <strong>{campaignAnalytics.engagement?.total_opened ?? 0}</strong>
                        </div>
                        <div>
                            <span>Clicks</span>
                            <strong>{campaignAnalytics.engagement?.total_clicked ?? 0}</strong>
                        </div>
                        <div>
                            <span>Open rate</span>
                            <strong>{formatRate(campaignAnalytics.engagement?.open_rate)}</strong>
                        </div>
                        <div>
                            <span>Click rate</span>
                            <strong>{formatRate(campaignAnalytics.engagement?.click_rate)}</strong>
                        </div>
                        <div>
                            <span>Bounce rate</span>
                            <strong>{formatRate(campaignAnalytics.negative?.bounce_rate)}</strong>
                        </div>
                    </div>
                </section>
            )}
            </div>
        </PageShell>
    );
};

export default Reports;
