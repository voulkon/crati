# VM Storage Investigation & Monitoring Guide

## Quick Storage Overview

### 1. Overall Disk Usage
```bash
# See disk space by filesystem
df -h

# Human-readable summary
df -h /
```

### 2. Find Top-Level Space Consumers
```bash
# Top directories from root
du -sh /* 2>/dev/null | sort -h | tail -20

# More detailed breakdown
du -h / --max-depth=1 2>/dev/null | sort -h | tail -20
```

### 3. Find Large Files (>1GB)
```bash
# Find files over 1GB across entire system
find / -type f -size +1G 2>/dev/null -exec ls -lh {} \; | awk '{print $9 ": " $5}'

# Find files over 500MB
find / -type f -size +500M 2>/dev/null -exec ls -lh {} \; | awk '{print $9 ": " $5}'

# Find in specific directory
find /var -type f -size +100M 2>/dev/null -exec ls -lh {} \;
```

---

## Common Storage Culprits

### Docker (Usually 60-80% of server space)

#### 1. Check Docker Disk Usage
```bash
# Overall Docker space
docker system df

# Detailed breakdown with individual items
docker system df -v

# Volumes specifically
docker volume ls
docker system df -v | grep -A 100 "Local Volumes"
```

#### 2. Docker Volumes Investigation
```bash
# Total volume space
du -sh /var/lib/docker/volumes

# Individual volumes
du -sh /var/lib/docker/volumes/* | sort -h | tail -20

# Find unused volumes (LINKS=0)
docker volume ls --filter "dangling=true"

# See what's inside a specific volume
docker run --rm -v VOLUME_NAME:/data alpine du -sh /data/*
```

#### 3. Docker Images
```bash
# List all images with sizes
docker images -a

# Find dangling images (<none>)
docker images -f "dangling=true"

# Check layer sizes
docker system df -v | grep -A 100 "Images space usage"
```

#### 4. Docker Overlay2 (Container Filesystems)
```bash
# Total overlay2 size
du -sh /var/lib/docker/overlay2

# Breakdown by container
du -sh /var/lib/docker/overlay2/* 2>/dev/null | sort -h | tail -20
```

#### 5. Container Logs
```bash
# Find large container logs
du -sh /var/lib/docker/containers/*/*.log 2>/dev/null | sort -h | tail -20

# Total container logs size
du -sh /var/lib/docker/containers

# See live log of specific container
docker logs --tail 100 CONTAINER_NAME
```

#### 6. Build Cache
```bash
# Check build cache size
docker system df | grep "Build Cache"

# Detailed cache info
docker buildx du
```

---

### System Logs

```bash
# Total logs size
du -sh /var/log

# Breakdown by log file
du -sh /var/log/* | sort -h | tail -20

# Check journal logs (systemd)
journalctl --disk-usage
du -sh /var/log/journal
```

---

### Application Data & Backups

#### Coolify (or similar deployment platforms)
```bash
# Check Coolify directory
du -sh /data/coolify/*

# Check backups specifically
du -sh /data/coolify/backups/*
du -sh /data/coolify/backups/databases/*/*

# List backup files with dates
find /data/coolify/backups -type f -name "*.dmp" -o -name "*.sql" -o -name "*.gz" -exec ls -lh {} \;
```

#### Other common directories
```bash
# Home directory
du -sh /root/* /root/.* 2>/dev/null | sort -h | tail -20

# Temporary files
du -sh /tmp /var/tmp

# APT cache
du -sh /var/cache/apt/archives

# Snap packages
du -sh /var/lib/snapd/snaps
```

---

## Safe Cleanup Commands

### Docker Cleanup

```bash
# 1. Remove unused volumes (no active containers)
docker volume prune -f

# 2. Remove dangling images
docker image prune -f

# 3. Remove all unused images (not just dangling)
docker image prune -a -f

# 4. Clear build cache
docker builder prune -af

# 5. Nuclear option - remove all unused Docker objects
docker system prune -a --volumes -f

# 6. Truncate container logs
truncate -s 0 /var/lib/docker/containers/**/*-json.log

# 7. Remove specific unused images by age
docker images --format '{{.Repository}}:{{.Tag}} {{.CreatedAt}}' | grep "months ago" | awk '{print $1}' | xargs -r docker rmi
```

### System Cleanup

