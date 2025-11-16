# Health Management API

A modern FastAPI application for health management with intelligent Q&A capabilities powered by Vietnamese sentence transformers (SBERT).

## Overview

Health Management API provides accessible Vietnamese health information through semantic search and AI-powered summarization. The system supports conversation-based interactions, comprehensive user management, and real-time health question answering.

## Key Features

- **Intelligent Q&A System** - Vietnamese semantic search using SBERT with AI summarization
- **Real-Time Streaming** - Server-Sent Events for progressive AI response delivery
- **Conversation Management** - History tracking, search, tagging, and pinning
- **Message Versioning** - Track edit history and create message branches
- **User Authentication** - JWT + OAuth (Google) with email verification
- **File Storage** - Google Cloud Storage integration
- **Performance Optimization** - Optional Redis caching and materialized views
- **Security Hardening** - Rate limiting, security headers, and comprehensive monitoring
- **Comprehensive Testing** - 80%+ test coverage with pytest
- **Production Ready** - Docker, Cloud Run, Terraform infrastructure

## Technology Stack

- **Backend**: FastAPI 0.115.0, Python 3.13
- **Database**: PostgreSQL 15+ with asyncpg
- **ML**: sentence-transformers 5.1.2 (Vietnamese SBERT)
- **AI**: OpenAI API (GPT-4o-mini) with streaming support
- **Streaming**: Server-Sent Events (SSE) for real-time responses
- **Cloud**: Google Cloud Platform (Cloud Run, GCS, Secret Manager)
- **Cache**: Redis (optional)
- **Testing**: pytest with 80%+ coverage
- **IaC**: Terraform for infrastructure

## Quick Start

### Prerequisites

- Python 3.13+
- PostgreSQL 15+
- Docker & Docker Compose (optional)
- Google Cloud account (for deployment)

### Local Development Setup

1. **Clone and setup environment**:
```bash
git clone <repository-url>
cd health_management
python3.13 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

2. **Configure environment**:
```bash
cp .env.example .env
# Edit .env with your database credentials and settings
```

3. **Initialize database**:
```bash
# Create database
createdb health_management

# Run migrations
cd scripts
alembic upgrade head
```

4. **Run application**:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```

5. **Access API**:
- API: http://localhost:8080
- Docs: http://localhost:8080/docs
- ReDoc: http://localhost:8080/redoc

### Docker Development

1. **Setup**:
```bash
cp .env.example .env
# Edit .env with database connection
```

2. **Start services**:
```bash
# Development mode with hot reload
docker-compose -f docker-compose.dev.yml up

# Production mode
docker-compose up -d
```

3. **View logs**:
```bash
docker-compose logs -f app
```

## Project Structure

```
health_management/
├── app/                     # Application code
│   ├── api/                 # FastAPI routers (endpoints)
│   ├── services/            # Business logic layer
│   ├── db/                  # Database repositories
│   ├── schemas/             # Pydantic models
│   ├── auth/                # Authentication
│   ├── utils/               # Utilities (GCS, etc.)
│   ├── main.py              # App entry point
│   └── config.py            # Settings
├── tests/                   # Test suite (integration, unit, repository)
├── scripts/                 # Migrations and utilities
├── terraform/               # Infrastructure as code
├── docs/                    # Detailed documentation
├── docker-compose.yml       # Production setup
├── Dockerfile               # Container image
└── requirements.txt         # Python dependencies
```

## API Endpoints

### Authentication
- `POST /api/v1/users/login` - User login
- `POST /api/v1/users/` - User registration
- `POST /api/v1/auth/verify-email` - Email verification
- `POST /api/v1/auth/reset-password` - Password reset
- `GET /api/v1/auth/google` - Google OAuth
- `POST /api/v1/auth/google/callback` - OAuth callback

### Q&A
- `POST /api/v1/qa/ask` - Ask health question (requires auth)
- `POST /api/v1/qa/ask-stream` - Ask health question with streaming response (SSE)
- `GET /api/v1/qa/health` - Q&A service health check

### Conversations
- `GET /api/v1/conversations/` - List conversations
- `POST /api/v1/conversations/` - Create conversation
- `GET /api/v1/conversations/{id}` - Get conversation
- `PATCH /api/v1/conversations/{id}` - Update conversation
- `DELETE /api/v1/conversations/{id}` - Delete conversation
- `GET /api/v1/conversations/search` - Search conversations
- `POST /api/v1/conversations/{id}/pin` - Pin/unpin conversation

