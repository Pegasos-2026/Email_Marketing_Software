# Email Marketing Software

A complete, production-ready email marketing application with Django REST API backend and React TypeScript frontend.

## Features

- **User Authentication**: JWT-based secure authentication system
- **Campaign Management**: Create, schedule, and send email campaigns
- **Email Templates**: Design and reuse email templates with HTML editor
- **Contact Management**: Import, organize, and manage contact lists
- **Analytics & Reporting**: Track opens, clicks, and campaign performance
- **Domain Verification**: SendGrid domain authentication setup
- **Real-time Tracking**: Email open and click tracking
- **Modern UI**: Clean, responsive React interface

## Technology Stack

### Backend
- **Django 6.0**: Web framework
- **Django REST Framework**: API development
- **JWT Authentication**: Simple JWT for token-based auth
- **SQLite**: Development database
- **SendGrid**: Email delivery service
- **CORS**: Cross-origin resource sharing support

### Frontend
- **React 17**: UI framework
- **TypeScript**: Type-safe JavaScript
- **React Router**: Client-side routing
- **Axios**: HTTP client with interceptors
- **CSS Modules**: Component styling

## Quick Start

### Prerequisites
- Python 3.8+
- Node.js 14+
- SendGrid API key

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd EmailMarketingSoftware
   ```

2. **Backend Setup**
   ```bash
   # Create virtual environment
   python -m venv .venv
   .venv\Scripts\activate  # Windows
   
   # Install dependencies
   pip install -r requirements.txt
   
   # Configure environment
   cp .env.example .env
   # Edit .env with your SendGrid API key
   
   # Setup database
   python manage.py makemigrations
   python manage.py migrate
   
   # Start server
   python manage.py runserver
   ```

3. **Frontend Setup**
   ```bash
   cd email-marketing-frontend
   npm install
   npm start
   ```

4. **Access the Application**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000/api
   - Admin Panel: http://localhost:8000/admin

## Project Structure

```
EmailMarketingSoftware/
├── app/                    # Django project settings
├── accounts/               # User authentication
├── campaigns/              # Campaign management
├── emails/                 # Email sending services
├── email-marketing-frontend/# React frontend
│   ├── src/
│   │   ├── components/     # React components
│   │   ├── pages/          # Page components
│   │   ├── services/       # API service layer
│   │   ├── types/          # TypeScript definitions
│   │   └── styles/         # CSS stylesheets
│   └── package.json
├── manage.py               # Django management script
├── SETUP_GUIDE.md          # Detailed setup instructions
└── README.md               # This file
```

## API Documentation

### Authentication
- `POST /api/token/` - Login
- `POST /api/auth/register/` - Register
- `POST /api/auth/logout/` - Logout

### Campaigns
- `GET /api/campaigns/campaigns/` - List campaigns
- `POST /api/campaigns/campaigns/` - Create campaign
- `GET /api/campaigns/campaigns/{id}/` - Get campaign details

### Templates
- `GET /api/campaigns/templates/` - List templates
- `POST /api/campaigns/templates/create/` - Create template

### Contacts
- `GET /api/campaigns/contacts/` - List contacts
- `POST /api/campaigns/contacts/import/` - Import contacts

### Analytics
- `GET /api/campaigns/analytics/dashboard/` - Dashboard stats
- `GET /api/campaigns/analytics/campaign/{id}/` - Campaign analytics

## Configuration

### Environment Variables

**Backend (.env)**
```env
EMAIL_ENCRYPTION_KEY=your_encryption_key
SENDGRID_API_KEY=your_sendgrid_api_key
```

**Frontend (.env)**
```env
REACT_APP_API_BASE_URL=http://localhost:8000/api
NODE_ENV=development
```

### SendGrid Setup

1. Create a SendGrid account
2. Generate an API key
3. Verify your sender domain/email
4. Add the API key to your `.env` file

## Development

### Backend Development
```bash
# Run development server
python manage.py runserver

# Create migrations
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser
```

### Frontend Development
```bash
# Start development server
npm start

# Build for production
npm run build

# Run tests
npm test
```

### Code Style

- **Backend**: Follow Django coding standards
- **Frontend**: Use TypeScript strict mode
- **Components**: Functional components with hooks
- **API**: RESTful conventions with proper HTTP methods

## Deployment

### Production Checklist

1. **Backend**
   - Set `DEBUG = False` in settings
   - Configure production database
   - Set up static file serving
   - Configure domain and SSL
   - Set environment variables

2. **Frontend**
   - Build production assets: `npm run build`
   - Deploy to static hosting
   - Update API base URL

3. **Database**
   - Migrate to production database
   - Set up backups
   - Configure connection pooling

## Security Features

- JWT token-based authentication
- CSRF protection
- CORS configuration
- Password validation
- Token refresh mechanism
- Secure headers

## Monitoring & Analytics

- Email open tracking
- Link click tracking
- Campaign performance metrics
- Real-time analytics dashboard
- Export capabilities

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## Support

For detailed setup instructions and troubleshooting, see [SETUP_GUIDE.md](SETUP_GUIDE.md).

## License

This project is licensed under the MIT License.
