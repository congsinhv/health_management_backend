# Project Overview & Product Development Requirements (PDR)

**VHealth Backend - Health Management API**

Version: 1.0.0
Last Updated: 2025-11-25
Status: Production

---

## 1. Project Overview

### Project Name
**VHealth Backend** - Intelligent Health Management Platform with Vietnamese Language Support

### Vision
Democratize access to health information and personalized health insights for Vietnamese-speaking users through AI-powered question-answering, obesity risk prediction, and comprehensive health management tools.

### Mission
Provide accessible, accurate, and actionable health information through:
- Semantic search-powered Q&A in Vietnamese
- AI-driven health risk assessments
- Personalized diet and workout recommendations
- Comprehensive health prediction reports
- Real-time conversational health assistance

### Project Context
VHealth Backend is a production-ready FastAPI backend system deployed on Google Cloud Run, designed to serve as the backend for health management applications. It combines modern web technologies, machine learning, and cloud infrastructure to deliver high-performance health services at scale.

---

## 2. Product Development Requirements (PDR)

### 2.1 Functional Requirements

#### FR-1: Intelligent Q&A System
**Priority**: CRITICAL
**Status**: Implemented

- **FR-1.1**: Support Vietnamese language semantic search using SBERT
- **FR-1.2**: Maintain Q&A dataset with health questions and answers
- **FR-1.3**: Return top-k relevant answers (default: 7) above similarity threshold (0.55)
- **FR-1.4**: Group answers by health field category (max 5 per field)
- **FR-1.5**: Integrate OpenAI GPT-4o-mini for AI summarization
- **FR-1.6**: Support real-time streaming responses via Server-Sent Events (SSE)
- **FR-1.7**: Cache frequently asked questions (30-minute TTL)
- **FR-1.8**: Auto-download models from Google Cloud Storage

**Acceptance Criteria:**
- Semantic search returns results in <50ms (with cache)
- Similarity scores above 0.55 threshold
- Streaming responses with event-based architecture
- Graceful degradation if AI summarization unavailable

#### FR-2: Health Prediction System
**Priority**: CRITICAL
**Status**: Implemented

- **FR-2.1**: Accept user health inputs (age, weight, height, lifestyle)
- **FR-2.2**: Calculate BMI and metabolic age
- **FR-2.3**: Predict obesity risk levels (7 categories)
- **FR-2.4**: Generate personalized health recommendations
- **FR-2.5**: Create diet plans using AI
- **FR-2.6**: Create workout plans using AI
- **FR-2.7**: Store predictions in database with unique IDs
- **FR-2.8**: Generate downloadable PDF reports with Vietnamese fonts

**Acceptance Criteria:**
- Prediction accuracy >85%
- Health metrics calculated correctly (BMI, metabolic age)
- PDF generation completes in <5 seconds
- PDFs support Vietnamese characters
- Predictions stored permanently

#### FR-3: PDF Report Generation
**Priority**: HIGH
**Status**: Implemented

- **FR-3.1**: Generate professional health reports as PDFs
- **FR-3.2**: Support Vietnamese fonts (DejaVu, Noto)
- **FR-3.3**: Include health metrics, charts, and recommendations
- **FR-3.4**: Upload PDFs to Google Cloud Storage
- **FR-3.5**: Provide public URLs for download
- **FR-3.6**: Handle concurrent PDF generation (max 3 workers)

**Acceptance Criteria:**
- PDFs render correctly with Vietnamese text
- Public URLs expire after defined period
- PDF generation is non-blocking
- Proper error handling and logging

#### FR-4: User Authentication & Authorization
**Priority**: CRITICAL
**Status**: Implemented

- **FR-4.1**: JWT-based authentication with access and refresh tokens
- **FR-4.2**: Password hashing with bcrypt (cost factor 12)
- **FR-4.3**: Email verification for new accounts
- **FR-4.4**: Password reset via email
- **FR-4.5**: Google OAuth social login
- **FR-4.6**: Role-based access control (user, admin)
- **FR-4.7**: Authentication event logging
- **FR-4.8**: Token expiration (30 minutes access, 30 days refresh)

