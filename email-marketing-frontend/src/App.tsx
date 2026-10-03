import React from 'react';
import { BrowserRouter as Router, Route, Switch, Redirect } from 'react-router-dom';
import { useAuth } from './context/AuthContext';
import Layout from './components/Layout';
import ProtectedRoute from './components/ProtectedRoute';
// Auth Pages
import Login from './pages/Login';
import Register from './pages/Register';

// Protected Pages
import Dashboard from './components/Dashboard';
import CampaignList from './components/CampaignList';
import CreateCampaign from './pages/CreateCampaign';
import CampaignAnalytics from './pages/CampaignAnalytics';
import CampaignDetail from './pages/CampaignDetail';
import CampaignEdit from './pages/CampaignEdit';
import DripDashboard from './pages/DripDashboard';
import CreateDripCampaign from './pages/CreateDripCampaign';
import DripBuilder from './pages/DripBuilder';
import DripDetail from './pages/DripDetail';
import DripAnalytics from './pages/DripAnalytics';
import EmailTemplates from './pages/EmailTemplates';
import TemplateForm from './pages/TemplateForm';
import TemplateDetail from './pages/TemplateDetail';
import ContactManagement from './pages/ContactManagement';
import ContactListDetail from './pages/ContactListDetail';
import Home from './pages/Home';
import Reports from './pages/Reports';
import Settings from './pages/Settings';
import EmailEditor from './components/EmailEditor';
const ProtectedWithLayout: React.FC<{ component: React.ComponentType<any>; path: string; exact?: boolean }> = ({
    component: Component,
    path,
    exact = false,
}) => (
    <ProtectedRoute
        path={path}
        exact={exact}
        component={(props: any) => (
            <Layout>
                <Component {...props} />
            </Layout>
        )}
    />
);

const HomeRoute: React.FC = () => {
    const { isAuthenticated, loading } = useAuth();
    if (loading) return <div className="loading-spinner">Loading…</div>;
    if (isAuthenticated) return <Redirect to="/dashboard" />;
    return <Home />;
};

const App: React.FC = () => {
    return (
        <Router>
            <Switch>
                {/* Public Routes */}
                <Route path="/login" exact component={Login} />
                <Route path="/register" exact component={Register} />

                {/* Protected Routes */}
                <ProtectedWithLayout path="/dashboard" exact component={Dashboard} />
                <ProtectedWithLayout path="/campaigns" exact component={CampaignList} />
                <ProtectedWithLayout path="/campaigns/create" exact component={CreateCampaign} />
                <ProtectedWithLayout path="/campaigns/:campaignId/edit" exact component={CampaignEdit} />
                <ProtectedWithLayout path="/campaigns/:campaignId/analytics" exact component={CampaignAnalytics} />
                <ProtectedWithLayout path="/campaigns/:campaignId" exact component={CampaignDetail} />
                <ProtectedWithLayout path="/drip" exact component={DripDashboard} />
                <ProtectedWithLayout path="/drip/create" exact component={CreateDripCampaign} />
                <ProtectedWithLayout path="/drip/:id/builder" exact component={DripBuilder} />
                <ProtectedWithLayout path="/drip/:id/analytics" exact component={DripAnalytics} />
                <ProtectedWithLayout path="/drip/:id" exact component={DripDetail} />
                <ProtectedWithLayout path="/templates" exact component={EmailTemplates} />
                <ProtectedWithLayout path="/templates/create" exact component={TemplateForm} />
                <ProtectedWithLayout path="/templates/:templateId/edit" exact component={TemplateForm} />
                <ProtectedWithLayout path="/templates/:templateId" exact component={TemplateDetail} />
                <ProtectedWithLayout path="/contacts" exact component={ContactManagement} />
                <ProtectedWithLayout path="/contact-lists/:listId" exact component={ContactListDetail} />
                <ProtectedWithLayout path="/email-editor" exact component={EmailEditor} />
                <ProtectedWithLayout path="/reports" exact component={Reports} />
                <ProtectedWithLayout path="/settings" exact component={Settings} />

                {/* Layout Routes */}
                <Route path="/" exact>
                    <Layout>
                        <HomeRoute />
                    </Layout>
                </Route>

                {/* Catch All */}
                <Route path="*">
                    <Redirect to="/" />
                </Route>
            </Switch>
        </Router>
    );
};

export default App;