### Messages
- `GET /api/v1/conversations/{id}/messages` - List messages
- `POST /api/v1/conversations/{id}/messages` - Create message
- `PUT /api/v1/conversations/{id}/messages/{msg_id}` - Update message
- `DELETE /api/v1/conversations/{id}/messages/{msg_id}` - Delete message

### Versions
- `GET /api/v1/conversations/{id}/messages/{msg_id}/versions` - List versions
- `GET /api/v1/conversations/{id}/messages/{msg_id}/versions/{version_id}` - Get version
- `POST /api/v1/conversations/{id}/messages/{msg_id}/versions/{version_id}/restore` - Restore version

### Users
- `GET /api/v1/users/` - List users (admin)
- `GET /api/v1/users/{id}` - Get user
- `PUT /api/v1/users/{id}` - Update user
- `DELETE /api/v1/users/{id}` - Delete user

### File Upload
- `POST /api/v1/upload` - Upload file to GCS

### Health & Performance
- `GET /health` - Application health check
- `GET /api/v1/performance/cache` - Cache statistics
- `GET /api/v1/performance/database` - Database statistics

## Testing

Run the test suite:

```bash
# All tests
pytest

# With coverage report
pytest --cov=app --cov-report=html

# Specific test types
pytest tests/integration/    # Integration tests
pytest tests/unit/           # Unit tests
pytest tests/repository/     # Repository tests

# Specific test file
pytest tests/integration/test_qa_api.py -v
```

Current coverage: **80%+**

## Configuration

Key environment variables (see `.env.example` for complete list):

```bash
# Application
APP_NAME=Health Management API
DEBUG=false
LOG_LEVEL=INFO

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/health_management

# Security
SECRET_KEY=your-secret-key-change-in-production
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Q&A Service
QA_ENABLED=true
QA_MODEL_PATH=./models/vietnamese-sbert
QA_THRESHOLD=0.55

# OpenRouter AI
OPENROUTER_API_KEY=your-api-key
OPENROUTER_MODEL=openai/gpt-4o-mini

# Google Cloud
GCP_PROJECT_ID=your-project-id
GCP_MODEL_BUCKET=your-models-bucket
GCP_PUBLIC_BUCKET=your-public-bucket

# OAuth (Optional)
GOOGLE_CLIENT_ID=your-client-id
GOOGLE_CLIENT_SECRET=your-client-secret

# Email (Optional)
MAIL_SERVER=smtp.gmail.com
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password

# Redis Cache (Optional)
ENABLE_REDIS_CACHE=false
REDIS_URL=redis://localhost:6379/0
```

## Deployment

### Production Checklist

1. **Environment Variables**:
   - Set `DEBUG=false`
   - Use strong `SECRET_KEY`
   - Configure production `DATABASE_URL`
   - Set `LOG_LEVEL=INFO`

2. **Database**:
   - Run migrations: `alembic upgrade head`
   - Enable SSL connections
   - Set up automated backups
   - Configure connection pooling

3. **Security**:
   - Enable HTTPS
   - Configure CORS origins
   - Rotate secrets regularly
   - Enable rate limiting (if available)

4. **Performance**:
   - Enable Redis caching
   - Refresh materialized views
   - Monitor query performance
   - Set appropriate connection pool sizes

### Deploy to Google Cloud Run

Using Terraform:

```bash
cd terraform
terraform init
terraform plan -var-file=environments/prod/terraform.tfvars
terraform apply -var-file=environments/prod/terraform.tfvars
```

Manual deployment:

```bash
# Build and push image
docker build -t gcr.io/PROJECT_ID/health-api .
docker push gcr.io/PROJECT_ID/health-api

# Deploy to Cloud Run
gcloud run deploy health-api \
  --image gcr.io/PROJECT_ID/health-api \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated
```

### CI/CD

The project includes Jenkinsfile for automated deployments:
- Build and test on commit
- Deploy to Cloud Run on merge to main
- Run database migrations separately
- Smoke tests after deployment

## Database Management

### Migrations

