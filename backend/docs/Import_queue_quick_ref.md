# Import Queue Quick Reference

Essential commands to manage the ImportJobQueue when things get stuck or we need to check status.

---

## Emergency Recovery (Job Stuck >1 Hour)

```bash
# Clear stale jobs and auto-dispatch next
python manage.py import_queue clear-stale --max-age-hours 1
```

**When to use**: Job stuck in "processing" or "fetching" for hours (see ⚠️ STALE! marker)

**What it does**:
- Marks old jobs as FAILED
- Automatically dispatches next pending job
- Unblocks the queue

---

## Check Queue Status

```bash
# View current queue state
python manage.py import_queue status
```

**Shows**:
- Active jobs count (should be ≤ MAX_CONCURRENT_JOBS)
- Pending jobs waiting
- Recent completed jobs
- ⚠️ Warnings for stale jobs (>6 hours old)

---

## Remove Duplicate Jobs

```bash
# Preview duplicates without deleting
python manage.py import_queue clear-duplicates --dry-run

# Actually remove duplicates (keeps oldest)
python manage.py import_queue clear-duplicates
```

**When to use**: Multiple jobs queued for same date+filters

**What it does**:
- Finds jobs with identical date + organization/unit/signer
- Keeps the oldest job
- Deletes newer duplicates

---

## Manual Job Dispatch

```bash
# Manually start next pending job
python manage.py import_queue dispatch-next
```

**When to use**: 
- Queue is clear but nothing is running
- After fixing worker issues
- After code changes that broke auto-dispatch

**NOT needed if**: Jobs are auto-processing (domino effect working)

---

##  Common Scenarios

### Scenario 1: Job Stuck for Hours
**Symptoms**: Active job with ⚠️ STALE! marker, pending jobs not moving

**Fix**:
```bash
python manage.py import_queue clear-stale --max-age-hours 1
# ✓ Auto-dispatches next job
```

---

### Scenario 2: Queue Empty But Nothing Running
**Symptoms**: Active: 0, Pending: 10+, Can Start New: True

**Fix**:
```bash
python manage.py import_queue dispatch-next
```

---

### Scenario 3: Too Many Duplicate Jobs
**Symptoms**: Same dates appearing multiple times in pending queue

**Fix**:
```bash
# Check first
python manage.py import_queue clear-duplicates --dry-run

# Then remove
python manage.py import_queue clear-duplicates
```

---

### Scenario 4: Worker Crashed/Restarted
**Symptoms**: Jobs stuck after docker-compose restart or laptop sleep

**Fix**:
```bash
# 1. Restart worker
docker-compose -f docker/docker-compose.yml restart worker

# 2. Clear any stale jobs
python manage.py import_queue clear-stale --max-age-hours 1

# 3. Check status
python manage.py import_queue status
```

---

## Tips

### Normal Operation
- **Active Jobs**: Should always be 1 (or MAX_CONCURRENT_JOBS)
- **Pending Jobs**: Decreasing as they process
- **No warnings**: Good! Queue is healthy

### Warning Signs
- ⚠️ STALE marker on active jobs
- Active jobs > 0 but jobs created days ago
- Pending count not decreasing

### Prevention
- Don't let laptop sleep while imports running
- Monitor queue every ~30 mins for long imports
- Run `clear-duplicates` before big import batches

---

## Quick Checks

```bash
# Is queue processing?
python manage.py import_queue status | grep "Active Jobs"
# Should see: Active Jobs: 1

# Any stale jobs?
python manage.py import_queue status | grep STALE
# Should see nothing

# How many pending?
python manage.py import_queue status | grep "Pending Jobs"
# Should decrease over time
```

---

## Complete Recovery Workflow

If everything is broken:

```bash
# 1. Check what's wrong
python manage.py import_queue status

# 2. Clear stale jobs
python manage.py import_queue clear-stale --max-age-hours 1

# 3. Remove duplicates
python manage.py import_queue clear-duplicates

# 4. Restart worker if needed
docker-compose -f docker/docker-compose.yml restart worker

# 5. Verify queue is processing
python manage.py import_queue status
# Active should be 1, pending decreasing
```

---

##  Advanced Commands

```bash
# Clear very old stale jobs (24 hours)
python manage.py import_queue clear-stale --max-age-hours 24

# Set concurrent job limit (runtime only)
python manage.py import_queue set-limit 2
```

---

## Monitoring During Import

```bash
# Auto-refresh status every 3 seconds
while true; do 
  clear
  date
  python manage.py import_queue status | head -n 30
  sleep 3
done
```

Press `Ctrl+C` to stop monitoring.

---

## FAQ

**Q: My laptop went to sleep, are jobs stuck?**  
A: Probably yes. Run `clear-stale --max-age-hours 1` to recover.

**Q: Should I run dispatch-next after clear-stale?**  
A: No! `clear-stale` auto-dispatches the next job.

**Q: How do I know if queue is working?**  
A: Run `status` twice, 30 seconds apart. Pending count should decrease.

**Q: Can I run multiple imports at once?**  
A: No, MAX_CONCURRENT_JOBS=1. Jobs queue automatically.

**Q: How long does a job take?**  
A: 30 seconds to 5 minutes depending on decisions count for that day.
