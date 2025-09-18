# Set up variables
CONTAINER_NAME="db-lgwgsc00gcgoo4wscogwswkk-141956204814"
DB_USER="local_diavgia_user"
DB_NAME="local_diavgia_db"
DB_PASSWORD="9f***54"

# Verify the container is running
docker ps | grep $CONTAINER_NAME

# Test 1: Connect to the database from outside the container
docker exec -it $CONTAINER_NAME psql -U $DB_USER -d $DB_NAME

# Test 2: If that fails, try with password in the command (less secure but for testing)
docker exec -it $CONTAINER_NAME sh -c "PGPASSWORD='$DB_PASSWORD' psql -U $DB_USER -d $DB_NAME"

# Test 3: Check what users actually exist in the database
docker exec -it $CONTAINER_NAME psql -U postgres -c "\du"

# Test 4: Check what databases exist
docker exec -it $CONTAINER_NAME psql -U postgres -c "\l"