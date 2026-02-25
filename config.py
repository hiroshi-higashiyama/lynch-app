import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key")
    EDINET_API_KEY = os.environ.get("EDINET_API_KEY", "")
    CACHE_TTL_SECONDS = int(os.environ.get("CACHE_TTL_SECONDS", "3600"))
    DEBUG = os.environ.get("FLASK_DEBUG", "0") == "1"
