#!/usr/bin/env bash
# Start script for Crypto Strategy API backend

BACKEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TMP_DIR="${TMPDIR:-/tmp}"
[ ! -d "$TMP_DIR" ] && TMP_DIR="/tmp"
LOG_FILE="$TMP_DIR/cryptostrategy-backend.log"
PID_FILE="$TMP_DIR/cryptostrategy-backend.pid"
PORT=${PORT:-8001}

cd "$BACKEND_DIR"

case "$1" in
  start)
    if [ -f "$PID_FILE" ] && kill -0 "$(cat $PID_FILE)" 2>/dev/null; then
      echo "Backend already running (PID: $(cat $PID_FILE))"
      exit 0
    fi
    echo "Starting Crypto Strategy API on port $PORT..."
    setsid python3 -m uvicorn app.main:app --host 0.0.0.0 --port $PORT \
      < /dev/null > "$LOG_FILE" 2>&1 &
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
    tail -f "$LOG_FILE"
    ;;
  *)
    echo "Usage: $0 {start|stop|restart|status|logs}"
    exit 1
    ;;
esac
