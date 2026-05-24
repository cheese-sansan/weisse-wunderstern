FROM python:3.10-slim

WORKDIR /app

# Copy source code
COPY . /app

# Set timezone
ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Make run script executable
RUN chmod +x /app/run.sh

CMD ["/bin/bash", "/app/run.sh"]
