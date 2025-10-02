# Terraform Infrastructure

This directory contains the Terraform configuration for the Health Management application infrastructure on Google Cloud Platform.

## Architecture

The infrastructure consists of:
- **Cloud SQL (PostgreSQL)**: Database with public IP access
- **Cloud Run**: Serverless application hosting
- **Artifact Registry**: Container image storage
- **Secret Manager**: Secure credential storage
- **VPC Connector**: Network connectivity for Cloud Run

## Cloud SQL Configuration

### Public IP Access
The Cloud SQL instance is configured with **public IP access** for easier connectivity from Jenkins and Cloud Run. The database:
- Has a public IPv4 address
- Requires SSL/TLS encrypted connections (`sslmode=require`)
- Allows connections from all IPs (0.0.0.0/0) - **consider restricting this in production**

### Security Recommendations
For production environments, consider:
1. Restricting `authorized_networks` to specific IP ranges (Jenkins, Cloud Run, etc.)
2. Enabling Cloud SQL Proxy for enhanced security
3. Using private IP with VPC peering for internal services

## Secret Manager

All sensitive credentials are stored in Google Cloud Secret Manager with the following naming convention: `{environment}-{secret-name}`

### Database Secrets

For environment `dev`, the following secrets are created:

| Secret Purpose | Secret Name | Description |
|----------------|-------------|-------------|
| Database Name | `dev-db-name` | PostgreSQL database name |
| Database Username | `dev-db-username` | Database user for application |
| Database Password | `dev-db-password` | Auto-generated secure password |
| Database Host | `dev-db-host` | Public IP address of Cloud SQL instance |
| Database URL | `dev-database-url` | Complete PostgreSQL connection string |

### Application Secrets

| Secret Purpose | Secret Name | Description |
|----------------|-------------|-------------|
| JWT Secret | `dev-secret-key` | Secret key for JWT token signing |
| Google OAuth Client ID | `dev-google-client-id` | Google OAuth 2.0 client ID |
| Google OAuth Secret | `dev-google-client-secret` | Google OAuth 2.0 client secret |
| Email Username | `dev-mail-username` | SMTP email username |
| Email Password | `dev-mail-password` | SMTP email password |

## Usage

### Prerequisites
1. Google Cloud SDK installed and configured
2. Terraform >= 1.5 installed
3. GCP project with billing enabled
4. Required APIs enabled (handled automatically by Terraform)

### Initialize Terraform

```bash
cd terraform

# Initialize with GCS backend
terraform init \
  -backend-config="bucket=YOUR_TERRAFORM_STATE_BUCKET" \
  -backend-config="prefix=terraform/state"
```

### Create tfvars file

Create a `terraform.tfvars` file (or use environment-specific files like `dev.tfvars`):

```hcl
# Required variables
project_id                      = "your-gcp-project-id"
region                          = "us-central1"
environment                     = "dev"

# Artifact Registry
artifact_registry_repository_id = "health-management"

# VPC Connector
vpc_connector_name              = "health-vpc-connector"
vpc_connector_ip_range          = "10.8.0.0/28"

# Cloud SQL
cloud_sql_instance_name         = "health-db-dev"
cloud_sql_tier                  = "db-f1-micro"
cloud_sql_deletion_protection   = false

# Cloud Run
cloud_run_service_name          = "health-management-api"
cloud_run_image                 = "us-central1-docker.pkg.dev/PROJECT_ID/health-management/api:latest"
cloud_run_max_instances         = 10

# Secrets (sensitive - use environment variables or secure input)
secret_key                      = "your-jwt-secret-key"
google_client_id                = "your-google-oauth-client-id"
google_client_secret            = "your-google-oauth-client-secret"
mail_username                   = "your-email@gmail.com"
mail_password                   = "your-email-password"
```

### Plan and Apply

```bash
# Review changes
terraform plan -var-file="dev.tfvars"

# Apply changes
terraform apply -var-file="dev.tfvars"
```

### Access Secrets

After deployment, retrieve secret values:

```bash
# Get database credentials
gcloud secrets versions access latest --secret="dev-db-name"
gcloud secrets versions access latest --secret="dev-db-username"
gcloud secrets versions access latest --secret="dev-db-password"
gcloud secrets versions access latest --secret="dev-db-host"

# Get complete DATABASE_URL
gcloud secrets versions access latest --secret="dev-database-url"
```

### Output Values

After applying, Terraform outputs useful values:

```bash
# View all outputs
terraform output

# View specific outputs
terraform output cloud_sql_public_ip
terraform output database_secret_names
terraform output cloud_run_service_account_email
```

## Modules

### artifact_registry
Manages the Artifact Registry repository for container images.

### vpc_connector
Creates a Serverless VPC Access connector for Cloud Run to access VPC resources.

### secret_manager
Manages secrets in Google Cloud Secret Manager and IAM permissions.

### cloud_sql
Provisions Cloud SQL PostgreSQL instance with public IP access.

## Database Connection

### From Cloud Run
Cloud Run can connect using either:
1. **DATABASE_URL** secret (recommended): Complete connection string with SSL
2. **Individual secrets**: Construct connection string from db_name, db_username, db_password, db_host

### From Jenkins/External
```bash
# Using Cloud SQL Proxy (recommended)
cloud-sql-proxy PROJECT_ID:REGION:INSTANCE_NAME

# Direct connection (requires SSL)
psql "postgresql://USERNAME:PASSWORD@PUBLIC_IP:5432/DATABASE_NAME?sslmode=require"
```

## Cleanup

To destroy all resources:

```bash
terraform destroy -var-file="dev.tfvars"
```

**Note**: If `cloud_sql_deletion_protection` is `true`, you'll need to manually disable it before destroying.

## Security Considerations

1. **Never commit** `terraform.tfvars` or `*.tfvars` files containing secrets to version control
2. Use environment variables for sensitive values: `TF_VAR_secret_key=xxx`
3. Restrict Cloud SQL authorized networks in production
4. Enable audit logging for Secret Manager access
5. Rotate database passwords regularly
6. Use least-privilege IAM roles for service accounts

## Troubleshooting

### Cloud SQL Connection Issues
- Verify public IP is enabled: Check outputs or GCP Console
- Ensure SSL mode is set to `require` in connection string
- Check authorized networks in Cloud SQL settings
- Verify service account has `cloudsql.client` role

### Secret Manager Access
- Verify service account has `secretmanager.secretAccessor` role
- Check secret name format: `{environment}-{key-with-hyphens}`
- Ensure Secret Manager API is enabled

### VPC Connector Issues
- Verify IP range doesn't conflict with existing subnets
- Check VPC Access API is enabled
- Ensure sufficient IP addresses in the range (minimum /28)
