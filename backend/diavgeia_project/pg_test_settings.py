from .settings import *
import os


# Start with the existing database configuration
test_db_config = DATABASES["default"].copy()

# Override database connection settings for tests
# Always use explicit environment variables first with clear fallbacks
test_db_config.update(
    {
        "NAME": os.environ.get(
            "TEST_DB_NAME", os.environ.get("DB_NAME", f"test_{test_db_config['NAME']}")
        ),
        "HOST": os.environ.get(
            "TEST_DB_HOST",
            os.environ.get("DB_HOST", test_db_config.get("HOST", "localhost")),
        ),
        "USER": os.environ.get(
            "TEST_DB_USER",
            os.environ.get("DB_USER", test_db_config.get("USER", "postgres")),
        ),
        "PASSWORD": os.environ.get(
            "TEST_DB_PASSWORD",
            os.environ.get("DB_PASSWORD", test_db_config.get("PASSWORD", "postgres")),
        ),
    }
)

# Use the test database configuration
DATABASES = {"default": test_db_config}

print(
    f"PostgreSQL connection details: HOST={test_db_config['HOST']} DB={test_db_config['NAME']}"
)

# Add a setting to indicate we're using PostgreSQL for tests
USING_POSTGRESQL_FOR_TESTS = True