```bash
# 1. Clean APT cache
apt-get clean
apt-get autoclean
apt-get autoremove -y

# 2. Remove old kernels (keep current + 1)
apt-get autoremove --purge -y

# 3. Clean journal logs (keep last 7 days)
journalctl --vacuum-time=7d

# Or keep last 500MB
journalctl --vacuum-size=500M

# 4. Clean old logs manually
find /var/log -type f -name "*.log.*.gz" -mtime +30 -delete
find /var/log -type f -name "*.log.*" -mtime +7 -delete

# 5. Clear package manager cache
apt-get clean
```

### Application-Specific Cleanup

```bash
# Remove old database backups (keep last 3)
cd /data/coolify/backups/databases/YOUR_PROJECT/YOUR_DB/
ls -t | tail -n +4 | xargs -r rm

# Clean old application logs
find /root -name "*.log" -mtime +30 -delete

# Remove old downloaded files
find /root -type f -size +100M -mtime +90
```

---

## Automated Monitoring Setup

> **Note:** These scripts don't exist yet - you need to create them first by running the commands below.

### 1. Create Storage Monitoring Script

```bash
cat > /usr/local/bin/check-storage.sh << 'EOF'
#!/bin/bash

# Storage monitoring script
THRESHOLD=85
USAGE=$(df / | tail -1 | awk '{print $5}' | sed 's/%//')

echo "==================================="
echo "Storage Report - $(date)"
echo "==================================="
echo ""

# Overall usage
df -h /
echo ""

# Top space consumers
echo "Top 10 directories:"
du -sh /* 2>/dev/null | sort -h | tail -10
echo ""

# Docker usage
echo "Docker usage:"
docker system df
echo ""

# Check if over threshold
if [ "$USAGE" -gt "$THRESHOLD" ]; then
    echo "⚠️  WARNING: Disk usage is ${USAGE}% (threshold: ${THRESHOLD}%)"
    echo ""
    echo "Quick fixes:"
    echo "  docker system prune -af --volumes"
    echo "  journalctl --vacuum-time=7d"
    echo "  apt-get autoremove && apt-get clean"
fi

EOF

chmod +x /usr/local/bin/check-storage.sh
```

### 2. Run Storage Check
```bash
/usr/local/bin/check-storage.sh
```

### 3. Schedule Daily Check (Optional)
```bash
# Add to crontab
crontab -e

# Add this line for daily 9 AM check
0 9 * * * /usr/local/bin/check-storage.sh > /var/log/storage-check.log 2>&1
```

### 4. Set Up Disk Usage Alerts

```bash
cat > /usr/local/bin/disk-alert.sh << 'EOF'
#!/bin/bash

THRESHOLD=85
USAGE=$(df / | tail -1 | awk '{print $5}' | sed 's/%//')

if [ "$USAGE" -gt "$THRESHOLD" ]; then
    echo "ALERT: Disk usage at ${USAGE}%" | logger -t disk-alert
    # Add notification service here (email, Slack, Discord, etc.)
fi
EOF

chmod +x /usr/local/bin/disk-alert.sh

# Run hourly
echo "0 * * * * /usr/local/bin/disk-alert.sh" | crontab -
```

---

## Docker Log Rotation Setup

### Configure Docker Daemon
```bash
# Create or edit /etc/docker/daemon.json
cat > /etc/docker/daemon.json << 'EOF'
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3",
    "compress": "true"
  }
}
EOF

# Restart Docker
systemctl restart docker
```

---

## Investigation Workflow

### When Disk is Full - Step by Step

1. **Check overall usage**
   ```bash
   df -h
   ```

2. **Find top directories**
   ```bash
   du -sh /* 2>/dev/null | sort -h | tail -10
   ```

3. **Investigate Docker** (usually the culprit)
   ```bash
   docker system df -v
   du -sh /var/lib/docker/*
   ```

4. **Check for large files**
   ```bash
   find / -type f -size +1G 2>/dev/null -exec ls -lh {} \;
   ```

5. **Check logs**
   ```bash
   du -sh /var/log/*
   journalctl --disk-usage
   ```

6. **Check backups**
   ```bash
   du -sh /data/coolify/backups/* 2>/dev/null
   du -sh /root/* 2>/dev/null | sort -h
   ```

7. **Clean up safely**
   ```bash
   # Start with least destructive
   docker volume prune -f
   docker image prune -f
   docker builder prune -f
   apt-get autoremove && apt-get clean
   journalctl --vacuum-time=7d
   ```

---

## Preventive Measures

### 1. Configure Coolify Backup Retention
- Log into Coolify UI
- For each database: Settings → Backups → Set retention to 2-3 backups
- Or change frequency from daily to weekly

