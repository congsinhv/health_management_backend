# Enhanced Authentication Setup Guide

## Overview

This document describes the enhanced authentication system implemented in the Health Management API, including Google OAuth integration, email verification, and password reset functionality.

## Features Implemented

### ✅ Core Authentication
- **JWT-based authentication** with access and refresh tokens
- **Password hashing** using bcrypt
- **Protected routes** with middleware
- **User session management**

### ✅ Email Verification
- **Email verification** for new user registrations
- **Resend verification** functionality
- **HTML email templates** with professional styling
- **Token-based verification** with expiration

### ✅ Password Reset
- **Password reset requests** via email
- **Secure token-based reset** process
- **Password change** for authenticated users
- **Email notifications** with reset links

### ✅ Google OAuth Integration
- **Google OAuth 2.0** authentication flow
- **Account linking** for existing users
- **Profile picture sync** from Google
- **Automatic email verification** for OAuth users

### ✅ Security Features
- **Refresh token rotation**
- **Token expiration management**
- **Email enumeration protection**
- **Secure password policies**
- **CORS configuration**

## Database Schema Changes

The following tables and fields have been added:

### Enhanced Users Table
```sql
-- New fields added to users table
ALTER TABLE users ADD COLUMN google_id VARCHAR(255) UNIQUE;
ALTER TABLE users ADD COLUMN provider VARCHAR(50) DEFAULT 'local';
ALTER TABLE users ADD COLUMN avatar_url VARCHAR(500);
ALTER TABLE users ADD COLUMN email_verified BOOLEAN DEFAULT FALSE;
ALTER TABLE users ADD COLUMN email_verification_token VARCHAR(255) UNIQUE;
ALTER TABLE users ADD COLUMN email_verification_sent_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE users ADD COLUMN password_reset_token VARCHAR(255) UNIQUE;
ALTER TABLE users ADD COLUMN password_reset_sent_at TIMESTAMP WITH TIME ZONE;
```

### New Tables
```sql
-- Refresh tokens table
CREATE TABLE refresh_tokens (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(255) UNIQUE NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    revoked BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Authentication audit log
CREATE TABLE auth_logs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    event_type VARCHAR(50) NOT NULL,
    ip_address INET,
    user_agent TEXT,
    success BOOLEAN DEFAULT TRUE,
    details JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

## Environment Configuration

Create a `.env` file with the following configuration:

```bash
# Database Configuration
DATABASE_URL=postgresql://username:password@localhost:5432/health_management

# Security Settings
SECRET_KEY=your-secret-key-here-please-generate-a-secure-one
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=30

# Email Configuration (Optional - for email verification and password reset)
MAIL_USERNAME=your-email@example.com
MAIL_PASSWORD=your-email-password
MAIL_FROM=your-email@example.com
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_TLS=true
MAIL_SSL=false

# Google OAuth Configuration (Optional)
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
GOOGLE_REDIRECT_URI=http://localhost:8000/api/v1/auth/google/callback

# Application Settings
APP_NAME=Health Management API
APP_VERSION=1.0.0
DEBUG=true
LOG_LEVEL=INFO

# API Settings
API_V1_PREFIX=/api/v1

# CORS Settings
CORS_ORIGINS=["*"]
CORS_ALLOW_CREDENTIALS=true
```

## Setup Instructions

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Database Setup

```bash
# Apply the authentication schema updates using Alembic
cd scripts
alembic upgrade head
```

### 3. Google OAuth Setup (Optional)

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the Google+ API
4. Create OAuth 2.0 credentials
5. Add authorized redirect URIs:
   - `http://localhost:8000/api/v1/auth/google/callback`
   - Your frontend callback URL
6. Copy the Client ID and Client Secret to your `.env` file

### 4. Email Configuration (Optional)

For Gmail:
1. Enable 2-factor authentication
2. Generate an app-specific password
3. Use your Gmail address and app password in the configuration

### 5. Start the Application

```bash
python -m app.main
```

## API Endpoints

### Authentication Endpoints (`/api/v1/auth/`)

| Method | Endpoint | Description | Authentication Required |
|--------|----------|-------------|------------------------|
| POST | `/verify-email` | Verify email with token | No |
| GET | `/verify-email?token=<token>` | Verify email from link | No |
| POST | `/resend-verification` | Resend verification email | Yes |
| POST | `/request-password-reset` | Request password reset | No |
| POST | `/reset-password` | Reset password with token | No |
| POST | `/change-password` | Change password | Yes |
| GET | `/google/login` | Get Google OAuth URL | No |
| POST | `/google/callback` | Handle OAuth callback | No |
| GET | `/google/callback` | Handle OAuth redirect | No |
| POST | `/login-with-refresh` | Login with refresh token | No |
| GET | `/me` | Get current user info | Yes |

