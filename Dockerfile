# MarketPulse Docker 镜像
FROM python:3.11-slim

LABEL org.opencontainers.image.title="MarketPulse"
LABEL org.opencontainers.image.description="A股市场情绪量化仪表盘"
LABEL org.opencontainers.image.version="2.1.0"

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目文件
COPY . .

# 创建数据目录
RUN mkdir -p data_source data logs backups

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8898/api/v1/health || exit 1

EXPOSE 8898

# 启动: 先下载数据(如果不存在)，再启动服务
CMD ["sh", "-c", "python scripts/setup_data.py 2>/dev/null; exec gunicorn -w 4 -b 0.0.0.0:8898 api.app:app"]