**Acceptance Criteria:**
- Secure password storage (bcrypt)
- JWT tokens validated on every request
- OAuth flow completes successfully
- Email verification required before access
- Admin endpoints protected

#### FR-5: Conversation Management
**Priority**: HIGH
**Status**: Implemented

- **FR-5.1**: Create and manage conversations
- **FR-5.2**: List conversations with pagination
- **FR-5.3**: Search conversations by content (full-text search)
- **FR-5.4**: Tag conversations for organization
- **FR-5.5**: Pin important conversations
- **FR-5.6**: Update conversation metadata
- **FR-5.7**: Soft delete conversations
- **FR-5.8**: Cache conversation lists (5-minute TTL)

**Acceptance Criteria:**
- Conversations listed in <50ms (with cache)
- Full-text search works correctly
- Tagging system functional
- Pinned conversations appear first

#### FR-6: Message Versioning & Branching
**Priority**: MEDIUM
**Status**: Implemented

- **FR-6.1**: Automatic version creation on message edits
- **FR-6.2**: Store edit history with timestamps
- **FR-6.3**: Support message branching (conversation forks)
- **FR-6.4**: Restore previous message versions
- **FR-6.5**: View version diffs
- **FR-6.6**: Track message metadata (tokens, model)

**Acceptance Criteria:**
- Versions created on every edit
- History preserved indefinitely
- Branch support functional
- Version restoration works correctly

#### FR-7: Real-Time Communication
**Priority**: MEDIUM
**Status**: Implemented

- **FR-7.1**: WebSocket support for real-time messaging
- **FR-7.2**: Connection management (connect, disconnect, reconnect)
- **FR-7.3**: Message broadcasting to conversation participants
- **FR-7.4**: Heartbeat/ping-pong for connection health
- **FR-7.5**: Automatic cleanup of stale connections (5 minutes)
- **FR-7.6**: Connection statistics and monitoring

**Acceptance Criteria:**
- WebSocket connections stable
- Messages delivered in real-time
- Stale connections cleaned up
- Health monitoring functional

#### FR-8: File Upload & Storage
**Priority**: MEDIUM
**Status**: Implemented

- **FR-8.1**: Upload files to Google Cloud Storage
- **FR-8.2**: Generate public URLs
- **FR-8.3**: Support common file types
- **FR-8.4**: File size limits (configurable)
- **FR-8.5**: Secure file access

**Acceptance Criteria:**
- Files uploaded successfully
- Public URLs accessible
- Size limits enforced

### 2.2 Non-Functional Requirements

#### NFR-1: Performance
**Priority**: CRITICAL

- **NFR-1.1**: API response time <200ms (95th percentile) without cache
- **NFR-1.2**: API response time <50ms (95th percentile) with cache
- **NFR-1.3**: Q&A search latency <5 seconds without cache
- **NFR-1.4**: Q&A search latency <50ms with cache
- **NFR-1.5**: Database connection pool: 1-20 connections
- **NFR-1.6**: Support 1000+ concurrent users
- **NFR-1.7**: Horizontal scaling via Cloud Run (auto-scaling)

**Acceptance Criteria:**
- Performance metrics monitored
- Cache hit rate >70%
- Latency SLOs met 99% of time
- Auto-scaling triggers correctly

#### NFR-2: Scalability
**Priority**: HIGH

- **NFR-2.1**: Stateless application design (Cloud Run compatible)
- **NFR-2.2**: Connection pooling for database
- **NFR-2.3**: Redis caching for performance
- **NFR-2.4**: Async/await for non-blocking I/O
- **NFR-2.5**: Auto-scaling based on CPU/memory
- **NFR-2.6**: Load balancing via Cloud Run

**Acceptance Criteria:**
- Application scales horizontally
- No session state in application
- Database connections managed efficiently
- Auto-scaling tested under load

#### NFR-3: Security
**Priority**: CRITICAL

- **NFR-3.1**: HTTPS only (TLS 1.2+)
- **NFR-3.2**: JWT token authentication
- **NFR-3.3**: Password hashing with bcrypt
- **NFR-3.4**: SQL injection prevention (parameterized queries)
- **NFR-3.5**: CORS configuration for allowed origins
- **NFR-3.6**: Security headers (HSTS, CSP, X-Frame-Options)
- **NFR-3.7**: Rate limiting (Redis-backed)
- **NFR-3.8**: Secret management via Secret Manager
- **NFR-3.9**: Audit logging for authentication events
- **NFR-3.10**: Input validation with Pydantic

