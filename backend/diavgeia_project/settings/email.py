import os

EMAIL_BACKEND = 'django_ses.SESBackend'
AWS_SES_ACCESS_KEY_ID = os.getenv('AWS_SES_ACCESS_KEY_ID', 'YOUR-ACCESS-KEY-ID')
AWS_SES_SECRET_ACCESS_KEY = os.getenv('AWS_SES_SECRET_ACCESS_KEY', 'YOUR-SECRET-ACCESS-KEY')

# Default email configuration
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'noreply@crati.co')
SERVER_EMAIL = os.getenv('SERVER_EMAIL', DEFAULT_FROM_EMAIL)

# Application-specific email settings
APP_NAME = os.getenv('APP_NAME', 'Crati.Co')

# Email verification for Django-registered users (optional)
# Note: Clerk handles email verification for Clerk users automatically
DJANGO_EMAIL_VERIFICATION_REQUIRED = os.getenv('DJANGO_EMAIL_VERIFICATION_REQUIRED', 'False').lower() == 'true'