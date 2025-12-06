# Health Management API

A production-ready FastAPI system for health management with Vietnamese semantic search (SBERT), AI-powered Q&A, health predictions, and conversation management.

**For Claude Code Users:** See [CLAUDE.md](./CLAUDE.md) for development commands, architecture patterns, and critical implementation details.

---

## Quick Overview

VHealth Backend delivers intelligent Vietnamese health information through semantic search, AI summarization, and persistent conversation tracking.

**Key Capabilities**:
- Semantic Q&A with SBERT + OpenAI streaming (SSE)
- Health risk predictions with recommendations
- Conversation management with full-text search
- Message versioning and branching
- JWT + Google OAuth authentication
- Redis optional caching (40-70% latency reduction)
- PDF report generation
- Email notifications (verification, password reset)
- Production deployment on Cloud Run (Terraform)

---

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Framework | FastAPI 0.115.0, Python 3.13 |
| Database | PostgreSQL 15+, asyncpg |
| Cache | Redis (optional) |
| ML/NLP | SBERT 5.1.2 (Vietnamese) |
| AI | OpenAI API (gpt-4o-mini) |
| PDF | WeasyPrint + Vietnamese fonts |
| Cloud | GCP (Cloud Run, SQL, GCS) |
| Testing | pytest (80%+ coverage) |
| IaC | Terraform |

---

## Quick Start

### Local Development

```bash
# Setup environment
python3.13 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your settings

# Initialize database
cd scripts && alembic upgrade head && cd ..

# Run application
uvicorn app.main:app --reload --host 0.0.0.0 --port 8080

# Access at http://localhost:8080
# Docs: http://localhost:8080/docs
```

### Docker Development

```bash
# Development with hot reload
docker-compose -f docker-compose.dev.yml up

# Production
docker-compose up -d

# View logs
docker-compose logs -f app
```

---

## Testing

```bash
# Run all tests
pytest

# With coverage
pytest --cov=app --cov-report=html

# Specific test types
pytest tests/integration/     # API endpoint tests
pytest tests/unit/            # Service logic tests
pytest tests/repository/      # Database tests

# Current coverage: 80%+
```

---

## Configuration

**Key Environment Variables**:

```bash
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/health_management

# Security
SECRET_KEY=your-secret-key-change-in-production

# Q&A Service
QA_ENABLED=true
QA_THRESHOLD=0.55

# OpenAI
OPENAI_API_KEY=your-api-key

# Redis (optional)
ENABLE_REDIS_CACHE=true
REDIS_URL=redis://localhost:6379/0

# Google Cloud
GCP_PROJECT_ID=your-project-id
GCP_MODEL_BUCKET=your-models-bucket

# OAuth (optional)
GOOGLE_CLIENT_ID=your-client-id
GOOGLE_CLIENT_SECRET=your-client-secret

# Email (optional)
MAIL_SERVER=smtp.gmail.com
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password
```

See `.env.example` for complete list.

---

## API Endpoints

### Authentication (8 endpoints)
- `POST /api/v1/users/` - Register
- `POST /api/v1/users/login` - Login
- `POST /api/v1/auth/verify-email` - Verify email
- `POST /api/v1/auth/reset-password` - Reset password
- `GET /api/v1/auth/google` - Google OAuth
- `POST /api/v1/auth/google/callback` - OAuth callback

### Q&A (3 endpoints)
- `POST /api/v1/qa/ask` - Ask question (JSON)
- `POST /api/v1/qa/ask-stream` - Ask question (SSE stream)
- `GET /api/v1/qa/health` - Q&A service health

### Conversations (7 endpoints)
- `GET /api/v1/conversations/` - List
- `POST /api/v1/conversations/` - Create
- `GET /api/v1/conversations/{id}` - Get
- `PATCH /api/v1/conversations/{id}` - Update
- `DELETE /api/v1/conversations/{id}` - Delete
- `GET /api/v1/conversations/search` - Search
- `POST /api/v1/conversations/{id}/pin` - Pin/unpin

