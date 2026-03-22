"""
Authentication settings.

Contains AUTH_USER_MODEL and password validators.
"""

# Custom user model
AUTH_USER_MODEL = "users.CustomUser"

# Authentication backends
# Use custom email-based authentication backend
AUTHENTICATION_BACKENDS = [
    'api.auth_backends.EmailAuthBackend',  # Email-based authentication
    'django.contrib.auth.backends.ModelBackend',  # Fallback to default username authentication
]

# Password validation
# https://docs.djangoproject.com/en/5.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]
