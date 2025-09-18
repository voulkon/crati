# OpenSearch S3 Backup: Step-by-Step Guide

This guide documents the process of setting up OpenSearch snapshot backups to AWS S3, including troubleshooting, best practices, and next steps for automation and restore.

---

## 1. **AWS Setup**

- **Created an S3 bucket** (e.g., `crati-backups`) in the `eu-north-1` region.
- **Created an IAM user** with programmatic access and a custom policy allowing S3 access to the backup bucket.
- **Stored the credentials** securely in your `.env_files/.env.local.secrets` file:
  ```env
  AWS_ACCESS_KEY_ID=...
  AWS_SECRET_ACCESS_KEY=...
  AWS_DEFAULT_REGION=eu-north-1
  ```

---

## 2. **Docker & OpenSearch Configuration**

- **Custom Dockerfile** for OpenSearch, installing the S3 plugin and using a custom entrypoint script.
- **Entrypoint script** creates the OpenSearch keystore and adds AWS credentials:
  ```bash
  echo "y" | /usr/share/opensearch/bin/opensearch-keystore create
  echo "$AWS_ACCESS_KEY_ID" | /usr/share/opensearch/bin/opensearch-keystore add --stdin s3.client.default.access_key
  echo "$AWS_SECRET_ACCESS_KEY" | /usr/share/opensearch/bin/opensearch-keystore add --stdin s3.client.default.secret_key
  exec /usr/share/opensearch/opensearch-docker-entrypoint.sh "$@"
  ```
- **docker-compose.yml** passes the AWS credentials and region to the container:
  ```yaml
  environment:
    - AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}
    - AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}
    - AWS_DEFAULT_REGION=${AWS_DEFAULT_REGION:-eu-north-1}
  ```

---

## 3. **Registering the S3 Repository**

Run this command to register the S3 repository in OpenSearch:
```bash
curl -X PUT "localhost:9200/_snapshot/s3-backup-repo" \
-H 'Content-Type: application/json' \
-d '{
  "type": "s3",
  "settings": {
    "bucket": "crati-backups",
    "base_path": "opensearch/test",
    "region": "eu-north-1",
    "compress": true
  }
}'
```
- **Tip:** Use a unique `base_path` for each environment (e.g., `opensearch/prod`, `opensearch/dev`) to keep backups organized.

---

## 4. **Creating a Snapshot**

Send a snapshot to S3:
```bash
curl -X PUT "localhost:9200/_snapshot/s3-backup-repo/test-snapshot-1?wait_for_completion=true" \
-H 'Content-Type: application/json' \
-d '{
  "indices": "*",
  "ignore_unavailable": true,
  "include_global_state": false
}'
```
- **Result:** You should see files and folders appear in your S3 bucket under the specified `base_path`.

---

## 5. **Troubleshooting**

- **Region errors:** Ensure `AWS_DEFAULT_REGION` and the `region` in your repository settings match your bucket's region.
- **Credentials errors:** Make sure the keystore is created and credentials are added before OpenSearch starts.
- **Bucket not found:** Double-check the bucket name and region.
- **Strange files/folders:** These are normal; OpenSearch organizes snapshot data by index and shard.

---

## 6. **Next Steps**

### **A. Restore from a Snapshot**
```bash
curl -X POST "localhost:9200/_snapshot/s3-backup-repo/test-snapshot-1/_restore" \
-H 'Content-Type: application/json' \
-d '{
  "indices": "*",
  "ignore_unavailable": true,
  "include_global_state": false
}'
```
- **Warning:** Restoring will overwrite existing indices with the same name.

### **B. Automate with Django**
- Integrate snapshot creation and restore into your Django app using the OpenSearch Python client.
- Example (pseudo-code):
  ```python
  from opensearchpy import OpenSearch
  client = OpenSearch(...)
  client.snapshot.create_repository(...)
  client.snapshot.create(...)
  client.snapshot.restore(...)
  ```
- Schedule regular backups with Celery or a management command.

### **C. Keep S3 Organized**
- Use a clear `base_path` for each environment and service:
  - `opensearch/prod/`, `opensearch/dev/`, etc.
- Avoid using the root of your bucket for backups to prevent clutter.

### **D. Monitor and Test**
- Periodically test restores to ensure backups are valid.
- Monitor S3 storage usage and set up lifecycle rules if needed.

---

## **Summary Table**

| Step                | What You Did                                    |
|---------------------|-------------------------------------------------|
| AWS Setup           | S3 bucket, IAM user, credentials                |
| Docker Config       | Custom Dockerfile, entrypoint, env vars         |
| Register Repository | curl to register S3 repo in OpenSearch          |
| Create Snapshot     | curl to create snapshot, verify in S3           |
| Restore/Automate    | (Next) Use API/Django for automation/restore    |

---

**You now have a robust, automated OpenSearch backup system using S3!**

**Next: Implement restore and automation in Django, and keep your S3 bucket organized by environment.**

Manually:

```
curl -X PUT "localhost:9200/_snapshot/s3-backup-repo" \
-H 'Content-Type: application/json' \
-d '{
  "type": "s3",
  "settings": {
    "bucket": "crati-backups",
    "base_path": "opensearch/test",
    "region": "eu-north-1",
    "compress": true
  }
}'
```

Then, send a snapshot:

```
curl -X PUT "localhost:9200/_snapshot/s3-backup-repo/test-snapshot-1?wait_for_completion=true" \
-H 'Content-Type: application/json' \
-d '{
  "indices": "*",
  "ignore_unavailable": true,
  "include_global_state": false
}'

```


Automatically:

```
...