### 2. Set Up Automatic Cleanup Cron Jobs
```bash
# Weekly Docker cleanup (Sundays at 3 AM)
0 3 * * 0 docker system prune -a -f --volumes >> /var/log/docker-cleanup.log 2>&1

# Weekly journal vacuum (Sundays at 3:30 AM)
30 3 * * 0 journalctl --vacuum-time=14d >> /var/log/journal-cleanup.log 2>&1

# Monthly APT cleanup (1st of month at 4 AM)
0 4 1 * * apt-get autoremove -y && apt-get clean >> /var/log/apt-cleanup.log 2>&1
```

### 3. Monitor Specific Projects
```bash
# Create project-specific cleanup scripts
cat > /usr/local/bin/cleanup-old-projects.sh << 'EOF'
#!/bin/bash
# Add commands to remove old project data
# Example:
# docker volume ls | grep "old-project" | awk '{print $2}' | xargs -r docker volume rm
EOF
```

### 4. Use External Storage for Backups
- Consider S3 or external backup service
- Keep only 1-2 local backups
- Archive old backups remotely

---

## Quick Reference Card

```bash
# Emergency Quick Cleanup (when disk is full)
docker system prune -a --volumes -f && \
journalctl --vacuum-time=3d && \
apt-get autoremove -y && apt-get clean && \
truncate -s 0 /var/lib/docker/containers/**/*-json.log

# Full Investigation
df -h && \
du -sh /* 2>/dev/null | sort -h | tail -10 && \
docker system df -v && \
du -sh /var/log/* | sort -h | tail -10

# Safe Routine Cleanup (weekly)
docker image prune -f && \
docker volume prune -f && \
docker builder prune -f && \
journalctl --vacuum-time=7d && \
apt-get autoremove -y && apt-get clean
```

---

## Storage Targets by System Size

### 150GB VM (Your Case)
- **Docker**: 60-80GB max
- **Volumes**: 40-50GB max (databases, app data)
- **Logs**: <5GB
- **Backups**: <10GB (use external for more)
- **System**: <10GB
- **Free space**: Keep >20GB free (15%)

### Warning Thresholds
- **85%+ used**: Immediate cleanup needed
- **90%+ used**: Critical, risk of service failures
- **95%+ used**: Emergency mode, databases may crash

---

## Tools for Deeper Analysis

### ncdu (NCurses Disk Usage)
```bash
# Install
apt-get install ncdu

# Use interactively
ncdu /
ncdu /var/lib/docker
```

### duf (Modern df alternative)
```bash
# Install
wget https://github.com/muesli/duf/releases/download/v0.8.1/duf_0.8.1_linux_amd64.deb
dpkg -i duf_0.8.1_linux_amd64.deb

# Use
duf
```

### dive (Docker image analysis)
```bash
# Install
wget https://github.com/wagoodman/dive/releases/download/v0.11.0/dive_0.11.0_linux_amd64.deb
dpkg -i dive_0.11.0_linux_amd64.deb

# Analyze image layers
dive IMAGE_NAME
```

---

---

## System Health Monitoring (Beyond Storage)

### Check Overall System Health

```bash
# Quick system overview
cat > /usr/local/bin/system-health.sh << 'EOF'
#!/bin/bash

echo "==================================="
echo "System Health Report - $(date)"
echo "==================================="
echo ""

# Disk usage
echo "📊 DISK USAGE:"
df -h / | tail -1 | awk '{print "  Used: " $3 "/" $2 " (" $5 ")"}'
echo ""

# Memory usage
echo "💾 MEMORY:"
free -h | grep Mem | awk '{print "  Used: " $3 "/" $2 " (" int($3/$2*100) "%)"}'
free -h | grep Swap | awk '{print "  Swap: " $3 "/" $2 " (" int($3/$2*100) "%)"}'
echo ""

# CPU Load
echo "⚡ CPU LOAD:"
uptime | awk -F'load average:' '{print "  " $2}'
echo ""

# Zombie processes
ZOMBIES=$(ps aux | awk '{if ($8=="Z") print $0}' | wc -l)
echo "🧟 ZOMBIE PROCESSES: $ZOMBIES"
if [ "$ZOMBIES" -gt 0 ]; then
    echo "  Warning: Found $ZOMBIES zombie processes"
    ps aux | awk '{if ($8=="Z") print "  PID: " $2 " CMD: " $11}'
fi
echo ""

# Docker containers
echo "🐳 DOCKER STATUS:"
docker ps --format "table {{.Names}}\t{{.Status}}" | head -10
echo "  Total: $(docker ps -q | wc -l) running, $(docker ps -aq | wc -l) total"
echo ""

# Pending updates
UPDATES=$(apt list --upgradable 2>/dev/null | grep -c upgradable)
echo "📦 UPDATES AVAILABLE: $UPDATES"
echo ""

# Restart required
if [ -f /var/run/reboot-required ]; then
    echo "⚠️  SYSTEM RESTART REQUIRED"
    if [ -f /var/run/reboot-required.pkgs ]; then
        echo "  Packages requiring restart:"
        cat /var/run/reboot-required.pkgs | head -5
    fi
else
    echo "✅ No restart required"
fi
echo ""

# Service failures
FAILED=$(systemctl list-units --state=failed --no-pager --no-legend | wc -l)
if [ "$FAILED" -gt 0 ]; then
    echo "❌ FAILED SERVICES: $FAILED"
    systemctl list-units --state=failed --no-pager --no-legend
else
    echo "✅ All services running"
fi

EOF

chmod +x /usr/local/bin/system-health.sh
```

