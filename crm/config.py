import os
from pathlib import Path
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()
BASE_DIR = Path(__file__).resolve().parent.parent

class Config:
    # Database Configuration - with connection pooling
    # Handle both postgres:// (deprecated) and postgresql:// schemes
    db_url = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{BASE_DIR / 'crm_local.db'}"
    )
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    
    SQLALCHEMY_DATABASE_URI = db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,  # Test connections before using
        "pool_recycle": 3600,   # Recycle connections every hour
        "pool_size": 10,        # Connection pool size
        "max_overflow": 20,     # Max overflow connections
    }
    
    # JWT Configuration - with token expiry
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-secret-key-change-in-production")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=int(os.getenv("JWT_EXPIRATION_HOURS", "24")))
    
    # CORS Configuration
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5000,http://localhost:5001").split(",")
    
    # Rate Limiting Configuration
    RATELIMIT_STORAGE_URL = os.getenv("RATELIMIT_STORAGE_URL", "memory://")
