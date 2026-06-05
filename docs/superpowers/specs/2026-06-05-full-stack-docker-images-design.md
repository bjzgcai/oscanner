# Full-Stack Docker Images Design

## Goal

Create production-oriented single-container images for Oscanner and Courses. Each image serves frontend static assets with nginx and runs the FastAPI backend inside the same container.

## Oscanner Image

The Oscanner image builds the Next.js dashboard as static assets, serves them from nginx on port 80, and proxies API traffic to the evaluator backend on port 8000. The repository runner backend also starts on port 8001 so existing evaluator `/api/runner` proxy behavior continues to work from the same image.

Runtime source code, plugins, checkers, and Python package metadata remain under `/app`. Runtime data is kept under `/data/oscanner` through `OSCANNER_HOME` and `OSCANNER_DATA_DIR`, so callers can mount a volume without writing into the application directory.

## Courses Image

The Courses image builds the Vite frontend with a root base path, serves the output from nginx on port 80, and proxies `/api`, `/static`, `/docs`, and OpenAPI traffic to the FastAPI backend on port 8003.

Runtime backend data and generated static uploads remain under the backend directory unless the caller mounts a volume over those locations. Secrets are supplied through environment variables or mounted env files, not baked into the image.

## Error Handling

Each image uses a small shell entrypoint that starts required backend process(es), exits if a backend dies, and runs nginx in the foreground. This keeps Docker lifecycle behavior simple while avoiding a heavier process supervisor.

## Verification

Verification consists of Dockerfile/config syntax checks and Docker builds for both images. If local Docker is unavailable, the fallback verification is static linting of Dockerfile/nginx/entrypoint content plus frontend/backend dependency checks.