### Run Health Check
```bash
/usr/local/bin/system-health.sh
```

---

## Specific Issue Investigations

### 1. Zombie Processes (10 found)

**What are zombies?**
- Processes that finished but parent didn't clean them up
- Usually harmless but indicate poor cleanup
- Can accumulate and consume PIDs

**Investigate zombies:**
```bash
# List zombie processes with details
ps aux | awk '{if ($8=="Z") print $0}'

# Find parent processes of zombies
ps -eo pid,ppid,stat,cmd | awk '$3 ~ /Z/ {print "Zombie PID: " $1 " Parent PID: " $2}'

# Find what's creating zombies
for pid in $(ps aux | awk '{if ($8=="Z") print $2}'); do
    parent=$(ps -o ppid= -p $pid)
    ps -p $parent -o pid,cmd
done
```

**Fix zombies:**
```bash
# Zombies usually resolve when parent process restarts
# Find the problematic parent service
ps -eo pid,ppid,stat,cmd | awk '$3 ~ /Z/'

# If it's a Docker container, restart it
docker ps | grep PARENT_NAME
docker restart CONTAINER_ID

# If it's a system service
systemctl restart SERVICE_NAME

# Last resort - reboot clears all zombies
reboot
```

### 2. System Restart Required

**Why restart is needed:**
- Kernel update
- Critical security update
- Core system library update

**Check what needs restart:**
```bash
# See which packages require restart
cat /var/run/reboot-required.pkgs

# Check current kernel vs running kernel
uname -r                    # Running kernel
ls /boot/vmlinuz-* | tail -1 # Installed kernel
```

**Safe restart procedure:**
```bash
# 1. Save current docker containers state
docker ps -a > ~/docker-containers-before-reboot.txt

# 2. Check no critical operations running
docker ps | grep -E "(backup|migration|import)"

# 3. Schedule reboot (optional - in 5 minutes)
shutdown -r +5 "Server rebooting for updates"

# 4. Or reboot immediately
reboot
```

### 3. Memory & Swap Usage (49% RAM, 21% Swap)

**Current status: ⚠️ Borderline**
- 49% memory is okay but watch for spikes
- 21% swap usage indicates memory pressure
- Should investigate what's consuming memory

**Check memory consumers:**
```bash
# Top memory users
ps aux --sort=-%mem | head -20

# Docker container memory
docker stats --no-stream --format "table {{.Name}}\t{{.MemUsage}}\t{{.MemPerc}}"

# System memory breakdown
free -h
vmstat 1 5
```

**Set memory limits on containers:**
```bash
# Check containers without memory limits
docker ps --format '{{.Names}}' | while read container; do
    limit=$(docker inspect $container | jq '.[0].HostConfig.Memory')
    if [ "$limit" == "0" ]; then
        echo "No limit: $container"
    fi
done

# Set memory limit (example)
docker update --memory="2g" --memory-swap="2g" CONTAINER_NAME
```

### 4. High Process Count (545)

**Normal range: 150-300 for basic server**
545 is high - likely from Docker containers

**Investigate:**
```bash
# Processes by count
ps aux | awk '{print $1}' | sort | uniq -c | sort -rn | head -10

# Docker container processes
docker ps --format '{{.Names}}' | while read container; do
    count=$(docker top $container | wc -l)
    echo "$container: $count processes"
done

# Find containers with excessive processes
docker ps --format '{{.Names}}' | while read container; do
    count=$(docker top $container 2>/dev/null | wc -l)
    if [ "$count" -gt 50 ]; then
        echo "⚠️  $container: $count processes"
    fi
done
```

