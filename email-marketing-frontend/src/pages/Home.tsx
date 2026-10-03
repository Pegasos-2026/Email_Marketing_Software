import React from 'react';
import { Link } from 'react-router-dom';
import '../styles/home.css';

const Home: React.FC = () => (
    <div className="home-hero">
        <div className="home-hero-inner">
            <div className="home-hero-logo">
                <h1>Pegasos</h1>
                <p>Email Marketing software</p>
            </div>
            <h2>Professional email marketing for fast-moving teams</h2>
            <p>
                Launch campaigns, manage audiences, and track live performance with a polished
                email platform built for growth, reliability, and clarity.
            </p>
            <div className="home-hero-actions">
                <Link to="/register" className="btn-primary">
                    Get started
                </Link>
                <Link to="/login" className="btn-secondary">
                    Sign in
                </Link>
            </div>
            <div className="home-hero-features">
                <div>
                    <strong>Reliable delivery</strong>
                    <span>Built-in analytics and domain management help every send land in inboxes.</span>
                </div>
                <div>
                    <strong>Live insights</strong>
                    <span>Real-time open, click, and engagement tracking in one dashboard.</span>
                </div>
            </div>
        </div>
    </div>
);

export default Home;