### Messages (6 endpoints)
- `GET /api/v1/conversations/{id}/messages` - List
- `POST /api/v1/conversations/{id}/messages` - Create
- `PUT /api/v1/conversations/{id}/messages/{msg_id}` - Update
- `DELETE /api/v1/conversations/{id}/messages/{msg_id}` - Delete
- `GET /api/v1/conversations/{id}/messages/{msg_id}/versions` - Version history
- `POST /api/v1/conversations/{id}/messages/{msg_id}/versions/{version_id}/restore` - Restore version

### Predictions (3 endpoints)
- `POST /api/v1/predict/` - Create prediction
- `GET /api/v1/predict/{id}` - Get prediction
- `POST /api/v1/predict/{id}/pdf` - Generate PDF

### Users (4 endpoints)
- `GET /api/v1/users/` - List (admin)
- `GET /api/v1/users/{id}` - Get
- `PUT /api/v1/users/{id}` - Update
- `DELETE /api/v1/users/{id}` - Delete

### Health & Performance
- `GET /health` - Overall health
- `GET /api/v1/cache/health` - Cache health
- `GET /api/v1/performance/cache` - Cache stats
- `GET /api/v1/performance/database` - DB pool stats

See `/docs` for auto-generated interactive API documentation.

---

## Architecture

```
API Layer (app/api/)
    ↓ Request validation & response serialization
Service Layer (app/services/)
    ↓ Business logic, external integrations, caching
Repository Layer (app/db/)
    ↓ Raw SQL with asyncpg (parameterized queries)
PostgreSQL Database
```

**Key Components**:
- **Q&A Service**: SBERT semantic search + OpenAI summarization
- **Conversation Service**: CRUD with full-text search (tsvector)
- **Message Service**: Versioning and branching support
- **Cache Service**: Redis with graceful fallback
- **Predict Service**: Scikit-learn ML models
- **PDF Service**: WeasyPrint HTML to PDF
- **Email Service**: SMTP + Jinja2 templates
- **Auth**: JWT tokens, OAuth 2.0

---

## Performance

### Caching Impact (Redis Enabled)
- Q&A responses: 2-5s → <50ms (95% reduction)
- Conversation operations: 100-200ms → <50ms (50-75% reduction)
- User data: 50-100ms → <20ms (60-80% reduction)

### Performance Targets
- API p95 latency: <200ms
- Cache hit rate: >60%
- Model loading: <30s (non-blocking)
- Database queries: <50ms

---

## Database

**Core Tables**:
- `users` - User accounts with soft deletes
- `conversations` - Chat history with full-text search (tsvector)
- `messages` - Messages (partitioned by date)
- `message_versions` - Version history
- `predictions` - Health predictions
- `auth_logs` - Authentication events

**Features**:
- JSONB for flexible metadata
- tsvector for full-text search
- Message table partitioning (monthly)
- Soft deletes (deleted_at column)
- Parameterized queries (SQL injection prevention)

---

## Security

- **Authentication**: JWT tokens (30min) + refresh tokens (30days)
- **Password**: Bcrypt hashing (cost factor 12)
- **Queries**: Parameterized only ($1, $2) - no SQL injection
- **Headers**: HSTS, CSP, X-Frame-Options
- **OAuth**: Google social login
- **Rate Limiting**: 3 concurrent SSE, 60 req/min per user
- **Audit**: Auth event logging
- **Secrets**: Environment variables + GCP Secret Manager

---

## Deployment

### Prerequisites
- Terraform >= 1.5
- Google Cloud account
- gcloud CLI configured

### Deploy to Cloud Run

```bash
cd terraform

# Test environment
terraform init -backend-config=backend-config.test
terraform plan -var-file=environments/test.tfvars -out=tfplan
terraform apply tfplan

# Production
terraform init -backend-config=backend-config.prod
terraform plan -var-file=environments/prod.tfvars -out=tfplan
terraform apply tfplan
```

### CI/CD
- Jenkins pipeline with automated testing
- Docker multi-stage build
- Artifact Registry integration
- Automated smoke tests
- Cloud Run deployment

See `docs/deployment-guide.md` for detailed instructions.

---

## Database Migrations

```bash
cd scripts

# Create migration
alembic revision --autogenerate -m "Description"

# Apply migration
alembic upgrade head

# Rollback
alembic downgrade -1

# View history
alembic history
```