**Acceptance Criteria:**
- Security audit passed
- OWASP Top 10 mitigated
- Secrets never in code/logs
- Rate limiting prevents abuse

#### NFR-4: Reliability
**Priority**: HIGH

- **NFR-4.1**: 99.9% uptime SLA
- **NFR-4.2**: Graceful degradation (cache, Q&A service)
- **NFR-4.3**: Health check endpoints
- **NFR-4.4**: Database connection retry logic
- **NFR-4.5**: Circuit breakers for external services
- **NFR-4.6**: Comprehensive error handling
- **NFR-4.7**: Rollback capability in CI/CD

**Acceptance Criteria:**
- Health checks pass consistently
- Graceful degradation tested
- Error rates <0.1%
- Rollback tested successfully

#### NFR-5: Observability
**Priority**: HIGH

- **NFR-5.1**: Structured logging (JSON format)
- **NFR-5.2**: Log levels (DEBUG, INFO, WARNING, ERROR)
- **NFR-5.3**: Request/response logging
- **NFR-5.4**: Performance metrics (Prometheus)
- **NFR-5.5**: Cache hit rate monitoring
- **NFR-5.6**: Database query performance tracking
- **NFR-5.7**: Integration with Google Cloud Logging

**Acceptance Criteria:**
- Logs searchable and structured
- Metrics collected and visualized
- Alerting configured
- Performance dashboards available

#### NFR-6: Maintainability
**Priority**: MEDIUM

- **NFR-6.1**: Test coverage >80%
- **NFR-6.2**: Code follows PEP 8 style guide
- **NFR-6.3**: Type hints on all functions
- **NFR-6.4**: Clear documentation (docstrings)
- **NFR-6.5**: Modular architecture (layered)
- **NFR-6.6**: Database migrations with Alembic
- **NFR-6.7**: Infrastructure as Code (Terraform)

**Acceptance Criteria:**
- Tests pass on every commit
- Code review checklist followed
- Documentation up to date
- Infrastructure reproducible

#### NFR-7: Portability
**Priority**: MEDIUM

- **NFR-7.1**: Docker containerization
- **NFR-7.2**: Environment-based configuration
- **NFR-7.3**: Cloud-agnostic design (where possible)
- **NFR-7.4**: Local development environment

**Acceptance Criteria:**
- Application runs in Docker
- Environment variables configure behavior
- Local development matches production

---

## 3. Key Features & Capabilities

### 3.1 Intelligent Q&A System
- **Vietnamese Language Support**: Native Vietnamese SBERT model for semantic search
- **Semantic Search**: Cosine similarity-based matching
- **AI Summarization**: GPT-4o-mini integration for context-aware summaries
- **Real-Time Streaming**: Server-Sent Events for progressive response delivery
- **Caching**: Redis-backed caching for 95% latency reduction
- **Auto-Download**: Models and data fetched from GCS automatically

### 3.2 Health Prediction Engine
- **7 Obesity Categories**: From Insufficient Weight to Obesity Type III
- **19 Features**: Comprehensive feature engineering for accuracy
- **BMI Calculation**: Automatic BMI and BMI category
- **Metabolic Age**: Calculated based on lifestyle factors
- **Personalized Recommendations**: AI-generated diet and workout plans
- **Database Storage**: Persistent prediction history
- **PDF Reports**: Professional health reports with Vietnamese fonts

### 3.3 PDF Generation
- **WeasyPrint**: HTML to PDF conversion
- **Vietnamese Fonts**: DejaVu and Noto fonts for proper rendering
- **Professional Layout**: Charts, metrics, recommendations
- **Cloud Storage**: Uploaded to GCS with public URLs
- **Concurrent Generation**: Thread pool (max 3 workers)
- **Template Engine**: Jinja2 for dynamic content

