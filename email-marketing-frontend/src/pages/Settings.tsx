import React from 'react';
import { authService } from '../services/authService';
import { emailService, EmailSettingsData } from '../services/emailService';
import { useToast } from '../context/ToastContext';
import PageShell from '../components/ui/PageShell';
import '../styles/settings.css';

const Settings: React.FC = () => {
    const { showToast } = useToast();
    const [profile, setProfile] = React.useState<any>(null);
    const [provider, setProvider] = React.useState('SMTP');
    const [smtpHost, setSmtpHost] = React.useState('smtp.gmail.com');
    const [smtpPort, setSmtpPort] = React.useState(587);
    const [smtpUser, setSmtpUser] = React.useState('');
    const [smtpPassword, setSmtpPassword] = React.useState('');
    const [apiKey, setApiKey] = React.useState('');
    const [fromName, setFromName] = React.useState('');
    const [fromEmail, setFromEmail] = React.useState('');
    const [sendingDomain, setSendingDomain] = React.useState('');
    const [subject, setSubject] = React.useState('Hello from Pegasos');
    const [html, setHtml] = React.useState(
        '<p>Hello,</p><p>This is a message from Pegasos Email Marketing.</p><p>Regards,<br>Pegasos Team</p>'
    );
    const [toEmail, setToEmail] = React.useState('');
    const [loading, setLoading] = React.useState(false);
    const [settingsLoading, setSettingsLoading] = React.useState(false);
    const [saveLoading, setSaveLoading] = React.useState(false);
    const [smtpPasswordConfigured, setSmtpPasswordConfigured] = React.useState(false);
    const [apiKeyConfigured, setApiKeyConfigured] = React.useState(false);
    const [domainVerified, setDomainVerified] = React.useState(false);
    const [siteUrlPublic, setSiteUrlPublic] = React.useState(true);
    const [siteUrl, setSiteUrl] = React.useState('');

    React.useEffect(() => {
        const loadPageData = async () => {
            try {
                const response = await authService.getProfile();
                setProfile(response);
                setToEmail(response.email || '');
                setFromEmail((current) => current || response.email || '');
                setSmtpUser((current) => current || response.email || '');
            } catch {
                showToast('Unable to load profile', 'error');
            }

            await loadEmailSettings();
        };

        loadPageData();
    }, [showToast]);

    const buildEmailSettingsPayload = (requireCredentials = false): EmailSettingsData => {
        const payload: EmailSettingsData = {
            provider,
            from_name: fromName,
            from_email: fromEmail,
            sending_domain: sendingDomain,
        };

        if (provider === 'SMTP') {
            if (!smtpHost.trim() || !smtpUser.trim()) {
                throw new Error('SMTP host and username are required.');
            }
            payload.smtp_host = smtpHost.trim();
            payload.smtp_port = smtpPort;
            payload.smtp_user = smtpUser.trim();
            if (smtpPassword.trim()) {
                payload.smtp_password = smtpPassword;
            } else if (requireCredentials && !smtpPasswordConfigured) {
                throw new Error(
                    'SMTP password is required. Enter your password and save settings before sending a test email.'
                );
            }
        } else {
            if (apiKey.trim()) {
                payload.api_key = apiKey;
            } else if (requireCredentials && !apiKeyConfigured) {
                throw new Error('SendGrid API key is required before sending a test email.');
            }
        }

        return payload;
    };

    const persistEmailSettings = async (requireCredentials = false) => {
        const payload = buildEmailSettingsPayload(requireCredentials);
        await emailService.updateSettings(payload);
        if (payload.smtp_password) {
            setSmtpPasswordConfigured(true);
        }
        if (payload.api_key) {
            setApiKeyConfigured(true);
        }
        setSmtpPassword('');
        setApiKey('');
    };

    const loadEmailSettings = async () => {
        setSettingsLoading(true);
        try {
            const settings = await emailService.getSettings();
            setProvider(settings.provider || 'SMTP');
            setFromName(settings.from_name || '');
            setFromEmail(settings.from_email || profile?.email || '');
            setSendingDomain(settings.sending_domain || '');
            setSmtpHost(settings.smtp_host || 'smtp.gmail.com');
            setSmtpPort(settings.smtp_port || 587);
            setSmtpUser(settings.smtp_user || profile?.email || '');
            setSmtpPasswordConfigured(Boolean(settings.smtp_password_configured));
            setApiKeyConfigured(Boolean(settings.api_key_configured));
            setDomainVerified(Boolean(settings.domain_verified));
            setSiteUrlPublic(settings.site_url_public !== false);
            setSiteUrl(settings.site_url || '');
            setApiKey('');
            setSmtpPassword('');
        } catch (err: any) {
            showToast(err.response?.data?.error || 'Unable to load email settings', 'error');
        } finally {
            setSettingsLoading(false);
        }
    };

    const saveEmailSettings = async (e: React.FormEvent) => {
        e.preventDefault();
        setSaveLoading(true);

        try {
            await persistEmailSettings(false);
            showToast('Email settings saved', 'success');
        } catch (err: any) {
            showToast(err.message || err.response?.data?.error || 'Failed to save email settings', 'error');
        } finally {
            setSaveLoading(false);
        }
    };

    const sendTestEmail = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        try {
            await persistEmailSettings(true);
            const response = await emailService.sendEmail({
                to_email: toEmail,
                subject,
                html_content: html,
            });
            showToast(response.message || 'Test email sent', 'success');
        } catch (err: any) {
            const apiError = err.response?.data?.error;
            showToast(apiError || err.message || 'Failed to send test email', 'error');
        } finally {
            setLoading(false);
        }
    };

    const verifyDomain = async () => {
        try {
            const response = await emailService.verifyDomain();
            showToast(`DNS records generated for ${response.domain || 'your domain'}`, 'info');
        } catch (err: any) {
            showToast(err.response?.data?.error || 'Configure email settings in admin first', 'error');
        }
    };

    const checkDomainStatus = async () => {
        try {
            const response = await emailService.checkDomainStatus();
            setDomainVerified(response.domain_verified);
            showToast(response.message, response.domain_verified ? 'success' : 'error');
        } catch (err: any) {
            showToast(err.response?.data?.error || 'Failed to check domain status', 'error');
        }
    };

    return (
        <PageShell title="Settings" subtitle="Account profile, email delivery, and test tools.">
            <div className="settings-page">
                <section className="card-panel settings-section">
                    <div className="settings-heading-row">
                        <div>
                            <h2 className="section-heading">Profile</h2>
                            <p className="section-description">
                                Manage your account identity and contact email for administrative notifications.
                            </p>
                        </div>
                    </div>
                    <div className="form-grid form-grid--2">
                        <div className="form-group">
                            <label>Username</label>
                            <input className="form-input" value={profile?.username || ''} readOnly />
                        </div>
                        <div className="form-group">
                            <label>Email</label>
                            <input className="form-input" value={profile?.email || ''} readOnly />
                        </div>
                    </div>
                </section>

                <section className="card-panel settings-section">
                    <div className="settings-heading-row">
                        <div>
                            <h2 className="section-heading">Email delivery settings</h2>
                            <p className="section-description">
                                Configure user-specific email delivery so all messages are sent from your account.
                            </p>
                        </div>
                    </div>
                    <form onSubmit={saveEmailSettings}>
                        <div className="form-grid form-grid--2">
                            <div className="form-group">
                                <label htmlFor="provider">Provider</label>
                                <select
                                    className="form-input"
                                    id="provider"
                                    value={provider}
                                    onChange={(e) => setProvider(e.target.value)}
                                >
                                    <option value="SMTP">SMTP</option>
                                    <option value="SendGrid">SendGrid</option>
                                </select>
                            </div>
                            <div className="form-group">
                                <label htmlFor="fromName">From name</label>
                                <input
                                    className="form-input"
                                    id="fromName"
                                    type="text"
                                    value={fromName}
                                    onChange={(e) => setFromName(e.target.value)}
                                />
                            </div>
                        </div>
                        <div className="form-grid form-grid--2">
                            <div className="form-group">
                                <label htmlFor="fromEmail">From email</label>
                                <input
                                    className="form-input"
                                    id="fromEmail"
                                    type="email"
                                    value={fromEmail}
                                    onChange={(e) => setFromEmail(e.target.value)}
                                />
                            </div>
                            {provider === 'SendGrid' ? (
                                <div className="form-group">
                                    <label htmlFor="apiKey">SendGrid API key</label>
                                    <input
                                        className="form-input"
                                        id="apiKey"
                                        type="text"
                                        value={apiKey}
                                        onChange={(e) => setApiKey(e.target.value)}
                                        placeholder="Leave blank to keep existing key"
                                    />
                                </div>
                            ) : (
                                <div className="form-group">
                                    <label htmlFor="smtpUser">SMTP username</label>
                                    <input
                                        className="form-input"
                                        id="smtpUser"
                                        type="email"
                                        value={smtpUser}
                                        onChange={(e) => setSmtpUser(e.target.value)}
                                    />
                                </div>
                            )}
                        </div>

                        {provider === 'SMTP' ? (
                            <>
                                <div className="form-grid form-grid--2">
                                    <div className="form-group">
                                        <label htmlFor="smtpHost">SMTP host</label>
                                        <input
                                            className="form-input"
                                            id="smtpHost"
                                            type="text"
                                            value={smtpHost}
                                            onChange={(e) => setSmtpHost(e.target.value)}
                                        />
                                    </div>
                                    <div className="form-group">
                                        <label htmlFor="smtpPort">SMTP port</label>
                                        <input
                                            className="form-input"
                                            id="smtpPort"
                                            type="number"
                                            value={smtpPort}
                                            onChange={(e) => setSmtpPort(Number(e.target.value))}
                                        />
                                    </div>
                                </div>
                                <div className="form-grid form-grid--2">
                                    <div className="form-group">
                                        <label htmlFor="smtpPassword">SMTP password</label>
                                        <input
                                            className="form-input"
                                            id="smtpPassword"
                                            type="password"
                                            value={smtpPassword}
                                            onChange={(e) => setSmtpPassword(e.target.value)}
                                            placeholder={
                                                smtpPasswordConfigured
                                                    ? 'Leave blank to keep existing password'
                                                    : 'Enter SMTP or app password'
                                            }
                                        />
                                        {!smtpPasswordConfigured && (
                                            <small className="field-hint">
                                                Password is required before you can send email.
                                            </small>
                                        )}
                                    </div>
                                    <div className="form-group">
                                        <label htmlFor="sendingDomain">Sending domain</label>
                                        <input
                                            className="form-input"
                                            id="sendingDomain"
                                            type="text"
                                            value={sendingDomain}
                                            onChange={(e) => setSendingDomain(e.target.value)}
                                            placeholder="Optional"
                                        />
                                    </div>
                                </div>
                            </>
                        ) : (
                            <div className="form-group">
                                <label htmlFor="sendingDomain">Sending domain</label>
                                <input
                                    className="form-input"
                                    id="sendingDomain"
                                    type="text"
                                    value={sendingDomain}
                                    onChange={(e) => setSendingDomain(e.target.value)}
                                />
                            </div>
                        )}

                        <div className="form-actions">
                            <button type="submit" className="btn-primary" disabled={saveLoading || settingsLoading}>
                                {saveLoading ? 'Saving…' : 'Save email settings'}
                            </button>
                        </div>
                    </form>
                </section>

                <section className="card-panel settings-section">
                    <div className="settings-heading-row">
                        <div>
                            <h2 className="section-heading">Email domain</h2>
                            <p className="section-description">
                                Verify your sending domain in SendGrid, then sync status here before sending campaigns.
                            </p>
                            {provider === 'SendGrid' && (
                                <p className="section-copy">
                                    Status:{' '}
                                    <strong className={domainVerified ? 'text-success' : 'text-warning'}>
                                        {domainVerified ? 'Verified' : 'Not verified yet'}
                                    </strong>
                                </p>
                            )}
                        </div>
                        <div className="settings-domain-actions">
                            <button type="button" className="btn-secondary" onClick={verifyDomain}>
                                Generate DNS records
                            </button>
                            <button type="button" className="btn-primary" onClick={checkDomainStatus}>
                                Check verification status
                            </button>
                        </div>
                    </div>
                    {provider === 'SendGrid' && (
                        <div className="deliverability-notice">
                            <h3>Inbox delivery checklist</h3>
                            {!siteUrlPublic && (
                                <p className="deliverability-warning">
                                    <strong>Important:</strong> Campaign emails currently include{' '}
                                    <strong>localhost</strong> tracking links because{' '}
                                    <code>SITE_URL</code> is set to <code>{siteUrl || 'http://localhost:8000'}</code>.
                                    Gmail often sends those messages to spam. Set{' '}
                                    <code>SITE_URL</code> in your server <code>.env</code> to your public HTTPS app URL
                                    (for example <code>https://app.pegasos.in</code>), restart the backend, then send
                                    again.
                                </p>
                            )}
                            {!domainVerified ? (
                                <>
                                    <p>
                                        If emails land in spam, complete <strong>Domain Authentication</strong> for{' '}
                                        <strong>pegasos.in</strong> in SendGrid (SPF/DKIM/DMARC DNS records).
                                        Single Sender alone is often not enough for Gmail inbox placement.
                                    </p>
                                    <ol>
                                        <li>SendGrid → Settings → Sender Authentication → authenticate pegasos.in</li>
                                        <li>Add all DNS records at your domain provider (Hostinger)</li>
                                        <li>
                                            Click <strong>Check verification status</strong> above when SendGrid shows
                                            Verified
                                        </li>
                                        <li>Use a real From name, reply-to, and plain text content in campaigns</li>
                                        <li>
                                            Ask recipients to mark your email as <strong>Not spam</strong> once
                                        </li>
                                    </ol>
                                </>
                            ) : (
                                <>
                                    <p>
                                        Your domain is verified. If mail reaches Gmail <strong>All Mail</strong> but
                                        not the <strong>Primary inbox</strong>, use these steps:
                                    </p>
                                    <ol>
                                        <li>
                                            Keep <strong>Inbox Priority</strong> ON — sends plain personal email (no
                                            marketing HTML) to all recipients in one send
                                        </li>
                                        <li>
                                            Use a personal From name (e.g. Anna), simple subject, and complete plain
                                            text with your signature
                                        </li>
                                        <li>
                                            Ask each recipient to open the email → click the <strong>⋮</strong> menu →{' '}
                                            <strong>Move to Primary</strong> (trains Gmail for future sends)
                                        </li>
                                        <li>
                                            Add <strong>gunaseelan@pegasos.in</strong> to Google Contacts on each
                                            Gmail account
                                        </li>
                                        <li>
                                            Have one recipient <strong>reply</strong> to your email once — replies
                                            strongly improve Primary placement
                                        </li>
                                        <li>
                                            Register at{' '}
                                            <a
                                                href="https://postmaster.google.com/"
                                                target="_blank"
                                                rel="noopener noreferrer"
                                            >
                                                Google Postmaster Tools
                                            </a>{' '}
                                            for pegasos.in
                                        </li>
                                    </ol>
                                </>
                            )}
                        </div>
                    )}
                </section>

                <section className="card-panel settings-section">
                    <div className="settings-heading-row">
                        <div>
                            <h2 className="section-heading">Send test email</h2>
                            <p className="section-description">
                                Use this tool to verify that outbound email delivery is configured correctly.
                                Your email settings are saved automatically before each test send.
                            </p>
                        </div>
                    </div>
                    <form onSubmit={sendTestEmail}>
                        <div className="form-grid form-grid--2">
                            <div className="form-group">
                                <label htmlFor="toEmail">To</label>
                                <input
                                    className="form-input"
                                    id="toEmail"
                                    type="email"
                                    value={toEmail}
                                    onChange={(e) => setToEmail(e.target.value)}
                                    required
                                />
                            </div>
                            <div className="form-group">
                                <label htmlFor="subject">Subject</label>
                                <input
                                    className="form-input"
                                    id="subject"
                                    value={subject}
                                    onChange={(e) => setSubject(e.target.value)}
                                    required
                                />
                            </div>
                        </div>
                        <div className="form-group">
                            <label htmlFor="html">Email content</label>
                            <textarea
                                className="form-textarea"
                                id="html"
                                rows={6}
                                value={html}
                                onChange={(e) => setHtml(e.target.value)}
                            />
                        </div>
                        <div className="form-actions">
                            <button type="submit" className="btn-primary" disabled={loading}>
                                {loading ? 'Sending…' : 'Send test email'}
                            </button>
                        </div>
                    </form>
                </section>
            </div>
        </PageShell>
    );
};

export default Settings;