### 5. System Updates (215 available)

**Security risk:** Unpatched vulnerabilities

**Update safely:**
```bash
# 1. Check available updates
apt list --upgradable

# 2. Update package list
apt-get update

# 3. Upgrade packages (non-interactive)
apt-get upgrade -y

# 4. Upgrade with auto-handle new configs
apt-get dist-upgrade -y

# 5. Remove old packages
apt-get autoremove -y

# 6. Clean cache
apt-get clean

# 7. Check if reboot needed
[ -f /var/run/reboot-required ] && echo "Reboot required" || echo "No reboot needed"
```

**Automate updates (optional):**
```bash
# Install unattended-upgrades
apt-get install unattended-upgrades -y

# Configure automatic security updates
cat > /etc/apt/apt.conf.d/50unattended-upgrades << 'EOF'
Unattended-Upgrade::Allowed-Origins {
    "${distro_id}:${distro_codename}-security";
};
Unattended-Upgrade::Automatic-Reboot "false";
EOF

# Enable automatic updates
dpkg-reconfigure -plow unattended-upgrades
```

---

## Comprehensive Monitoring Setup

### Create Full System Monitor

```bash
cat > /usr/local/bin/full-monitor.sh << 'EOF'
#!/bin/bash

LOG_FILE="/var/log/system-monitor.log"
ALERT_DISK=85
ALERT_MEM=80
ALERT_SWAP=50

{
    echo "======================================="
    echo "Full System Monitor - $(date)"
    echo "======================================="
    
    # Storage
    DISK_USAGE=$(df / | tail -1 | awk '{print $5}' | sed 's/%//')
    echo "DISK: ${DISK_USAGE}%"
    [ "$DISK_USAGE" -gt "$ALERT_DISK" ] && echo "⚠️  ALERT: Disk usage critical!"
    
    # Memory
    MEM_USAGE=$(free | grep Mem | awk '{print int($3/$2*100)}')
    SWAP_USAGE=$(free | grep Swap | awk '{print int($3/$2*100)}')
    echo "MEMORY: ${MEM_USAGE}%"
    echo "SWAP: ${SWAP_USAGE}%"
    [ "$MEM_USAGE" -gt "$ALERT_MEM" ] && echo "⚠️  ALERT: High memory usage!"
    [ "$SWAP_USAGE" -gt "$ALERT_SWAP" ] && echo "⚠️  ALERT: High swap usage!"
    
    # Zombies
    ZOMBIES=$(ps aux | awk '{if ($8=="Z") print $0}' | wc -l)
    echo "ZOMBIES: $ZOMBIES"
    [ "$ZOMBIES" -gt 5 ] && echo "⚠️  ALERT: Too many zombie processes!"
    
    # Docker
    DOCKER_RUNNING=$(docker ps -q | wc -l)
    DOCKER_DEAD=$(docker ps -a -f status=exited -q | wc -l)
    echo "DOCKER: $DOCKER_RUNNING running, $DOCKER_DEAD stopped"
    [ "$DOCKER_DEAD" -gt 10 ] && echo "⚠️  Consider cleaning stopped containers"
    
    # Load average
    LOAD=$(uptime | awk -F'load average:' '{print $2}' | awk '{print $1}' | sed 's/,//')
    echo "LOAD: $LOAD"
    
    # Failed services
    FAILED=$(systemctl list-units --state=failed --no-pager --no-legend | wc -l)
    echo "FAILED SERVICES: $FAILED"
    [ "$FAILED" -gt 0 ] && systemctl list-units --state=failed --no-pager --no-legend
    
    echo ""
} | tee -a "$LOG_FILE"

EOF

chmod +x /usr/local/bin/full-monitor.sh
```

### Schedule Monitoring

```bash
# Add to crontab for hourly monitoring
(crontab -l 2>/dev/null; echo "0 * * * * /usr/local/bin/full-monitor.sh") | crontab -

# Or combine with storage check
cat > /usr/local/bin/daily-health-check.sh << 'EOF'
#!/bin/bash
/usr/local/bin/system-health.sh
/usr/local/bin/check-storage.sh
/usr/local/bin/full-monitor.sh
EOF

chmod +x /usr/local/bin/daily-health-check.sh

# Run daily at 9 AM
(crontab -l 2>/dev/null; echo "0 9 * * * /usr/local/bin/daily-health-check.sh > /var/log/daily-health.log") | crontab -
```