### Enhanced User Endpoints (`/api/v1/users/`)

- Most user management endpoints now require authentication
- Admin-only endpoints require superuser privileges
- User creation supports OAuth users

## Authentication Flow Examples

### 1. Regular User Registration

```javascript
// 1. Register user
const response = await fetch('/api/v1/users/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
        email: 'user@example.com',
        first_name: 'John',
        last_name: 'Doe',
        password: 'securepassword123'
    })
});

// 2. Check email for verification link
// 3. User clicks link or calls verify endpoint
await fetch('/api/v1/auth/verify-email', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token: 'verification-token-from-email' })
});

// 4. Login
const loginResponse = await fetch('/api/v1/users/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
        email: 'user@example.com',
        password: 'securepassword123'
    })
});
```

### 2. Google OAuth Flow

```javascript
// 1. Get authorization URL
const authResponse = await fetch('/api/v1/auth/google/login');
const { authorization_url } = await authResponse.json();

// 2. Redirect user to Google
window.location.href = authorization_url;

// 3. Handle callback with authorization code
const tokenResponse = await fetch('/api/v1/auth/google/callback', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
        code: 'authorization-code-from-google',
        state: 'optional-state-parameter'
    })
});

const { access_token, refresh_token } = await tokenResponse.json();
```

### 3. Password Reset Flow

```javascript
// 1. Request password reset
await fetch('/api/v1/auth/request-password-reset', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
        email: 'user@example.com'
    })
});

// 2. Use token from email to reset password
await fetch('/api/v1/auth/reset-password', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
        token: 'reset-token-from-email',
        new_password: 'newSecurePassword123'
    })
});
```

## Frontend Integration

### Using Access Tokens

```javascript
// Store tokens securely
localStorage.setItem('access_token', access_token);
localStorage.setItem('refresh_token', refresh_token);

// Use token in requests
const response = await fetch('/api/v1/auth/me', {
    headers: {
        'Authorization': `Bearer ${localStorage.getItem('access_token')}`
    }
});
```

### Token Refresh (Future Implementation)

```javascript
// Refresh tokens when they expire
const refreshResponse = await fetch('/api/v1/auth/refresh', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
        refresh_token: localStorage.getItem('refresh_token')
    })
});
```

## Security Considerations

1. **HTTPS Only**: Use HTTPS in production
2. **Secure Token Storage**: Store tokens securely on the client
3. **Token Rotation**: Implement refresh token rotation
4. **Rate Limiting**: Add rate limiting for auth endpoints
5. **Email Verification**: Require email verification for sensitive operations
6. **Password Policies**: Enforce strong password requirements

## Testing

Test the authentication system:

```bash
# Run tests
python -m pytest app/tests/

# Test specific auth functionality
python -m pytest app/tests/test_auth.py
```

## Database Migrations with Alembic

This project uses Alembic for database schema management. Here are the key commands:

### Creating New Migrations

```bash
cd scripts

# Create a new migration file
alembic revision -m "description_of_changes"

# Create with autogenerate (if you have SQLAlchemy models)
alembic revision --autogenerate -m "description_of_changes"
```

### Running Migrations

```bash
cd scripts

# Apply all pending migrations
alembic upgrade head

# Apply migrations up to a specific revision
alembic upgrade <revision_id>

# Downgrade to previous revision
alembic downgrade -1

# Downgrade to specific revision
alembic downgrade <revision_id>
```

### Migration History

```bash
cd scripts

# Show current migration status
alembic current

# Show migration history
alembic history

# Show pending migrations
alembic heads
```

### Available Migrations

- **`cde7763a63b8`**: Enhanced authentication support with OAuth, email verification, password reset, refresh tokens, and audit logging

## Troubleshooting

### Common Issues

1. **Email not sending**: Check SMTP configuration and credentials
2. **OAuth not working**: Verify Google OAuth setup and redirect URIs
3. **Database errors**: Ensure schema updates have been applied
4. **Token errors**: Check SECRET_KEY configuration

### Debug Mode

Enable debug mode in `.env`:
```bash
DEBUG=true
LOG_LEVEL=DEBUG
```

## Next Steps

This authentication system provides a solid foundation. Consider implementing:

1. **Rate limiting** for authentication endpoints
2. **Account lockout** after failed attempts
3. **Multi-factor authentication** (2FA/MFA)
4. **Session management** improvements
5. **Audit logging** enhancements
6. **Social login** for other providers (Facebook, Twitter, etc.)

## Support

For questions or issues, please refer to the API documentation at `/docs` when running in debug mode.

