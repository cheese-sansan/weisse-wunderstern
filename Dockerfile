FROM python:3.10-slim

WORKDIR /app

# 安装可选文档解析依赖（按需启用）
ARG INSTALL_EXTRAS=false
RUN if [ "$INSTALL_EXTRAS" = "true" ]; then \
        pip install --no-cache-dir \
            pymupdf pdfplumber PyPDF2 \
            python-docx openpyxl python-pptx \
            ebooklib striprtf \
            Pillow pytesseract \
            fastapi uvicorn python-multipart; \
    else \
        pip install --no-cache-dir fastapi uvicorn python-multipart; \
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
