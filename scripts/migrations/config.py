import os

DATABASE_URI = os.environ.get(
    "DATABASE_URI",
    "postgresql://health_user:health_password@localhost:5432/health_management",
)
