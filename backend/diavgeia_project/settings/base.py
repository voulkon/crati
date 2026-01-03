"""
Base Django settings.

Contains core settings like SECRET_KEY, DEBUG, ALLOWED_HOSTS, and other fundamental configurations.
"""

import os
from pathlib import Path
from urllib.parse import urlparse

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
default_unsafe_secret_key = "django-insecure-_qy*f$4zd#u_)lt_v%2t*29g9f$rr0=u!-g=t#+6g+z0)u6zsi"
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", default_unsafe_secret_key) 



# SECURITY WARNING: don't run with debug turned on in production!
DEBUG_ENV = os.getenv("DEBUG", "False")  # Get it as a string
DEBUG = DEBUG_ENV.lower() in ("true", "1", "t")  # Convert to boolean

# Stealth mode - requires authentication for all API endpoints
STEALTH_MODE = os.getenv("STEALTH_MODE", "False").lower() in ("true", "1", "t")

# Stealth allowlist - when enabled with STEALTH_MODE, only users in AllowedUser table can access
STEALTH_ALLOWLIST = os.getenv("STEALTH_ALLOWLIST", "False").lower() in ("true", "1", "t")


FRONTEND_DOMAINS:list[str] = os.getenv("FRONTEND_DOMAINS", "http://localhost:3000").split(",")
FRONTEND_DOMAINS_clean:list[str] = [d.strip() for d in FRONTEND_DOMAINS]

if not FRONTEND_DOMAINS_clean and not DEBUG:
    raise ValueError("FRONTEND_DOMAINS must be set in production")
FRONTEND_HOSTNAMES = [
    urlparse(d).netloc for d in FRONTEND_DOMAINS_clean if urlparse(d).netloc
]

# Start with frontend hostnames
ALLOWED_HOSTS = FRONTEND_HOSTNAMES.copy()

# Add any additional hosts from environment
ALLOWED_HOSTS_ENV = os.getenv("ALLOWED_HOSTS")
if ALLOWED_HOSTS_ENV:
    ALLOWED_HOSTS.extend([host.strip() for host in ALLOWED_HOSTS_ENV.split(",")])

# If DEBUG is True, you might want to add common local hosts for convenience
if DEBUG:
    ALLOWED_HOSTS.extend(["localhost", "127.0.0.1"])

# Default primary key field type
# https://docs.djangoproject.com/en/5.0/ref/settings/#default-auto-field
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# WSGI application
WSGI_APPLICATION = "diavgeia_project.wsgi.application"

# Root URL configuration
ROOT_URLCONF = "diavgeia_project.urls"
