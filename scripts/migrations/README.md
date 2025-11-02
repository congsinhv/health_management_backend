# Database Migrations

This project uses [Alembic](https://alembic.sqlalchemy.org/en/latest/index.html) for database schema version management.

## Getting Started

### 1. Export Configuration in Terminal

**On Unix/Linux/macOS:**
```bash
export DATABASE_URI=postgresql://health_user:health_password@localhost:5432/health_management
export PYTHONPATH=$(pwd)/scripts
```

**On Windows (Command Prompt):**
```cmd
set DATABASE_URI=postgresql://health_user:health_password@localhost:5432/health_management
set PYTHONPATH=%CD%\scripts
```

**On Windows (PowerShell):**
```powershell
$env:DATABASE_URI="postgresql://health_user:health_password@localhost:5432/health_management"
$env:PYTHONPATH="$PWD\scripts"
```

### 2. Install Python 3.13

Install Python 3.13 from [python.org](https://www.python.org/downloads/release/python-3137/)

### 3. Navigate to Scripts Folder

```shell
cd scripts/
```

### 4. Set Up Python Virtual Environment

**On Unix/Linux/macOS:**
```shell
python3.13 -m venv env && source env/bin/activate && pip install -r requirements.txt
```

**On Windows:**
```cmd
python3.13 -m venv env && env\Scripts\activate && pip install -r requirements.txt
```

## Usage

### 1. Run Migration Scripts

Apply all pending migrations to the database:

```shell
alembic upgrade head
```

After running, the database will track the applied version in the `public.alembic_version` table:

| version_num   |
| ------------- |
| 41ac3d38ccc0  |

### 2. Create a New Migration Script

Generate a new migration file:

```shell
alembic revision -m "Change some thing"
```

A new migration script will be created in `migrations/versions/{revision}_{name}.py`:

```python
"""Change some thing

Revision ID: bd30e5e471f5
Revises: 41ac3d38ccc0
Create Date: 2021-01-07 09:27:26.610750

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'bd30e5e471f5'
down_revision = '41ac3d38ccc0'
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
```

Put your database change script in the `upgrade()` function. Also add the reverse operation in the `downgrade()` function to enable rolling back to the previous version.

### 3. Auto-Generate Migration from Models

To automatically detect changes in your SQLAlchemy models:

```shell
alembic revision --autogenerate -m "Description of changes"
```

**Note:** Always review auto-generated migrations before applying them.

### 4. Downgrade to Previous Version

Roll back the last migration:

```shell
alembic downgrade -1
```

Roll back to a specific revision:

```shell
alembic downgrade <revision_id>
```

### 5. View Migration History

See current revision:

```shell
alembic current
```

See migration history:

```shell
alembic history
```

## Environment Variables from .env File

If you prefer to load environment variables from a `.env` file:

**On Unix/Linux/macOS:**
```bash
export $(grep -v '^#' .env | xargs)
```

**On Windows (PowerShell):**
```powershell
Get-Content .env | ForEach-Object {
    if ($_ -match '^([^#].+?)=(.+)$') {
        [System.Environment]::SetEnvironmentVariable($matches[1], $matches[2])
    }
}
```

## Troubleshooting

### Connection Errors

If you encounter database connection errors, verify:
- Database server is running
- Connection string is correct
- User has proper permissions
- Firewall allows connection

### Path Issues

If Python can't find modules, ensure `PYTHONPATH` is set correctly:
- Use `$(pwd)` on Unix/macOS (gets current directory)
- Use `%CD%` on Windows Command Prompt
- Use `$PWD` on Windows PowerShell
