# Health Management API

A modern FastAPI application for health management with PostgreSQL database and raw SQL queries.

## 🚀 Features

- **FastAPI** - Modern, fast web framework for building APIs
- **PostgreSQL** - Robust relational database with asyncpg for async operations
- **Raw SQL Queries** - Direct database control for optimal performance
- **Docker Ready** - Complete containerization setup
- **Authentication** - JWT-based user authentication with OAuth support
- **Database Migrations** - Alembic for schema management
- **Testing** - Comprehensive test suite with pytest
- **Type Safety** - Full Python type hints and Pydantic validation
- **Q&A Service** - AI-powered health question answering with semantic search

## 📁 Project Structure

```
health_management/
├── app/
│   ├── main.py                 # FastAPI entrypoint
│   ├── config.py               # Configuration settings
│   ├── utils.py                # Utility functions
│   ├── db/
│   │   ├── database.py         # Database connection pool
│   │   ├── user.py             # User database operations
│   │   └── qa.py               # Q&A database operations
│   ├── api/
│   │   ├── user.py             # User API endpoints
│   │   ├── auth.py             # Authentication endpoints
│   │   └── qa.py               # Q&A API endpoints
│   ├── services/
│   │   ├── user.py             # Business logic layer
│   │   ├── qa_service.py       # Q&A service with SBERT
│   │   └── email.py            # Email service
│   ├── schemas/
│   │   ├── base.py             # Base Pydantic models
│   │   ├── user.py             # User schemas
│   │   └── qa.py               # Q&A schemas
│   └── auth/
│       └── dependencies.py     # Auth dependencies
├── tests/                      # Test suite
│   ├── conftest.py             # Test configuration
│   ├── test_user.py            # User tests
│   └── test_qa.py              # Q&A tests
├── models/
│   └── vietnamese-sbert/       # Vietnamese SBERT model
├── scripts/
│   ├── alembic.ini             # Alembic configuration
│   ├── init_db.sql             # Database initialization
│   └── migrations/             # Database migration scripts
├── data.xlsx                   # Q&A dataset
├── tuvung.txt                  # Vietnamese vocabulary
├── docker-compose.yml          # Development environment
├── Dockerfile                  # Application container
├── requirements.txt            # Python dependencies
└── README.md                   # This file
```

## 🛠️ Setup

### Prerequisites

- Python 3.11+
- PostgreSQL 15+
- Docker (optional, for containerized development)

### Local Development

1. **Clone and setup environment:**
   ```bash
   git clone <repository-url>
   cd health_management
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your database credentials and settings
   ```

3. **Setup database:**
   ```bash
   # Create PostgreSQL database
   createdb health_management

   # Run initial schema
   psql health_management < scripts/init_db.sql
   ```

4. **Run the application:**
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

### Docker Development

1. **Start services:**
   ```bash
   docker-compose up -d
   ```

2. **View logs:**
   ```bash
   docker-compose logs -f api
   ```

3. **Access services:**
   - API: http://localhost:8000
   - API Docs: http://localhost:8000/docs
   - PgAdmin: http://localhost:5050 (optional, use `--profile dev`)

## 🧪 Testing

Run the test suite:
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_user.py -v
```

## 📚 API Documentation

When running in development mode, interactive API documentation is available at:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Key Endpoints

#### User Management
- `POST /api/v1/users/` - Create new user
- `GET /api/v1/users/` - List all users (paginated)
- `GET /api/v1/users/{id}` - Get specific user
- `PUT /api/v1/users/{id}` - Update user
- `DELETE /api/v1/users/{id}` - Delete user

#### Authentication
- `POST /api/v1/auth/login` - User authentication
- `POST /api/v1/auth/register` - User registration
- `POST /api/v1/auth/refresh` - Refresh access token
- `POST /api/v1/auth/google` - Google OAuth login

#### Q&A Service
- `POST /api/v1/qa/ask` - Ask a health-related question
- `GET /api/v1/qa/health` - Q&A service health check
- `GET /api/v1/qa/conversations` - List conversation history
- `GET /api/v1/qa/conversations/{id}` - Get specific conversation
- `DELETE /api/v1/qa/conversations/{id}` - Delete conversation

#### Health Check
- `GET /health` - Application health check endpoint

## 🗄️ Database

### Schema

The application uses PostgreSQL with the following main table:

```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    deleted_at TIMESTAMP WITH TIME ZONE NULL
);
```

### Migrations

Database schema changes are managed with Alembic:

```bash
# Generate migration
cd scripts
alembic revision --autogenerate -m "Description of changes"

# Run migrations
alembic upgrade head