### 3.4 Authentication & Security
- **JWT Tokens**: Access and refresh tokens
- **Bcrypt Hashing**: Cost factor 12 for password security
- **Email Verification**: Required for new accounts
- **Password Reset**: Secure reset flow via email
- **Google OAuth**: Social login integration
- **RBAC**: Role-based access control (user, admin)
- **Audit Logging**: Track authentication events

### 3.5 Conversation Management
- **CRUD Operations**: Create, read, update, delete conversations
- **Full-Text Search**: PostgreSQL tsvector-based search
- **Tagging**: Organize conversations with tags
- **Pinning**: Pin important conversations
- **Pagination**: Efficient pagination for large lists
- **Caching**: Redis caching for list operations

### 3.6 Message Versioning
- **Automatic Versioning**: Every edit creates a version
- **Edit History**: Complete version history
- **Branching**: Support conversation forks
- **Restore**: Restore previous versions
- **Diffs**: Version comparison
- **Metadata**: Track tokens, model, timestamps

### 3.7 Real-Time Communication
- **WebSockets**: Bidirectional communication
- **Broadcasting**: Message delivery to participants
- **Connection Management**: Lifecycle management
- **Heartbeat**: Connection health monitoring
- **Auto-Cleanup**: Remove stale connections
- **Statistics**: Connection metrics

### 3.8 Performance Optimization
- **Redis Caching**: 40-70% latency reduction
- **Connection Pooling**: Efficient database connections
- **Async/Await**: Non-blocking I/O throughout
- **In-Memory Embeddings**: Fast semantic search
- **Thread Pools**: CPU-bound tasks (PDF generation)
- **Auto-Scaling**: Cloud Run horizontal scaling

---

## 4. Target Users & Use Cases

### 4.1 Primary Users

#### End Users (Patients/Health-Conscious Individuals)
- **Age Range**: 18-65+
- **Language**: Vietnamese speakers
- **Tech Savviness**: Moderate (mobile/web users)
- **Goals**:
  - Get health information in Vietnamese
  - Understand obesity risk
  - Receive personalized health recommendations
  - Track health conversations

#### Healthcare Providers (Future)
- **Role**: Doctors, nutritionists, trainers
- **Goals**:
  - Review patient predictions
  - Provide recommendations
  - Track patient progress

#### Administrators
- **Role**: System administrators
- **Goals**:
  - Monitor system health
  - Manage users
  - Review cache performance
  - Analyze usage patterns

### 4.2 Use Cases

#### UC-1: Ask Health Question
**Actor**: End User
**Precondition**: User is authenticated
**Flow**:
1. User submits health question in Vietnamese
2. System performs semantic search
3. System returns top relevant answers
4. System generates AI summary (optional)
5. System streams response in real-time

**Postcondition**: User receives health information

#### UC-2: Get Health Prediction
**Actor**: End User
**Precondition**: User is authenticated
**Flow**:
1. User provides health inputs (age, weight, height, lifestyle)
2. System calculates health metrics (BMI, metabolic age)
3. System predicts obesity risk level
4. System generates AI-powered recommendations
5. System stores prediction in database
6. User receives prediction with unique ID

**Postcondition**: Prediction stored, user has prediction ID

#### UC-3: Generate PDF Report
**Actor**: End User
**Precondition**: User has prediction ID
**Flow**:
1. User requests PDF for prediction
2. System retrieves prediction from database
3. System generates PDF with Vietnamese fonts
4. System uploads PDF to GCS
5. User receives public download URL

**Postcondition**: PDF available for download

#### UC-4: Manage Conversations
**Actor**: End User
**Precondition**: User is authenticated
**Flow**:
1. User creates/views conversations
2. User searches conversations by content
3. User tags/pins important conversations
4. User edits conversation messages
5. System maintains version history

**Postcondition**: Conversations organized and searchable

#### UC-5: Real-Time Chat
**Actor**: End User
**Precondition**: User is authenticated
**Flow**:
1. User connects via WebSocket
2. User sends messages in real-time
3. System broadcasts to conversation participants
4. System maintains connection health
5. User disconnects gracefully

**Postcondition**: Real-time communication successful

---

## 5. Technology Stack Overview

### 5.1 Backend Framework
- **FastAPI 0.115.0**: Modern async web framework
- **Uvicorn 0.32.0**: ASGI server with standard extras
- **Python 3.13**: Latest Python version with performance improvements

