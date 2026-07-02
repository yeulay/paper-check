# 投稿前自检网页版 · 容器镜像(Railway / Render / Fly.io 通用)
FROM python:3.11-slim

WORKDIR /app

# 只装 webapp 需要的依赖(不含监控项目那套)
COPY webapp/requirements.txt webapp/requirements.txt
RUN pip install --no-cache-dir -r webapp/requirements.txt

# webapp 复用 tools/manuscript_check.py 的分析逻辑,两者都要拷进来
COPY tools/ tools/
COPY webapp/ webapp/

ENV PORT=8000
EXPOSE 8000

# shell form 以便展开 $PORT(平台会注入自己的端口)
CMD ["sh", "-c", "uvicorn webapp.main:app --host 0.0.0.0 --port ${PORT}"]
