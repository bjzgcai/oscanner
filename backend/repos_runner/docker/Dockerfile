FROM python:3.12-bookworm AS python-runtime

FROM node:22-bookworm

ENV VIRTUAL_ENV=/opt/oscanner-venv
ENV PATH="/opt/oscanner-venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

COPY --from=python-runtime /usr/local /usr/local

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        chromium \
        fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv "$VIRTUAL_ENV" \
    && "$VIRTUAL_ENV/bin/python" -m pip install --upgrade pip setuptools wheel \
    && "$VIRTUAL_ENV/bin/python" -m pip install \
        pytest \
        pytest-json-report \
        fastapi==0.116.1 \
        "uvicorn[standard]==0.35.0" \
        "pydantic>=2.12,<3" \
        "pydantic-settings>=2.13,<3" \
        httpx==0.28.1 \
        websockets==15.0.1 \
    && chmod -R a+rwx "$VIRTUAL_ENV"
