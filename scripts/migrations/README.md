# Overview
This project contains scripts for manage database structure version. The framework use is [Alembic](https://alembic.sqlalchemy.org/en/latest/index.html)

# Getting Started

### 1. Export below config in terminal
```bash
export DATABASE_URI=postgresql://health_user:health_password@localhost:5432/health_management
export PYTHONPATH=/path/to/health_management_backend/scripts
```

### 2. Install `python3.13`. [More details](https://www.python.org/downloads/release/python-3137/)


### 3. cd to scripts folder
```shell
cd scripts/
```


### 4. Set up python venv
```shell
python3.13 -m venv env && source env/bin/activate && pip install -r requirements.txt
```

# Usage

### 1. Run migration scripts
```shell
alembic upgrade head
```

After run the script, the database table to track for the version applied in `public.alembic_version`

| version_num |
| ----------- |
| 41ac3d38ccc0|


### 2. Create a new migration script
```shell
alembic revision -m "Change some thing"
```

A new migration script will be generated in `alembic/versions/{revision}_{name}.py`
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

Put your script to make change to database in upgrade function. Also need to put downgrade script to be able to downgrade the database to the last changed version.


export $(grep -v '^#' .env | xargs)

> Test.