---

## Immediate Actions for Your VM

Based on your current status:

### 1. **CRITICAL: Handle Zombie Processes**
```bash
# Find and document zombies
ps aux | awk '{if ($8=="Z") print $0}' > ~/zombie-processes.txt

# Find parent process
ps -eo pid,ppid,stat,cmd | awk '$3 ~ /Z/ {print "Zombie: " $1 " Parent: " $2 " Cmd: " $4}'

# Usually Docker containers - restart them
docker ps | head -20
```

### 2. **IMPORTANT: System Restart**
```bash
# Check what needs restart
cat /var/run/reboot-required.pkgs

# Plan restart during low-traffic time
# Coolify and containers will auto-restart
shutdown -r +60 "Scheduled restart for kernel updates"

# Or do it now if it's okay
reboot
```

### 3. **RECOMMENDED: Update System**
```bash
# Update everything
apt-get update && apt-get upgrade -y && apt-get dist-upgrade -y
apt-get autoremove -y && apt-get clean

# This will likely require reboot after
```

### 4. **MONITOR: Memory Pressure**
```bash
# Check top memory users
docker stats --no-stream --format "table {{.Name}}\t{{.MemUsage}}\t{{.MemPerc}}" | sort -k 3 -rn

# If any container uses >2GB, investigate
docker inspect CONTAINER_NAME | jq '.[0].HostConfig.Memory'

# Set limits if needed
docker update --memory="2g" CONTAINER_NAME
```

### 5. **OPTIONAL: Reduce Process Count**
```bash
# Stop unused containers
docker ps -a | grep Exited
docker rm $(docker ps -a -f status=exited -q)

# Check for unnecessary services
systemctl list-units --type=service --state=running
```

---

## Health Monitoring Checklist

Run this weekly:

```bash
# Weekly health check
cat > ~/weekly-check.sh << 'EOF'
#!/bin/bash

echo "=== WEEKLY SYSTEM HEALTH CHECK ==="
echo ""

echo "✓ Disk usage:"
df -h / | tail -1

echo "✓ Docker cleanup:"
docker system prune -af --volumes

echo "✓ System updates:"
apt-get update && apt-get upgrade -y
apt-get autoremove -y && apt-get clean

echo "✓ Log cleanup:"
journalctl --vacuum-time=14d

echo "✓ Backup check:"
du -sh /data/coolify/backups/*
echo "  (Keep only last 2-3 backups)"

echo "✓ Zombie processes:"
ps aux | awk '{if ($8=="Z") print $0}' | wc -l

echo "✓ Memory usage:"
free -h

echo "✓ Restart required?"
[ -f /var/run/reboot-required ] && echo "  YES - schedule restart" || echo "  NO"

echo ""
echo "=== DONE ==="
EOF

chmod +x ~/weekly-check.sh
```

---

## Summary

Your VM filled up because:
1. **Coolify backups**: 43GB (5 weekly backups @ 8.7GB each)
2. **PostgreSQL volume**: 41.5GB (single database)
3. **Docker overlay2**: 35GB (container filesystems)
4. **Other volumes**: 15GB

Your VM also needs attention for:
1. **10 zombie processes** - Find parent and restart it
2. **System restart required** - Schedule reboot for kernel updates
3. **21% swap usage** - Memory pressure, monitor containers
4. **215 updates** - Apply security patches
5. **545 processes** - High but normal for Docker host

**Regular maintenance** (run weekly):
- `docker system prune -af`
- `docker volume prune -f`
- `journalctl --vacuum-time=7d`
- Check `/data/coolify/backups` and keep only last 2-3
- Monitor with `/usr/local/bin/system-health.sh`
- Update system: `apt-get update && apt-get upgrade -y`
- Reboot if kernel updates applied

---

## Existing Tools in /usr/local/bin

Your VM already has these tools installed. Here's what they do and whether you need them:

### 1. **docker-compose** ✅ KEEP
**Purpose:** Orchestrate multi-container Docker applications
```bash
# Check version
docker-compose --version

# Usage (if you have docker-compose.yml files)
docker-compose up -d
docker-compose down
docker-compose logs
```
**Should I remove?** **NO** - Actively used by many projects

---

