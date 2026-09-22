#!/usr/bin/env bash
# Start script for Crypto Strategy API backend

BACKEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TMP_DIR="${TMPDIR:-/tmp}"
[ ! -d "$TMP_DIR" ] && TMP_DIR="/tmp"
LOG_FILE="$TMP_DIR/cryptostrategy-backend.log"
PID_FILE="$TMP_DIR/cryptostrategy-backend.pid"
PORT=${PORT:-8001}
MAX_LOG_SIZE=${MAX_LOG_SIZE:-5242880}  # 5MB — rotate keeping .1/.2/.3

rotate_logs() {
  if [ -f "$LOG_FILE" ]; then
    size=$(wc -c < "$LOG_FILE" 2>/dev/null || echo 0)
    if [ "$size" -ge "$MAX_LOG_SIZE" ]; then
      rm -f "${LOG_FILE}.3"
      [ -f "${LOG_FILE}.2" ] && mv "${LOG_FILE}.2" "${LOG_FILE}.3"
      [ -f "${LOG_FILE}.1" ] && mv "${LOG_FILE}.1" "${LOG_FILE}.2"
      mv "$LOG_FILE" "${LOG_FILE}.1"
      echo "Rotated logs (was ${size} bytes)"
    fi
  fi
}

cd "$BACKEND_DIR"

case "$1" in
  start)
    if [ -f "$PID_FILE" ] && kill -0 "$(cat $PID_FILE)" 2>/dev/null; then
      echo "Backend already running (PID: $(cat $PID_FILE))"
      exit 0
    fi
    rotate_logs
    echo "Starting Crypto Strategy API on port $PORT..."
    echo "===== $(date '+%Y-%m-%d %H:%M:%S') starting on port $PORT =====" >> "$LOG_FILE"
    setsid python3 -m uvicorn app.main:app --host 0.0.0.0 --port $PORT \
      < /dev/null >> "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"
    sleep 3
    if kill -0 "$(cat $PID_FILE)" 2>/dev/null; then
      echo "Backend started (PID: $(cat $PID_FILE))"
      echo "URL: http://localhost:$PORT"
      echo "Docs: http://localhost:$PORT/docs"
    else
      echo "Backend failed to start. Check logs: $LOG_FILE"
      cat "$LOG_FILE" | tail -20
    fi
    ;;
  stop)
    if [ -f "$PID_FILE" ]; then
      PID=$(cat "$PID_FILE")
      kill "$PID" 2>/dev/null
      rm -f "$PID_FILE"
    fi
    pkill -f "uvicorn app.main:app.*8001" 2>/dev/null
    sleep 1
    echo "Backend stopped"
    ;;
  restart)
    $0 stop
    sleep 2
    $0 start
    ;;
  status)
    if [ -f "$PID_FILE" ] && kill -0 "$(cat $PID_FILE)" 2>/dev/null; then
      echo "Backend is running (PID: $(cat $PID_FILE))"
      curl -s http://localhost:$PORT/health 2>/dev/null && echo ""
    else
      echo "Backend is not running"
    fi
    ;;
  logs)
    tail -n 100 -f "$LOG_FILE"
    ;;
  logs-all)
    tail -n 100 "${LOG_FILE}.3" "${LOG_FILE}.2" "${LOG_FILE}.1" "$LOG_FILE" 2>/dev/null
    ;;
  *)
    echo "Usage: $0 {start|stop|restart|status|logs|logs-all}"
    exit 1
    ;;
esac
