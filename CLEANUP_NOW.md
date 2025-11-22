# 🚨 URGENT: Jenkins Disk Space Cleanup

## Run These Commands on Your Jenkins Server NOW

### Option 1: Quick Cleanup (Run this first)
```bash
# SSH into your Jenkins server
ssh your-user@your-jenkins-server

# Run comprehensive Docker cleanup
sudo docker system prune -af --volumes
sudo docker builder prune -af

# Check results
df -h
docker system df
```

### Option 2: Use the Cleanup Script
```bash
# From your local machine, copy the script
scp /Users/synh/Code/Personal/health_management/scripts/cleanup-jenkins-docker.sh your-user@your-jenkins-server:/tmp/

# SSH into Jenkins server
ssh your-user@your-jenkins-server

# Run the script
sudo bash /tmp/cleanup-jenkins-docker.sh
```

### Option 3: Manual Cleanup (if above doesn't work)
```bash
# SSH into Jenkins server
ssh your-user@your-jenkins-server

# Stop Jenkins temporarily (optional, for deeper cleanup)
sudo systemctl stop jenkins

# Clean Docker resources step by step
sudo docker container prune -f
sudo docker image prune -af
sudo docker volume prune -f
sudo docker builder prune -af
sudo docker network prune -f

# Clean Jenkins workspace (be careful!)
# Only do this if you're sure
cd /var/lib/jenkins/workspace
sudo rm -rf */

# Clean old Docker logs
sudo truncate -s 0 /var/lib/docker/containers/*/*-json.log

# Restart Jenkins
sudo systemctl start jenkins

# Verify disk space
df -h
docker system df
```

## What This Will Do

The cleanup will remove:
- ✅ All stopped containers
- ✅ All dangling images (untagged)
- ✅ All unused images (not used by any container)
- ✅ All unused volumes
- ✅ All build cache
- ✅ All unused networks

**This is safe** - it won't delete:
- ❌ Running containers
- ❌ Images currently in use
- ❌ Jenkins configuration
- ❌ Your source code

## Expected Results

Before cleanup, you might see:
```
TYPE            TOTAL     ACTIVE    SIZE      RECLAIMABLE
Images          50        5         15GB      12GB (80%)
Containers      20        2         500MB     400MB (80%)
Local Volumes   10        2         5GB       4GB (80%)
Build Cache     100       0         20GB      20GB (100%)
```

After cleanup:
```
TYPE            TOTAL     ACTIVE    SIZE      RECLAIMABLE
Images          5         5         3GB       0B (0%)
Containers      2         2         100MB     0B (0%)
Local Volumes   2         2         1GB       0B (0%)
Build Cache     0         0         0B        0B (0%)
```

## After Cleanup: Trigger New Build

Once cleanup is complete:

1. Go to Jenkins: http://your-jenkins-server:8080
2. Navigate to your pipeline
3. Click "Build with Parameters"
4. Select branch: `develop`
5. Click "Build"

The new build should:
- ✅ Complete without "No space left on device" errors
- ✅ Use the optimized Dockerfile (commit db6aa57)
- ✅ Install smaller PyTorch CPU version (~100MB vs 2GB)
- ✅ Deploy successfully to Cloud Run

## Monitoring

After the build, monitor disk usage:

```bash
# Check every hour
watch -n 3600 'df -h && echo "---" && docker system df'
```

## Need More Space?

If cleanup doesn't free enough space, you'll need to:

1. **Increase disk size** on your Jenkins server
2. **Move Docker data directory** to a larger volume
3. **Set up automatic cleanup** in Jenkins

Let me know if you need help with any of these options!

---

## Quick Reference

| Command | What it does |
|---------|-------------|
| `docker system prune -af --volumes` | Remove everything unused |
| `docker builder prune -af` | Remove all build cache |
| `df -h` | Check disk space |
| `docker system df` | Check Docker disk usage |
| `du -sh /var/lib/docker/*` | See what's using space |

## Status

- ✅ Code optimizations: DONE (commit db6aa57)
- ⏳ Disk cleanup: **WAITING FOR YOU TO RUN**
- ⏳ New build: After cleanup
- ⏳ Deployment: After successful build

