#!/bin/bash

# BabelDoc Server 启动脚本

echo "=========================================="
echo "BabelDoc Translation Server"
echo "=========================================="
echo ""

# 检查是否在正确的目录
if [ ! -f "babeldoc/babeldoc_server.py" ]; then
    echo "错误: 请在项目根目录运行此脚本"
    echo "用法: bash babeldoc/start_server.sh"
    exit 1
fi

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到 Python 3"
    exit 1
fi

echo "Python 版本: $(python3 --version)"
echo ""

# 检查依赖
echo "检查依赖..."
if ! python3 -c "import fastapi" 2>/dev/null; then
    echo "警告: 未安装 FastAPI"
    echo "正在安装依赖..."
    pip install -r babeldoc/requirements_server.txt
fi

if ! python3 -c "import uvicorn" 2>/dev/null; then
    echo "警告: 未安装 Uvicorn"
    echo "正在安装依赖..."
    pip install -r babeldoc/requirements_server.txt
fi

echo "✓ 依赖检查完成"
echo ""

# 启动服务器
echo "启动服务器..."
echo "访问地址: http://localhost:8321"
echo "API 文档: http://localhost:8321/docs"
echo "按 Ctrl+C 停止服务器"
echo ""
echo "=========================================="
echo ""

python3 babeldoc/babeldoc_server.py

