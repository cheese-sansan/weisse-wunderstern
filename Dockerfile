ARG PYTHON_IMAGE=python:3.10-slim
FROM ${PYTHON_IMAGE}

WORKDIR /app

COPY requirements-api.txt requirements-extras.txt /app/

# 安装 API 依赖；可选文档解析依赖按需启用。
ARG INSTALL_EXTRAS=false
RUN pip install --no-cache-dir -r requirements-api.txt && \
    if [ "$INSTALL_EXTRAS" = "true" ]; then \
        pip install --no-cache-dir -r requirements-extras.txt; \
    fi

COPY . /app

# 时区
ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

RUN chmod +x /app/run.sh

# MODE=cli 或 api
ENV MODE=api
ENV API_PORT=8000

EXPOSE 8000

ENTRYPOINT ["/bin/bash", "/app/run.sh"]
