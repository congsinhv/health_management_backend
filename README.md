# Health Management API

A modern FastAPI application for health management with PostgreSQL database and raw SQL queries.

## 🚀 Features

- **FastAPI** - Modern, fast web framework for building APIs
- **PostgreSQL** - Robust relational database with asyncpg for async operations
- **Raw SQL Queries** - Direct database control for optimal performance
- **Docker Ready** - Complete containerization setup
- **Authentication** - JWT-based user authentication
- **Database Migrations** - Alembic for schema management
- **Testing** - Comprehensive test suite with pytest
- **Type Safety** - Full Python type hints and Pydantic validation

## 📁 Project Structure

```
health_management/
├── app/
│   ├── main.py                 # FastAPI entrypoint
│   ├── config.py               # Configuration settings
│   ├── utils.py                # Utility functions
│   ├── db/
│   │   ├── database.py         # Database connection pool
│   │   └── user.py            # User database operations
│   ├── api/
│   │   └── user.py            # User API endpoints
│   ├── services/
│   │   └── user.py            # Business logic layer
│   └── schemas/
│       ├── base.py            # Base Pydantic models
│       └── user.py            # User schemas
├── tests/                      # Test suite
│   ├── conftest.py            # Test configuration
│   └── test_user.py           # User tests
├── scripts/
│   ├── alembic.ini            # Alembic configuration
│   ├── init_db.sql            # Database initialization
│   └── migrations/            # Database migration scripts
├── docker-compose.yml          # Development environment
├── Dockerfile                 # Application container
├── requirements.txt           # Python dependencies
└── README.md                  # This file
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

- `POST /api/v1/users/` - Create new user
- `GET /api/v1/users/` - List all users (paginated)
- `GET /api/v1/users/{id}` - Get specific user
- `PUT /api/v1/users/{id}` - Update user
- `DELETE /api/v1/users/{id}` - Delete user
- `POST /api/v1/users/login` - User authentication
- `GET /health` - Health check endpoint

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

- `DATABASE_URL` - PostgreSQL connection string
- `SECRET_KEY` - JWT signing key (change in production!)
- `DEBUG` - Enable/disable debug mode
- `LOG_LEVEL` - Logging level (DEBUG, INFO, WARNING, ERROR)

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
