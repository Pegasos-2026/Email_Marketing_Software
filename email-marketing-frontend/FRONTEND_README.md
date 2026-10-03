# Email Marketing Frontend - Complete Documentation

## Overview

This frontend application is a React/TypeScript web interface for the Email Marketing Software backend. It provides a comprehensive UI for managing email campaigns, contacts, templates, and analytics.

## Project Structure

```
email-marketing-frontend/
├── src/
│   ├── components/
│   │   ├── Layout.tsx              # Main layout with navigation
│   │   ├── Dashboard.tsx           # Dashboard overview
│   │   ├── CampaignList.tsx        # List all campaigns
│   │   ├── EmailEditor.tsx         # Email content editor
│   │   └── ProtectedRoute.tsx      # Protected route wrapper
│   ├── pages/
│   │   ├── Home.tsx                # Public home page
│   │   ├── Login.tsx               # Login page
│   │   ├── Register.tsx            # Registration page
│   │   ├── CreateCampaign.tsx      # Create new campaign
│   │   ├── CampaignAnalytics.tsx   # Campaign analytics view
│   │   ├── EmailTemplates.tsx      # Email templates management
│   │   ├── ContactManagement.tsx   # Contact management
│   │   ├── Reports.tsx             # Reports page
│   │   └── Settings.tsx            # Settings page
│   ├── services/
│   │   ├── api.ts                  # Axios API client with interceptors
│   │   └── authService.ts          # Authentication service
│   ├── styles/
│   │   ├── layout.css              # Layout styles
│   │   ├── auth.css                # Authentication styles
│   │   ├── dashboard.css           # Dashboard styles
│   │   ├── campaigns.css           # Campaigns styles
│   │   ├── analytics.css           # Analytics styles
│   │   ├── templates.css           # Templates styles
│   │   └── contacts.css            # Contacts styles
│   ├── App.tsx                     # Main app component with routes
│   ├── index.tsx                   # React entry point
│   └── index.css                   # Global styles
└── public/
    └── index.html                  # HTML template
```

## Features

### 1. **Authentication**
- **Login** - User authentication with JWT tokens
- **Register** - New user account creation
- **Protected Routes** - Routes that require authentication
- **Auto Token Refresh** - Automatic token refresh on 401 errors

### 2. **Dashboard**
- **Overview Statistics** - Total sent, opens, clicks, draft campaigns
- **Recent Campaigns** - Quick view of last 5 campaigns
- **Campaign Status** - Visual status badges (draft, sent, scheduled, sending)

### 3. **Campaign Management**
- **List Campaigns** - View all campaigns with filtering by status
- **Create Campaign** - Form to create new campaigns with:
  - Campaign name and subject
  - Sender information (from email, from name, reply-to)
  - Contact list selection
  - HTML and plain text content
- **Edit Campaign** - Modify draft campaigns
- **Delete Campaign** - Remove draft campaigns
- **Campaign Details** - View full campaign information

### 4. **Analytics**
- **Campaign Analytics** - Detailed metrics for sent campaigns
  - Sending performance (recipients, sent, delivered, delivery rate)
  - Engagement metrics (opens, clicks, click-to-open rate)
  - Negative events (bounces, spam reports, unsubscribes)
- **Dashboard Statistics** - Aggregate metrics across all campaigns

### 5. **Email Templates**
- **Browse Templates** - View templates by category
- **Filter by Category** - newsletter, promotional, event, welcome, announcement
- **Create Template** - Create custom email templates
- **Edit Template** - Modify existing templates
- **Delete Template** - Remove templates
- **Template Preview** - Preview templates with sample data

### 6. **Contact Management**
- **Contact List** - View all contacts with search functionality
- **Import Contacts** - Import contacts from CSV
- **Export Contacts** - Export contacts to CSV
- **Search Contacts** - Filter by email or name
- **Contact Status** - View subscription status
- **Tags** - View and manage contact tags

### 7. **Reports**
- Campaign performance reports
- Engagement metrics
- Contact engagement history

### 8. **Settings**
- User profile settings
- Email configuration (SendGrid settings)
- Domain verification
- General preferences

## Services

### API Service (`api.ts`)
- **Base Configuration** - Set up axios with baseURL
- **Request Interceptor** - Automatically adds JWT token to requests
- **Response Interceptor** - Handles 401 errors and token refresh
- **Token Management** - Stores and refreshes tokens in localStorage

