# 使用官方的 Python 镜像作为基础镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 复制当前目录内容到工作目录中
COPY . .

# 安装依赖项
RUN pip install --no-cache-dir --no-progress-bar websockets pycryptodome


# 运行 WebSocket 服务器
CMD ["python", "app.py", "server"]
