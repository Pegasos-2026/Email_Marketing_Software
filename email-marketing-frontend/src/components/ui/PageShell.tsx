import React from 'react';
import LiveBadge from './LiveBadge';

interface PageShellProps {
    title: string;
    subtitle?: string;
    actions?: React.ReactNode;
    live?: boolean;
    lastUpdated?: Date | null;
    onRefresh?: () => void;
    children: React.ReactNode;
}

const PageShell: React.FC<PageShellProps> = ({
    title,
    subtitle,
    actions,
    live,
    lastUpdated,
    onRefresh,
    children,
}) => (
    <div className="page-shell">
        <header className="page-header">
            <div className="page-header-text">
                <h1>{title}</h1>
                {subtitle && <p className="page-subtitle">{subtitle}</p>}
                {(live !== undefined || lastUpdated) && (
                    <div className="page-header-meta">
                        <LiveBadge live={!!live} />
                        {lastUpdated && (
                            <span className="meta-time">
                                Updated {lastUpdated.toLocaleTimeString()}
                            </span>
                        )}
                        {onRefresh && (
                            <button type="button" className="btn-ghost" onClick={onRefresh}>
                                Refresh
                            </button>
                        )}
                    </div>
                )}
            </div>
            {actions && <div className="page-header-actions">{actions}</div>}
        </header>
        <div className="page-body">{children}</div>
    </div>
);

export default PageShell;
