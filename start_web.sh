#!/bin/bash

echo "========================================"
echo "🌍 ChinArXiv 论文翻译器 Web版"
echo "========================================"

# 检查babeldoc服务是否运行
echo ""
echo "1. 检查babeldoc服务..."
if curl -s http://localhost:8321/health > /dev/null 2>&1; then
    echo "✅ Babeldoc服务正在运行"
else
    echo "⚠️  Babeldoc服务未运行！"
    echo "请先启动babeldoc服务："
    echo "  bash babeldoc/start_server.sh"
    echo ""
    read -p "是否现在启动babeldoc服务? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "启动babeldoc服务..."
        cd babeldoc
        bash start_server.sh &
        cd ..
        echo "等待服务启动..."
        sleep 5
    else
        echo "请手动启动babeldoc服务后再运行此脚本"
        exit 1
    fi
fi

# 检查config.py
echo ""
echo "2. 检查配置文件..."
if [ -f "config.py" ]; then
    echo "✅ 配置文件存在"
else
    echo "❌ 配置文件不存在！"
    echo "请创建 config.py 文件并配置API密钥"
    exit 1
fi

# 创建必要的目录
echo ""
echo "3. 创建必要目录..."
mkdir -p arxiv_cache
mkdir -p uploads
mkdir -p static
echo "✅ 目录创建完成"

# 检查依赖
echo ""
echo "4. 检查依赖..."
python3 -c "import fastapi" 2>/dev/null
if [ $? -eq 0 ]; then
    echo "✅ FastAPI已安装"
else
    echo "⚠️  FastAPI未安装"
    read -p "是否现在安装依赖? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        pip install -r requirements_web.txt
    else
        echo "请先安装依赖: pip install -r requirements_web.txt"
        exit 1
    fi
fi

# 启动Web应用
echo ""
echo "========================================"
echo "🚀 启动Web应用..."
echo "========================================"
echo ""
echo "访问地址: http://localhost:12985"
echo "按 Ctrl+C 停止服务"
echo ""

python3 web_main.py

