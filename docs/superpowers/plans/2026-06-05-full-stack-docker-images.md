# Full-Stack Docker Images Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add single-image Docker packaging for Oscanner and Courses with nginx-served static assets and in-container FastAPI backends.

**Architecture:** Each repository gets a multi-stage Dockerfile. Node builds frontend assets, Python installs backend/runtime dependencies, nginx serves static files, and a small entrypoint starts backend process(es) before nginx runs in the foreground.

**Tech Stack:** Docker, nginx, Node 22, Python 3.12, FastAPI, uvicorn, Next.js static export, Vite static build.

---

### Task 1: Oscanner Docker Assets

**Files:**
- Create: `Dockerfile`
- Create: `.dockerignore`
- Create: `docker/nginx.conf`
- Create: `docker/entrypoint.sh`

- [ ] **Step 1: Add Dockerfile with frontend build and Python runtime**

Create a multi-stage root Dockerfile that builds `frontend/webapp/out`, installs the Python package into a virtualenv, keeps plugin/checker source under `/app`, installs nginx and runner tooling, and exposes port 80.

- [ ] **Step 2: Add nginx config**

Proxy `/api`, `/docs`, `/openapi.json`, `/health`, and `/version` to evaluator port 8000. Serve the dashboard static export with `try_files $uri $uri/ /index.html`.

- [ ] **Step 3: Add entrypoint**

Start evaluator on 8000 and runner on 8001, then run nginx in the foreground. Exit if either backend exits.

- [ ] **Step 4: Add docker ignore rules**

Exclude secrets, caches, local virtualenvs, node_modules, generated frontend outputs, and runtime repository data.

### Task 2: Courses Docker Assets

**Files:**
- Create: `/home/carter/working/courses/Dockerfile`
- Create: `/home/carter/working/courses/.dockerignore`
- Create: `/home/carter/working/courses/docker/nginx.conf`
- Create: `/home/carter/working/courses/docker/entrypoint.sh`

- [ ] **Step 1: Add Dockerfile with root-based Vite build**

Build the frontend using `VITE_APP_BASE=/ npx vite build`, install backend requirements into a virtualenv, copy static assets into nginx, and expose port 80.

- [ ] **Step 2: Add nginx config**

Proxy `/api`, `/static`, `/docs`, and `/openapi.json` to backend port 8003. Serve the Vite app with SPA fallback.

- [ ] **Step 3: Add entrypoint**

Start the Courses backend on 8003, then run nginx in the foreground. Exit if the backend exits.

- [ ] **Step 4: Add docker ignore rules**

Exclude secrets, caches, local virtualenvs, node_modules, frontend dist, backend runtime result data, and uploaded static output.

### Task 3: Verification

**Files:**
- Verify: both Dockerfiles
- Verify: both nginx configs
- Verify: both entrypoint scripts

- [ ] **Step 1: Static syntax checks**

Run shell syntax checks on entrypoints and nginx config checks if nginx is locally available.

- [ ] **Step 2: Docker build checks**

Run `docker build -t oscanner-fullstack:local .` from `/home/carter/working/oscanner` and `docker build -t courses-fullstack:local .` from `/home/carter/working/courses` if Docker is available.

- [ ] **Step 3: Review git diffs**

Confirm no secrets or generated cache/runtime files are included in the changes.
