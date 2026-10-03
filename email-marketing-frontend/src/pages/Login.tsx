import React, { useState } from 'react';
import { useHistory, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import '../styles/auth.css';

const getErrorMessage = (err: any, fallback: string) => {
    const data = err?.response?.data;
    if (!data) {
        if (err?.message?.includes('Network Error')) {
            return 'Cannot reach the API. Start Django on port 8000 and use http://localhost:3000.';
        }
        return err?.message || fallback;
    }
    if (typeof data.detail === 'string') return data.detail;
    if (typeof data.error === 'string') return data.error;
    return fallback;
};

const Login: React.FC = () => {
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);
    const history = useHistory();
    const { login } = useAuth();

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');
        setLoading(true);
        try {
            await login(email, password);
            history.push('/dashboard');
        } catch (err: any) {
            setError(getErrorMessage(err, 'Login failed'));
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="auth-page">
            <div className="auth-card">
                <div className="auth-brand">
                    <h1>Pegasos</h1>
                    <p className="auth-brand-tagline">Sign in to your account</p>
                </div>
                {error && <div className="alert alert-error">{error}</div>}
                <form onSubmit={handleSubmit}>
                    <div className="form-group">
                        <label htmlFor="email">Email</label>
                        <input
                            id="email"
                            type="email"
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            required
                            autoComplete="email"
                        />
                    </div>
                    <div className="form-group">
                        <label htmlFor="password">Password</label>
                        <input
                            id="password"
                            type="password"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            required
                            autoComplete="current-password"
                        />
                    </div>
                    <button type="submit" disabled={loading} className="btn-primary">
                        {loading ? 'Signing in…' : 'Sign in'}
                    </button>
                </form>
                <p className="auth-footer">
                    No account? <Link to="/register">Create one</Link>
                </p>
            </div>
        </div>
    );
};

export default Login;
