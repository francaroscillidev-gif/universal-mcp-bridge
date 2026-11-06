#!/usr/bin/env bash
# Quick system health check reporter (disk, memory, uptime)
echo "=== SYSTEM HEALTH REPORT ==="
echo "Date: $(date)"
echo "Uptime: $(uptime)"
echo "Disk space:"
df -h . | head -n 2
