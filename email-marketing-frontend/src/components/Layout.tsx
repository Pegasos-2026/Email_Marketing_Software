import React, { useState } from 'react';
import { Link, useHistory, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import '../styles/layout.css';

const NAV_ITEMS = [
    { to: '/dashboard', label: 'Dashboard', icon: '▣' },
    { to: '/campaigns', label: 'Campaigns', icon: '✉' },
    { to: '/drip', label: 'Drip Campaigns', icon: '⇄' },
    { to: '/templates', label: 'Templates', icon: '▤' },
    { to: '/contacts', label: 'Contacts', icon: '◎' },
    { to: '/reports', label: 'Reports', icon: '▥' },
    { to: '/settings', label: 'Settings', icon: '⚙' },
];

const Layout: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const { isAuthenticated, user, logout } = useAuth();
    const history = useHistory();
    const location = useLocation();
    const [sidebarOpen, setSidebarOpen] = useState(false);

    const handleLogout = async () => {
        try {
            await logout();
        } finally {
            history.push('/login');
        }
    };

    if (!isAuthenticated) {
        return <div className="layout-public">{children}</div>;
    }

    const isActive = (path: string) =>
        location.pathname === path ||
        (path !== '/dashboard' && location.pathname.startsWith(path));

    return (
        <div className="app-shell">
            <button
                type="button"
                className="sidebar-toggle"
                aria-label="Toggle menu"
                onClick={() => setSidebarOpen((o) => !o)}
            >
                ☰
            </button>

            {sidebarOpen && (
                <button
                    type="button"
                    className="sidebar-backdrop"
                    aria-label="Close menu"
                    onClick={() => setSidebarOpen(false)}
                />
            )}

            <aside className={`app-sidebar ${sidebarOpen ? 'app-sidebar--open' : ''}`}>
                <Link to="/dashboard" className="sidebar-brand" onClick={() => setSidebarOpen(false)}>
                    <span className="sidebar-brand-text">
                        <strong>Pegasos</strong>
                        <small>Email Marketing</small>
                    </span>
                </Link>

                <nav className="sidebar-nav">
                    {NAV_ITEMS.map((item) => (
                        <Link
                            key={item.to}
                            to={item.to}
                            className={`sidebar-link ${isActive(item.to) ? 'sidebar-link--active' : ''}`}
                            onClick={() => setSidebarOpen(false)}
                        >
                            <span className="sidebar-link-icon" aria-hidden>
                                {item.icon}
                            </span>
                            {item.label}
                        </Link>
                    ))}
                </nav>

                <div className="sidebar-footer">
                    <div className="sidebar-user">
                        <span className="sidebar-user-avatar">
                            {(user?.first_name?.[0] || user?.email?.[0] || 'U').toUpperCase()}
                        </span>
                        <div>
                            <strong>{user?.first_name || user?.username || 'User'}</strong>
                            <small>{user?.email}</small>
                        </div>
                    </div>
                    <button
                        type="button"
                        className="btn-secondary btn-small sidebar-logout"
                        onClick={handleLogout}
                    >
                        Sign out
                    </button>
                </div>
            </aside>

            <div className="app-main">
                <main className="app-content">{children}</main>
                <footer className="app-footer">
                    © {new Date().getFullYear()} Pegasos Email Marketing
                </footer>
            </div>
        </div>
    );
};

export default Layout;
