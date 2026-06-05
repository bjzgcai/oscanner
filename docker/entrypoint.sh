#!/bin/sh
set -eu

mkdir -p "${OSCANNER_HOME:-/data/oscanner}" "${OSCANNER_DATA_DIR:-/data/oscanner/data}"

uvicorn backend.evaluator.server:app --host 127.0.0.1 --port 8000 &
evaluator_pid="$!"

uvicorn backend.repos_runner.server:app --host 127.0.0.1 --port 8001 &
runner_pid="$!"

nginx -g 'daemon off;' &
nginx_pid="$!"

term_children() {
    kill "$evaluator_pid" "$runner_pid" "$nginx_pid" 2>/dev/null || true
}

trap 'term_children; exit 0' INT TERM

while :; do
    if ! kill -0 "$evaluator_pid" 2>/dev/null; then
        term_children
        wait "$evaluator_pid" 2>/dev/null || true
        exit 1
    fi
    if ! kill -0 "$runner_pid" 2>/dev/null; then
        term_children
        wait "$runner_pid" 2>/dev/null || true
        exit 1
    fi
    if ! kill -0 "$nginx_pid" 2>/dev/null; then
        term_children
        wait "$nginx_pid" 2>/dev/null || true
        exit 1
    fi
    sleep 2
done
