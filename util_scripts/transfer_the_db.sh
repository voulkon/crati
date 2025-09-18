#!/bin/bash

# Variables
REMOTE_CONTAINER="db-lsk8o0ckck40oo04gokog084-160408558532"
REMOTE_USER="trypas"
REMOTE_DB="db_trypia"
REMOTE_SERVER="root@49.13.136.52"
LOCAL_CONTAINER="diavgeia_db"
DUMP_FILE="remote_db_dump.sql"
SSH_KEY="C:/Users/voulk/.ssh/id_ed25519"
LOCAL_POSTGRES_USER="local_diavgia_user"
LOCAL_POSTGRES_PASSWORD="9fc3:0724:b1c6:be8c:5c90:526f:a078:fc54"
LOCAL_POSGRES_DB="local_diavgia_db"

# Step 1: Dump the remote database
echo "Dumping remote database..."
ssh -i "$SSH_KEY" $REMOTE_SERVER "docker exec -t $REMOTE_CONTAINER pg_dump -U $REMOTE_USER $REMOTE_DB > /tmp/$DUMP_FILE"

# Step 2: Transfer the dump file to local
echo "Transferring dump file to local machine..."
scp -i "$SSH_KEY" $REMOTE_SERVER:/tmp/$DUMP_FILE ./

# Step 3: Copy the dump file into the local container
echo "Copying dump file into local container..."
docker cp ./$DUMP_FILE $LOCAL_CONTAINER:/tmp/$DUMP_FILE

# Step 4: Restore the dump in the local database
echo "Restoring dump into local database..."
ssh -i "$SSH_KEY" $REMOTE_SERVER "docker exec -t $REMOTE_CONTAINER pg_dump --data-only -U $REMOTE_USER $REMOTE_DB > /tmp/$DUMP_FILE"# Cleanup

echo "Cleaning up..."
rm ./$DUMP_FILE
ssh -i "$SSH_KEY" $REMOTE_SERVER "rm /tmp/$DUMP_FILE"

echo "Database transfer completed!"