---

## Project Structure

```
app/                    # Application code (5,350 LOC)
├── api/               # FastAPI routers (8 modules)
├── services/          # Business logic (13+ modules)
├── db/               # Data access (9 repositories)
├── schemas/          # Pydantic models (8 files)
├── auth/             # JWT & dependencies
├── core/             # Centralized utilities
├── middleware/       # Security headers, rate limiting
├── utils/            # GCS, metrics, helpers
├── templates/        # Email & PDF templates
├── main.py          # FastAPI app entry point
├── config.py        # Settings
├── exceptions.py    # Error hierarchy
└── constants.py     # Enums

tests/                  # Test suite (80%+ coverage)
├── integration/       # API endpoint tests
├── unit/             # Service logic tests
├── repository/       # Database tests
└── conftest.py      # Fixtures

scripts/               # Database & utilities
├── migrations/       # Alembic migration files
└── maintain_search_index.py

terraform/            # Infrastructure as Code
├── main.tf           # Core orchestration
├── modules/          # GCP modules
└── environments/     # Test/prod configs

docs/                 # Comprehensive documentation
├── project-overview-pdr.md
├── codebase-summary.md
├── code-standards.md
├── system-architecture.md
├── deployment-guide.md
└── project-roadmap.md
```

---

## Documentation

**Comprehensive documentation in `docs/` directory**:

- **[Project Overview & PDR](docs/project-overview-pdr.md)** - Vision, requirements, features, roadmap
- **[Codebase Summary](docs/codebase-summary.md)** - Directory structure, modules, patterns
- **[Code Standards](docs/code-standards.md)** - Conventions, best practices, Git workflow
- **[System Architecture](docs/system-architecture.md)** - Design, components, data flows
- **[Deployment Guide](docs/deployment-guide.md)** - GCP, Docker, CI/CD, troubleshooting
- **[Project Roadmap](docs/project-roadmap.md)** - Phase status, planned features, metrics

---

## Development

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

### Git Workflow

```bash
# Create feature branch
git checkout -b feature/feature-name

# Make changes, commit with clear message
git commit -m "feat: Add new feature description"

# Push and create pull request
git push origin feature/feature-name

# On approval: merge to develop
```

---

## Contributing

1. Fork repository
2. Create feature branch: `git checkout -b feature/name`
3. Commit changes: `git commit -m "feat: Description"`
4. Push to branch: `git push origin feature/name`
5. Create pull request

**PR Checklist**:
- [ ] Code follows PEP 8
- [ ] Full type hints
- [ ] Tests pass (80%+ coverage)
- [ ] No security issues
- [ ] Documentation updated
- [ ] Database migrations included (if needed)

---

## Known Issues

- Vietnamese Q&A only (single-language support)
- OpenAI API dependency (no fallback)
- PostgreSQL-specific features (JSONB, tsvector)
- Synchronous model loading at startup
- Font dependencies for PDF generation

---

## Troubleshooting

**Q&A service not responding**:
- Check `QA_ENABLED=true` in `.env`
- Verify model files exist
- Check logs: `docker-compose logs -f app`

**Database connection timeout**:
- Verify PostgreSQL is running
- Check `DATABASE_URL` is correct
- Test connection: `psql $DATABASE_URL`

**Redis cache not working**:
- Check Redis is running: `redis-cli ping`
- Verify `ENABLE_REDIS_CACHE=true`
- Check `REDIS_URL` is correct

**Memory/performance issues**:
- Check API latency: `curl -w "@curl-format.txt" -o /dev/null -s https://api.example.com/health`
- Monitor cache hit rate: `curl http://localhost:8080/api/v1/performance/cache`
- Review slow queries: `gcloud sql operations list --instance=health-db`

---

## License

[Add your license here]

## Support

For issues, questions, or contributions:
- Create GitHub issue
- Review documentation in `docs/` directory
- Check API docs at `/docs` endpoint
- See CLAUDE.md for development guidance

---

## Acknowledgments

Built with FastAPI, PostgreSQL, SBERT, and WeasyPrint.
Deployed on Google Cloud Platform with Terraform.

