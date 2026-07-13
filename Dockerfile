ARG PYTHON_IMAGE=python:3.10-slim
FROM ${PYTHON_IMAGE}

WORKDIR /app

COPY pyproject.toml README.md LICENSE /app/
COPY src /app/src

ARG INSTALL_EXTRAS=false
RUN python -m pip install --no-cache-dir --upgrade pip && \
    if [ "$INSTALL_EXTRAS" = "true" ]; then \
        python -m pip install --no-cache-dir ".[api,documents]"; \
    else \
        python -m pip install --no-cache-dir ".[api]"; \
    fi

ENV TZ=Asia/Shanghai \
    API_PORT=8000 \
    PYTHONUNBUFFERED=1

RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"

ENTRYPOINT ["noteforge"]
CMD ["api", "--host", "0.0.0.0", "--port", "8000"]
