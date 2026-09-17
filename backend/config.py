"""
CyberNexus - Backend Configuration
Phase 6F-1: Centralized configuration layer with Supabase environment settings.
"""

import os
from typing import List
from dotenv import load_dotenv

# Load .env variables from root or working directory
load_dotenv()

# Server Configuration
API_TITLE: str = "CyberNexus API"
API_VERSION: str = "1.0.0"
API_DESCRIPTION: str = "ML-Powered Security Content Analysis API for SMS, Email, URL, and QR threats."
HOST: str = os.getenv("HOST", "127.0.0.1")
PORT: int = int(os.getenv("PORT", "8000"))

# CORS Configuration
ALLOWED_ORIGINS: List[str] = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

# Supabase Configuration
SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY: str = (
    os.getenv("SUPABASE_SERVICE_ROLE_KEY") 
    or os.getenv("SUPABASE_SECRET_KEY") 
    or ""
)
