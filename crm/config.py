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
    # Fallback = the value the currently deployed build already uses, so a missing Railway
    # variable can never crash the boot and existing sessions stay valid. Set real values
    # in Railway (SECRET_KEY / JWT_SECRET_KEY) — a warning is logged while the fallback is used.
    _FALLBACK_SECRET = "dev-secret-key-change-in-production"
    SECRET_KEY = os.getenv("SECRET_KEY") or _FALLBACK_SECRET
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY") or _FALLBACK_SECRET
    if SECRET_KEY == _FALLBACK_SECRET or JWT_SECRET_KEY == _FALLBACK_SECRET:
        import logging as _lg
        _lg.getLogger(__name__).warning("SECRET_KEY/JWT_SECRET_KEY not set — using insecure fallback; set them in Railway")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=int(os.getenv("JWT_EXPIRATION_HOURS", "24")))
    
    # CORS Configuration - allow the landing-page origins (public sites) + local dev
    # NOTE: Pagliano's client LP still runs on Netlify (verdant-crumble) and is NOT legacy.
    CORS_ORIGINS = os.getenv(
        "CORS_ORIGINS",
        "https://verdant-crumble-021449.netlify.app,https://lexflow-site.pages.dev,"
        "http://localhost:3000,http://localhost:5000,http://localhost:5001,http://localhost:5002,http://localhost:5003"
    ).split(",")
    
    # Rate Limiting Configuration
    RATELIMIT_STORAGE_URL = os.getenv("RATELIMIT_STORAGE_URL", "memory://")