# Check migration status
alembic current
```

## 🔧 Configuration

Configuration is managed through environment variables. Key settings:

### Core Settings
- `DATABASE_URL` - PostgreSQL connection string
- `SECRET_KEY` - JWT signing key (change in production!)
- `DEBUG` - Enable/disable debug mode
- `LOG_LEVEL` - Logging level (DEBUG, INFO, WARNING, ERROR)

### Q&A Service Settings
- `QA_ENABLED` - Enable/disable Q&A service (default: true)
- `QA_GCS_BUCKET` - GCS bucket name for Q&A files (required)
- `QA_MODEL_PATH` - GCS path to SBERT model directory (default: models/vietnamese-sbert)
- `QA_DATA_PATH` - GCS path to Q&A dataset Excel file (default: data/data.xlsx)
- `QA_VOCAB_PATH` - GCS path to Vietnamese vocabulary file (default: data/tuvung.txt)
- `QA_LOCAL_CACHE_DIR` - Local cache directory for downloaded GCS files (default: /tmp/qa_cache)
- `QA_THRESHOLD` - Minimum similarity threshold for answers (default: 0.55)
- `QA_TOP_K` - Maximum number of top results to return (default: 7)
- `OPENROUTER_API_KEY` - OpenRouter API key for AI summarization
- `OPENROUTER_MODEL` - OpenRouter model to use (default: openai/gpt-4o-mini)
- `OPENROUTER_TIMEOUT` - OpenRouter API timeout in seconds (default: 30)

## 🤖 Q&A Service

The Q&A service provides AI-powered health question answering using semantic search and LLM-based summarization.

### Features

- **Semantic Search**: Uses Vietnamese SBERT model for understanding question context
- **Multi-field Answers**: Returns categorized answers from different health domains
- **AI Summarization**: Generates concise summaries using OpenRouter AI
- **Conversation History**: Stores and retrieves past Q&A interactions
- **Optional Authentication**: Works with or without user authentication

### How It Works

1. **Question Processing**: User questions are preprocessed and cleaned using Vietnamese vocabulary
2. **Semantic Matching**: SBERT model encodes the question and finds similar questions in the dataset
3. **Answer Collection**: Top-K most similar answers are collected based on similarity threshold
4. **AI Summary**: OpenRouter AI generates a concise summary from the collected answers
5. **Storage**: Conversation is saved to database for future reference

### Example Usage

```python
# Ask a question
POST /api/v1/qa/ask
{
    "question": "What are the symptoms of diabetes?",
    "threshold": 0.55,
    "top_k": 7
}

# Response
{
    "question": "What are the symptoms of diabetes?",
    "answers": {
        "Nutrition": [
            "Q: What are diabetes symptoms?\nA: Common symptoms include..."
        ]
    },
    "summary": "Diabetes symptoms typically include increased thirst, frequent urination...",
    "conversation_id": 123
}
```

### Setup Requirements

The Q&A service requires files to be stored in Google Cloud Storage (GCS).

1. **Create GCS Bucket**: Use Terraform to create the storage bucket:
   ```bash
   cd terraform
   terraform apply -var-file="dev.tfvars"
   ```

2. **Upload Files to GCS**: Upload the following to your GCS bucket:
   ```bash
   # Get bucket name from Terraform output
   BUCKET_NAME=$(terraform output -raw qa_storage_bucket_name)
   
   # Upload model files (directory structure)
   gsutil -m cp -r ./models/vietnamese-sbert gs://${BUCKET_NAME}/models/
   
   # Upload dataset and vocabulary
   gsutil cp data.xlsx gs://${BUCKET_NAME}/data/data.xlsx
   gsutil cp tuvung.txt gs://${BUCKET_NAME}/data/tuvung.txt
   
   # Verify uploads
   gsutil ls -r gs://${BUCKET_NAME}
   ```

3. **Configure Environment**: Set these environment variables:
   ```bash
   QA_GCS_BUCKET=vhealth-qa-storage-dev
   QA_MODEL_PATH=models/vietnamese-sbert
   QA_DATA_PATH=data/data.xlsx
   QA_VOCAB_PATH=data/tuvung.txt
   ```

4. **Run Database Migration**: Apply the Q&A conversations table migration:
   ```bash
   cd scripts
   alembic upgrade head
   ```

5. **Permissions**: Cloud Run service account automatically has `roles/storage.objectViewer` permission via Terraform

#### Storage Architecture

- **GCS Storage**: All Q&A files (model, dataset, vocabulary) are stored in Google Cloud Storage
- **Automatic Download**: Files are downloaded from GCS on first access and cached locally at `/tmp/qa_cache`
- **Cache Persistence**: Files remain cached for the lifetime of the container instance
- **Security**: Service account authentication (no API keys needed for GCS access)

## 🔐 Security Features

- **Password Hashing** - Bcrypt for secure password storage
- **JWT Authentication** - Token-based authentication
- **Input Validation** - Pydantic models for request validation
- **SQL Injection Protection** - Parameterized queries with asyncpg
- **CORS Configuration** - Configurable cross-origin settings

## 📦 Deployment

### Production Checklist

1. **Environment Variables:**
   ```bash
   DEBUG=false
   SECRET_KEY=<strong-random-key>
   DATABASE_URL=<production-database-url>
   LOG_LEVEL=INFO
   ```

2. **Database:**
   - Run migrations: `alembic upgrade head`
   - Set up database backups
   - Configure connection pooling

3. **Security:**
   - Use HTTPS
   - Configure proper CORS origins
   - Set up rate limiting
   - Enable database SSL

### Docker Production

```bash
# Build production image
docker build -t health-management-api .

# Run container
docker run -d \
  --name health-api \
  -p 8000:8000 \
  --env-file .env.production \
  health-management-api
```

## 🤝 Development

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

### Project Architecture

The application follows a clean architecture pattern:

1. **API Layer** (`app/api/`) - HTTP endpoints and request/response handling
2. **Service Layer** (`app/services/`) - Business logic and orchestration
3. **Data Layer** (`app/db/`) - Database operations and queries
4. **Schema Layer** (`app/schemas/`) - Data validation and serialization

This separation ensures:
- **Testability** - Each layer can be tested independently
- **Maintainability** - Clear boundaries between concerns
- **Scalability** - Easy to modify or extend individual layers

## 📝 License

[Add your license here]

## 👥 Contributing

[Add contribution guidelines here]

---

Built with ❤️ using FastAPI and PostgreSQL