### 5.2 Database
- **PostgreSQL 15+**: Primary relational database
- **asyncpg 0.30.0**: High-performance async driver
- **Alembic 1.14.0**: Database migration tool

### 5.3 Machine Learning
- **sentence-transformers 5.1.2**: Vietnamese SBERT for semantic search
- **PyTorch 2.5.1**: ML framework (CPU optimized)
- **pandas 2.3.3**: Data processing
- **scikit-learn**: Obesity prediction model

### 5.4 AI Integration
- **OpenAI API**: GPT-4o-mini for summarization and recommendations
- **httpx-sse**: Server-Sent Events for streaming

### 5.5 Document Generation
- **WeasyPrint 62.3**: HTML to PDF conversion
- **Jinja2 3.1.2**: Template engine

### 5.6 Cloud Infrastructure (GCP)
- **Cloud Run**: Serverless container hosting
- **Cloud SQL**: Managed PostgreSQL
- **Cloud Storage**: File and model storage
- **Secret Manager**: Secrets management
- **Memorystore**: Managed Redis
- **Artifact Registry**: Docker images
- **Cloud Scheduler**: Cron jobs

### 5.7 Caching & Performance
- **Redis 5.0+**: In-memory cache
- **Connection Pooling**: Database optimization
- **Async/Await**: Non-blocking I/O

### 5.8 DevOps
- **Docker**: Containerization
- **Terraform**: Infrastructure as Code
- **Jenkins**: CI/CD pipelines
- **pytest**: Testing framework

---

## 6. Business Context & Goals

### 6.1 Business Objectives

#### Primary Objectives
1. **Accessibility**: Make health information accessible in Vietnamese
2. **Accuracy**: Provide evidence-based health predictions
3. **Engagement**: Enable conversational health assistance
4. **Scalability**: Support growing user base
5. **Performance**: Deliver fast, responsive service

#### Secondary Objectives
1. **Cost Efficiency**: Optimize cloud resource usage
2. **Maintainability**: Ensure long-term codebase health
3. **Extensibility**: Enable feature additions
4. **Reliability**: Maintain high uptime

### 6.2 Success Metrics

#### User Metrics
- **Daily Active Users (DAU)**: Target 1000+ users
- **Questions Asked**: 5000+ per day
- **Predictions Generated**: 500+ per day
- **PDF Downloads**: 200+ per day
- **User Retention**: 60%+ after 30 days

#### Performance Metrics
- **API Response Time**: <50ms (95th percentile with cache)
- **Q&A Latency**: <50ms (with cache)
- **Cache Hit Rate**: >70%
- **Uptime**: 99.9%
- **Error Rate**: <0.1%

#### Business Metrics
- **Cost per User**: <$0.10 per month
- **Infrastructure Cost**: <$500 per month (initial)
- **Model Inference Cost**: <$100 per month (OpenAI)
- **Storage Cost**: <$50 per month (GCS)

### 6.3 Risks & Mitigation

#### Technical Risks
1. **Risk**: Model download failures
   - **Mitigation**: Auto-download with retry, GCS fallback

2. **Risk**: OpenAI API downtime
   - **Mitigation**: Graceful degradation, cached summaries

3. **Risk**: Database connection exhaustion
   - **Mitigation**: Connection pooling, monitoring

4. **Risk**: Redis cache failures
   - **Mitigation**: Pass-through mode, graceful degradation

#### Business Risks
1. **Risk**: High cloud costs
   - **Mitigation**: Auto-scaling limits, cost monitoring

2. **Risk**: Low user adoption
   - **Mitigation**: User feedback, feature improvements

3. **Risk**: Data privacy concerns
   - **Mitigation**: GDPR compliance, encryption, audit logs

---

## 7. Roadmap & Future Enhancements

### Phase 1: Foundation (Completed)
- ✅ FastAPI backend setup
- ✅ PostgreSQL database
- ✅ Authentication system
- ✅ Q&A service
- ✅ Health prediction
- ✅ PDF generation
- ✅ Cloud Run deployment

### Phase 2: Optimization (Completed)
- ✅ Redis caching
- ✅ Performance optimization
- ✅ Real-time WebSockets
- ✅ Conversation management
- ✅ Message versioning
- ✅ Comprehensive testing