```bash
cd scripts

# Create new migration
alembic revision --autogenerate -m "Description of changes"

# Run migrations
alembic upgrade head

# Rollback last migration
alembic downgrade -1

# Check current version
alembic current

# View migration history
alembic history
```

### Search Index Maintenance

```bash
# Refresh materialized view for search
python scripts/maintain_search_index.py
```

## Architecture

The application follows clean architecture with clear separation of concerns:

**API Layer** (`app/api/`) → HTTP endpoints and request/response handling

**Service Layer** (`app/services/`) → Business logic and orchestration

**Repository Layer** (`app/db/`) → Database operations with raw SQL

**Schema Layer** (`app/schemas/`) → Data validation and serialization

See [`docs/system-architecture.md`](docs/system-architecture.md) for detailed architecture documentation.

## Documentation

Comprehensive documentation is available in the `docs/` directory:

- **[Project Overview & PDR](docs/project-overview-pdr.md)** - Project goals, features, requirements, and success criteria
- **[Codebase Summary](docs/codebase-summary.md)** - Complete codebase structure, components, and technology stack
- **[Code Standards](docs/code-standards.md)** - Coding conventions, architecture patterns, and best practices
- **[System Architecture](docs/system-architecture.md)** - High-level architecture, data flows, and deployment infrastructure

## Development Guidelines

### Code Quality

```bash
# Format code
black app/ tests/

# Sort imports
isort app/ tests/

# Type checking
mypy app/

# Linting
flake8 app/ tests/
```

### Contributing

1. Create feature branch: `git checkout -b feature/feature-name`
2. Make changes and add tests
3. Ensure tests pass: `pytest`
4. Check code quality: `black`, `isort`, `flake8`
5. Commit with clear message
6. Push and create pull request

### Code Review Checklist

- [ ] Code follows style guide (PEP 8)
- [ ] All functions have type hints
- [ ] Tests included and passing (>80% coverage)
- [ ] No security vulnerabilities
- [ ] Documentation updated
- [ ] Database migrations included (if needed)

## Performance Considerations

- **Database**: Connection pooling, indexes, materialized views
- **Caching**: Optional Redis for conversation lists and search results
- **Async**: Full async/await for non-blocking I/O
- **Model Loading**: SBERT model loaded once at startup
- **Search**: In-memory embeddings for fast similarity search

## Security Features

- **Authentication**: JWT tokens with expiration
- **Password**: Bcrypt hashing (cost factor 12)
- **OAuth**: Google social login
- **SQL Injection**: Parameterized queries only
- **CORS**: Configurable allowed origins
- **Audit**: Authentication event logging
- **Secrets**: Environment variables and Secret Manager

## Monitoring & Logging

- **Structured Logging**: JSON format with levels (DEBUG, INFO, WARNING, ERROR)
- **Health Checks**: `/health` endpoint for service monitoring
- **Performance Metrics**: Cache and database statistics endpoints
- **Cloud Logging**: Integrated with GCP Cloud Logging
- **Alerts**: Configure GCP monitoring alerts

## Known Limitations

- Vietnamese language only (Q&A service)
- OpenRouter API dependency for AI summarization
- PostgreSQL-specific features (JSONB, tsvector)
- Single language model (no multi-language support)
- Synchronous model loading at startup

## Troubleshooting

### Database Connection Issues

```bash
# Check PostgreSQL is running
pg_isready -h localhost -p 5432

# Test connection
psql -h localhost -U postgres -d health_management

# Check pool status
curl http://localhost:8080/api/v1/performance/database
```

### Q&A Service Not Available

1. Check `QA_ENABLED=true` in `.env`
2. Verify model files exist in `./models/vietnamese-sbert/`
3. Check GCS credentials if auto-download enabled
4. View logs: `docker-compose logs -f app`

### Redis Cache Issues

1. Check Redis is running: `redis-cli ping`
2. Verify `ENABLE_REDIS_CACHE=true` in `.env`
3. Check `REDIS_URL` configuration
4. View cache stats: `curl http://localhost:8080/api/v1/performance/cache`

## License

[Add your license here]

## Support

For issues, questions, or contributions:
- Create an issue in the repository
- Review documentation in `docs/` directory
- Check API documentation at `/docs` endpoint

## Acknowledgments

Built with FastAPI, PostgreSQL, and Vietnamese SBERT for semantic search.