### Authentication Service (`authService.ts`)
- `register()` - Create new user account
- `login()` - Authenticate user
- `logout()` - Logout and blacklist token
- `getProfile()` - Fetch user profile
- `isAuthenticated()` - Check if user is logged in

## Backend Integration

The frontend connects to the Django backend API:

### Authentication Endpoints
- `POST /api/token/` - Get access and refresh tokens
- `POST /api/token/refresh/` - Refresh access token
- `POST /api/auth/register/` - Register new user
- `GET /api/auth/profile/` - Get current user
- `POST /api/auth/logout/` - Logout

### Campaign Endpoints
- `GET /api/campaigns/` - List user campaigns
- `POST /api/campaigns/` - Create campaign
- `GET /api/campaigns/{id}/` - Get campaign details
- `PUT /api/campaigns/{id}/` - Update campaign
- `DELETE /api/campaigns/{id}/` - Delete campaign
- `POST /api/campaigns/{id}/send/` - Send campaign
- `POST /api/campaigns/{id}/schedule/` - Schedule campaign

### Analytics Endpoints
- `GET /api/analytics/dashboard/` - Dashboard statistics
- `GET /api/analytics/campaign/{id}/` - Campaign analytics

### Template Endpoints
- `GET /api/templates/` - List templates
- `POST /api/templates/create/` - Create template
- `GET /api/templates/{id}/` - Template details
- `DELETE /api/templates/{id}/delete/` - Delete template

### Contact Endpoints
- `GET /api/contacts/` - List contacts
- `POST /api/contacts/import/` - Import contacts
- `GET /api/contacts/export/` - Export contacts

## Installation & Setup

```bash
# Navigate to frontend directory
cd email-marketing-frontend

# Install dependencies
npm install

# Start development server
npm start

# Build for production
npm run build

# Run tests
npm test
```

The app will be available at `http://localhost:3000`

## Environment Configuration

Create a `.env` file if needed:
```
REACT_APP_API_BASE_URL=http://localhost:8000/api
```

## Component Usage Examples

### Using ProtectedRoute
```tsx
<ProtectedRoute path="/campaigns" component={CampaignList} />
```

### Using API Service
```tsx
import api from '../services/api';

const response = await api.get('/campaigns/');
await api.post('/campaigns/', campaignData);
```

### Using Auth Service
```tsx
import { authService } from '../services/authService';

await authService.login(email, password);
const isAuth = authService.isAuthenticated();
```

## Styling

The application uses CSS modules and a global style system:

- **Layout CSS** - Header, footer, navigation
- **Component CSS** - Specific styles for each component
- **Global CSS** - Common styles, buttons, badges, messages
- **Responsive Design** - Mobile-first approach with media queries

### Common CSS Classes
- `.btn-primary` - Primary action button
- `.btn-secondary` - Secondary action button
- `.btn-small` - Small inline button
- `.status-badge` - Status indicator
- `.error-message` - Error notification
- `.loading` - Loading state
- `.no-data` - Empty state

## State Management

Components use React hooks for state management:
- `useState` - Local component state
- `useEffect` - Side effects (API calls)
- `useHistory` - Navigation
- `useParams` - Route parameters

## Authentication Flow

1. User navigates to `/login` or `/register`
2. User enters credentials
3. Frontend sends to backend API
4. Backend returns JWT tokens (access + refresh)
5. Frontend stores tokens in localStorage
6. All subsequent requests include Bearer token
7. On 401 error, token is automatically refreshed
8. If refresh fails, user is redirected to login

## Error Handling

- API errors are caught and displayed to users
- Network errors trigger error messages
- Authentication errors redirect to login
- Form validation prevents invalid submissions

## Security Features

- JWT-based authentication
- Protected routes require authentication
- Auto token refresh prevents session expiry
- Tokens stored securely in localStorage
- CORS configured to only allow localhost:3000

## Future Enhancements

- [ ] Email template drag-and-drop editor
- [ ] Advanced analytics charts and graphs
- [ ] Campaign scheduling calendar
- [ ] Contact segmentation and targeting
- [ ] A/B testing interface
- [ ] Dark mode support
- [ ] Mobile app version
- [ ] Real-time notifications
- [ ] Bulk contact operations
- [ ] Email preview across devices

## Troubleshooting

**Blank Page**: Check browser console for errors, ensure backend is running

**API Errors**: Verify backend URL in .env, check backend is running on correct port

**Authentication Issues**: Clear localStorage, log out and log back in

**Styling Not Applied**: Ensure CSS files are imported correctly

## Support

For issues or questions, refer to the backend documentation or contact the development team.
