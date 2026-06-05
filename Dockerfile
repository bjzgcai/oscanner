FROM node:22-bookworm AS dashboard-builder

WORKDIR /src

COPY frontend/webapp/package.json frontend/webapp/package-lock.json ./frontend/webapp/
WORKDIR /src/frontend/webapp
RUN npm ci

WORKDIR /src
COPY frontend/webapp ./frontend/webapp
COPY plugins ./plugins
RUN cd frontend/webapp && npm run build

FROM python:3.12-bookworm AS python-runtime

FROM node:22-bookworm AS runtime

ENV VIRTUAL_ENV=/opt/oscanner-venv
ENV PATH="/opt/oscanner-venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
ENV PYTHONUNBUFFERED=1
ENV OSCANNER_HOME=/data/oscanner
ENV OSCANNER_DATA_DIR=/data/oscanner/data
ENV OSCANNER_PLUGINS_DIR=/app/plugins
ENV OSCANNER_CHECKERS_DIR=/app/checkers
ENV RUNNER_SERVICE_URL=http://127.0.0.1:8001
ENV REPOS_RUNNER_EXECUTOR=local

COPY --from=python-runtime /usr/local /usr/local

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        cargo \
        chromium \
        cmake \
        default-jdk-headless \
        fonts-noto-cjk \
        git \
        golang-go \
        gradle \
        maven \
        meson \
        nginx \
        ninja-build \
        openssh-client \
        rustc \
    && rm -f /etc/nginx/sites-enabled/default \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv "$VIRTUAL_ENV" \
    && "$VIRTUAL_ENV/bin/python" -m pip install --upgrade pip setuptools wheel

WORKDIR /app
COPY pyproject.toml README.md README_en.md LICENSE ./
COPY backend ./backend
COPY cli ./cli
COPY checkers ./checkers
COPY plugins ./plugins
COPY benchmark ./benchmark

RUN pip install --no-cache-dir ".[dev]" -r backend/repos_runner/requirements.txt

COPY --from=dashboard-builder /src/frontend/webapp/out /usr/share/nginx/html
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY docker/entrypoint.sh /usr/local/bin/oscanner-docker-entrypoint

RUN mkdir -p /data/oscanner/data /run/nginx \
    && chmod +x /usr/local/bin/oscanner-docker-entrypoint

EXPOSE 80

CMD ["oscanner-docker-entrypoint"]