### 2. **kubectl** ⚠️ REVIEW
**Purpose:** Kubernetes cluster management CLI
```bash
# Check if you have a cluster
kubectl cluster-info
kubectl get nodes

# Check if connected to anything
kubectl config current-context
```
**Should I remove?** 
- If command fails or shows no cluster → **YES, remove it**
- If you're running K8s workloads → **KEEP**

**Remove if unused:**
```bash
rm /usr/local/bin/kubectl
```

---

### 3. **minikube** ⚠️ PROBABLY REMOVE
**Purpose:** Run local Kubernetes cluster (development/testing)
**Size:** ~90MB (you have minikube-linux-amd64 in /root at 92MB)

```bash
# Check if running
minikube status

# Check if you have clusters
minikube profile list
```

**Should I remove?** 
- **YES** - If not actively using Kubernetes
- Minikube is for local dev, not production servers
- You're already using Docker/Coolify, don't need minikube

**Remove:**
```bash
minikube delete --all  # Delete any clusters
rm /usr/local/bin/minikube
rm ~/minikube-linux-amd64  # Free 92MB
rm -rf ~/.minikube  # Free 193MB
```
**Total freed: ~285MB**

---

### 4. **crictl** ⚠️ PROBABLY REMOVE
**Purpose:** CLI for Container Runtime Interface (alternative to docker)
**Used by:** Kubernetes, not standalone Docker

```bash
# Check if configured
crictl info
crictl ps
```

**Should I remove?**
- **YES** - If you're not using Kubernetes/containerd
- You're using Docker, so you don't need crictl

**Remove:**
```bash
rm /usr/local/bin/crictl
```

---

### 5. **cri-dockerd** ⚠️ PROBABLY REMOVE
**Purpose:** Docker Engine shim for Kubernetes (141MB in /root)
**Used by:** Allows Kubernetes to use Docker as container runtime

```bash
# Check if running
systemctl status cri-docker
ps aux | grep cri-docker
```

**Should I remove?**
- **YES** - If you're not using Kubernetes
- This is only needed if using Docker with Kubernetes

**Remove:**
```bash
systemctl stop cri-docker 2>/dev/null
systemctl disable cri-docker 2>/dev/null
rm /usr/local/bin/cri-dockerd
rm -rf ~/cri-dockerd  # Free 141MB
```
**Total freed: ~141MB**

---

### 6. **aws & aws_completer** ✅ PROBABLY KEEP
**Purpose:** AWS CLI for managing AWS resources
**Size:** ~249MB in ~/aws

```bash
# Check if configured
aws configure list
aws s3 ls 2>/dev/null

# Check usage history
history | grep aws | tail -20
```

**Should I remove?**
- **KEEP** - If you use AWS S3, EC2, RDS, etc.
- **REMOVE** - If you don't use AWS at all

**Check what's using it:**
```bash
# Check for AWS backups or services
grep -r "aws" /data/coolify/ 2>/dev/null
docker ps | grep -i aws
```

**Remove if unused:**
```bash
rm /usr/local/bin/aws
rm /usr/local/bin/aws_completer
rm -rf ~/aws  # Free 249MB
rm -rf ~/.aws
```
**Total freed: ~249MB**

---

## Cleanup Recommendation for Your VM

### Total Space You Can Reclaim: **~675MB**

#### Safe to Remove (if not using Kubernetes):
```bash
# 1. Remove Minikube (285MB)
minikube delete --all
rm /usr/local/bin/minikube
rm ~/minikube-linux-amd64
rm -rf ~/.minikube

# 2. Remove CRI tools (141MB)
systemctl stop cri-docker 2>/dev/null
systemctl disable cri-docker 2>/dev/null
rm /usr/local/bin/cri-dockerd
rm /usr/local/bin/crictl
rm -rf ~/cri-dockerd

# 3. Remove kubectl if not using K8s
rm /usr/local/bin/kubectl

# Check disk space after cleanup
df -h
```

#### Consider Removing (if not using AWS):
```bash
# Only if you don't use AWS services
rm /usr/local/bin/aws
rm /usr/local/bin/aws_completer
rm -rf ~/aws
rm -rf ~/.aws
# Freed: 249MB
```

#### Keep:
- **docker-compose** - Actively used
- **aws** (if using AWS S3 for backups or services)

---

## Other Large Files in /root to Review

From your earlier scan, you have:

```bash
# Large files/folders in /root:
602M    /root/opekepay_dump.sql      # Old database dump
1.5G    /root/maps_reviews          # Project data
1.8G    /root/.cache                # Temporary cache
1.8G    /root/.vscode-server        # VS Code remote
472M    /root/langchain             # Python library
97M     /root/ragflow               # Project
94M     /root/autogen               # Project
19M     /root/tribe                 # Project
```