### Phase 3: Enhancement (In Progress)
- ✅ PDF generation with Vietnamese font support (DejaVu, Noto)
- ✅ Comprehensive documentation suite (CLAUDE.md, guides)
- ✅ Docker font configuration for production environments
- 🔄 Advanced analytics
- 🔄 User dashboard
- 🔄 Mobile app integration
- 🔄 Multi-language support
- 🔄 Enhanced AI features

### Phase 4: Scale (Planned)
- 📋 Multi-region deployment
- 📋 Advanced caching strategies
- 📋 Machine learning model updates
- 📋 Healthcare provider portal
- 📋 Integration with wearables

---

## 8. Compliance & Standards

### 8.1 Security Standards
- OWASP Top 10 compliance
- HTTPS/TLS 1.2+ only
- Secure password storage (bcrypt)
- SQL injection prevention
- Input validation (Pydantic)

### 8.2 Data Privacy
- User data encryption at rest
- Secure token management
- Audit logging
- GDPR-ready architecture
- Data retention policies

### 8.3 Code Quality
- PEP 8 style guide
- Type hints everywhere
- 80%+ test coverage
- Code review required
- Documentation standards

### 8.4 Infrastructure
- Infrastructure as Code (Terraform)
- Version control (Git)
- CI/CD pipelines (Jenkins)
- Environment separation (dev/prod)
- Backup and recovery procedures

---

## 9. Dependencies & Constraints

### 9.1 External Dependencies
- PostgreSQL 15+
- Redis 5.0+
- Google Cloud Platform
- OpenAI API
- Vietnamese SBERT model
- Python 3.13+

### 9.2 Technical Constraints
- Vietnamese language only (Q&A)
- Single-region deployment (initial)
- Cloud Run limitations (CPU-bound tasks)
- OpenAI API rate limits
- GCS storage costs

### 9.3 Business Constraints
- Budget limitations
- Resource availability
- Time-to-market pressures
- User privacy requirements
- Regulatory compliance

---

## 10. Stakeholders

### Internal Stakeholders
- **Development Team**: Build and maintain the system
- **DevOps Team**: Manage infrastructure and deployments
- **Product Manager**: Define features and priorities
- **QA Team**: Ensure quality and reliability

### External Stakeholders
- **End Users**: Primary beneficiaries of health information
- **Healthcare Providers**: Future integration partners
- **Cloud Provider (GCP)**: Infrastructure provider
- **AI Provider (OpenAI)**: AI summarization provider

---

---

## Recent Changes & Updates

### 2025-11-25
- **PDF Font Support**: Fixed PDF rendering in development and production environments by adding `fonts-dejavu-core` and `fonts-noto-core` to both Dockerfile and Dockerfile.base (lines 17-18 and 44-54 respectively). This ensures Vietnamese text renders correctly in generated health reports.
- **Documentation Update**: Created comprehensive CLAUDE.md guide for Claude Code instances with development commands, architecture patterns, and critical gotchas.
- **Initial Documentation**: Completed documentation suite including project overview, system architecture, code standards, and codebase summary.

### 2025-11-24
- **PDF Template Refinement**: Simplified PDF generation by removing template version parameter and improving BMI extraction logic in PdfGeneratorService.
- **Template Versioning**: Enhanced PDF generation system with new template version support.

---

## Appendix

### Related Documentation
- [CLAUDE.md](../CLAUDE.md) - Claude Code development guide
- [Codebase Summary](./codebase-summary.md)
- [Code Standards](./code-standards.md)
- [System Architecture](./system-architecture.md)
- [Project Roadmap](./project-roadmap.md)
- [Deployment Guide](./deployment-guide.md)
- [Redis Caching Implementation](./redis-caching-implementation.md)
- [Cache Handoff Guide](./cache-handoff-guide.md)

### References
- FastAPI Documentation: https://fastapi.tiangolo.com
- PostgreSQL Documentation: https://www.postgresql.org/docs/
- Google Cloud Documentation: https://cloud.google.com/docs
- Terraform Documentation: https://www.terraform.io/docs
- OpenAI API Documentation: https://platform.openai.com/docs