### Cleanup Old Data
```bash
# 1. Old database dump (602MB) - Delete if backed up
ls -lh /root/opekepay_dump.sql
# If old and backed up:
rm /root/opekepay_dump.sql

# 2. Cache (1.8GB) - Safe to delete
rm -rf /root/.cache
mkdir /root/.cache  # Recreate empty

# 3. VS Code Server (1.8GB) - Only if not using remote VS Code
# Check last access:
ls -la /root/.vscode-server
# If not using anymore:
# rm -rf /root/.vscode-server

# 4. Old projects - Review each one
ls -la /root/maps_reviews
ls -la /root/langchain
ls -la /root/ragflow
ls -la /root/autogen
ls -la /root/tribe

# Delete if obsolete:
# rm -rf /root/PROJECT_NAME

# Check space freed
df -h
```

**Potential total from /root cleanup: ~6GB**

---

## Monitoring Script Quick Start

**The monitoring scripts DON'T EXIST YET. Create all 3 at once:**

```bash
# This will create all monitoring scripts
bash << 'SCRIPT_END'

# 1. Storage monitoring
cat > /usr/local/bin/check-storage.sh << 'EOF'
#!/bin/bash
echo "=== Storage Report $(date) ==="
df -h /
echo -e "\nTop 10 directories:"
du -sh /* 2>/dev/null | sort -h | tail -10
echo -e "\nDocker usage:"
docker system df
echo -e "\nCoolify backups:"
du -sh /data/coolify/backups/* 2>/dev/null
EOF
chmod +x /usr/local/bin/check-storage.sh

# 2. System health monitoring
cat > /usr/local/bin/system-health.sh << 'EOF'
#!/bin/bash
echo "=== System Health Report $(date) ==="
echo "DISK: $(df / | tail -1 | awk '{print $5}')"
echo "MEMORY: $(free | grep Mem | awk '{print int($3/$2*100)}')%"
echo "SWAP: $(free | grep Swap | awk '{print int($3/$2*100)}')%"
echo "ZOMBIES: $(ps aux | awk '{if ($8=="Z") print $0}' | wc -l)"
echo "DOCKER: $(docker ps -q | wc -l) running"
uptime
EOF
chmod +x /usr/local/bin/system-health.sh

# 3. Full monitoring
cat > /usr/local/bin/full-monitor.sh << 'EOF'
#!/bin/bash
/usr/local/bin/system-health.sh
echo ""
/usr/local/bin/check-storage.sh
EOF
chmod +x /usr/local/bin/full-monitor.sh

echo "✅ Monitoring scripts created!"
echo "Run them with:"
echo "  /usr/local/bin/system-health.sh"
echo "  /usr/local/bin/check-storage.sh"
echo "  /usr/local/bin/full-monitor.sh"

SCRIPT_END
```

**Then run your first check:**
```bash
/usr/local/bin/system-health.sh
```

---

## Quick Cleanup Script

**Create and run this cleanup script:**

```bash
cat > ~/cleanup-vm.sh << 'EOF'
#!/bin/bash

echo "=== VM Cleanup Script ==="
echo ""

# 1. Remove Kubernetes tools (not needed)
echo "Removing Kubernetes tools..."
minikube delete --all 2>/dev/null
rm -f /usr/local/bin/minikube
rm -f /usr/local/bin/kubectl
rm -f /usr/local/bin/crictl
rm -f /usr/local/bin/cri-dockerd
rm -f ~/minikube-linux-amd64
rm -rf ~/.minikube
rm -rf ~/cri-dockerd

# 2. Clear caches
echo "Clearing caches..."
rm -rf /root/.cache
mkdir /root/.cache

# 3. Docker cleanup
echo "Docker cleanup..."
docker system prune -af --volumes
docker builder prune -af

# 4. System cleanup
echo "System cleanup..."
apt-get autoremove -y
apt-get clean
journalctl --vacuum-time=7d

# 5. Check Coolify backups
echo "Coolify backup sizes:"
du -sh /data/coolify/backups/* 2>/dev/null

echo ""
echo "=== Cleanup Complete ==="
echo "Current disk usage:"
df -h /

EOF

chmod +x ~/cleanup-vm.sh
```

**Then run it:**
```bash
~/cleanup-vm.sh
```

**Expected space freed: 3-7GB**

