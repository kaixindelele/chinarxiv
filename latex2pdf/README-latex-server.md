# LaTeX编译服务器

独立的LaTeX编译服务，支持HTTP API接口，用于将LaTeX文档编译为PDF文件。支持依赖文件处理、异步编译、任务管理等高级功能。

## 🌟 功能特色

- **HTTP API接口**：RESTful API设计，易于集成
- **同步/异步编译**：支持两种编译模式，满足不同需求
- **依赖文件支持**：自动处理.cls、.sty、.bib等依赖文件
- **完整编译流程**：支持pdflatex → bibtex → pdflatex → pdflatex完整流程
- **任务管理**：异步任务状态跟踪和管理
- **自动清理**：定期清理过期任务和临时文件
- **Docker支持**：提供完整的Docker部署方案
- **健康检查**：内置健康检查和监控接口

## 📋 API接口

### 健康检查
```http
GET /health
```

响应示例：
```json
{
    "status": "healthy",
    "service": "LaTeX Compile Server",
    "active_tasks": 2,
    "timestamp": "2025-01-01T12:00:00"
}
```

### 同步编译
```http
POST /compile/sync
Content-Type: application/json

{
    "tex_content": "\\documentclass{article}\\begin{document}Hello World\\end{document}",
    "output_name": "test",
    "dependencies": {
        "custom.cls": "base64编码的文件内容",
        "refs.bib": "base64编码的参考文献"
    }
}
```

响应示例：
```json
{
    "success": true,
    "pdf_content": "base64编码的PDF内容",
    "log": "编译日志信息",
    "error": null
}
```

### 异步编译
```http
POST /compile/async
Content-Type: application/json

{
    "tex_content": "LaTeX文档内容",
    "output_name": "document",
    "dependencies": {}
}
```

响应示例：
```json
{
    "success": true,
    "task_id": "task_abc12345",
    "error": null
}
```

### 查询任务状态
```http
GET /status/{task_id}
```

响应示例：
```json
{
    "task_id": "task_abc12345",
    "status": "completed",
    "progress": 100.0,
    "result": {
        "success": true,
        "pdf_content": "base64编码的PDF内容",
        "log": "编译日志",
        "error": null
    },
    "created_at": "2025-01-01T12:00:00",
    "updated_at": "2025-01-01T12:01:30"
}
```

任务状态说明：
- `pending`: 等待处理
- `running`: 正在编译
- `completed`: 编译完成
- `failed`: 编译失败

### 删除任务
```http
DELETE /task/{task_id}
```

## 🚀 快速开始

### 方式1：直接运行（推荐开发）

#### 环境要求
- Python 3.8+
- LaTeX环境（TeX Live完整版）
- 系统依赖：curl（用于健康检查）

#### 安装依赖
```bash
cd latex2pdf
pip install -r requirements-latex-server.txt
```

#### 启动服务器
```bash
python latex_compile_server.py
```

服务器将在 `http://localhost:9851` 启动

#### 测试客户端
```bash
python latex_compile_client.py
```

### 方式2：Docker部署（推荐生产）

#### 构建和启动
```bash
cd latex2pdf
docker-compose -f docker-compose-latex-server.yml up --build -d
```

#### 查看日志
```bash
docker-compose -f docker-compose-latex-server.yml logs -f
```

#### 停止服务
```bash
docker-compose -f docker-compose-latex-server.yml down
```

## 🔧 配置说明

### 服务器配置

在 [`latex_compile_server.py`](latex_compile_server.py:92) 中可以修改：

```python
# 服务器配置
HOST = "0.0.0.0"          # 监听地址
PORT = 9851               # 监听端口
MAX_WORKERS = 4           # 最大并发编译数

# 编译配置
LATEX_CMD = "pdflatex"    # LaTeX命令
LATEX_ARGS = [            # LaTeX参数
    "-interaction=nonstopmode",
    "-file-line-error", 
    "-synctex=1"
]

# 清理配置
CLEANUP_INTERVAL = 3600   # 清理间隔（秒）
TASK_EXPIRE_HOURS = 24    # 任务过期时间（小时）
```

### Docker配置

在 [`docker-compose-latex-server.yml`](docker-compose-latex-server.yml) 中可以修改：

```yaml
services:
  latex-compile-server:
    ports:
      - "9851:9851"       # 端口映射
    
    environment:
      - HOST=0.0.0.0
      - PORT=9851
      - PYTHONUNBUFFERED=1
    
    deploy:
      resources:
        limits:
          cpus: '2.0'     # CPU限制
          memory: 2G      # 内存限制
        reservations:
          cpus: '0.5'
          memory: 512M
```

## 💻 客户端使用

### Python客户端

```python
from latex_compile_client import LaTeXCompileClient

# 创建客户端
client = LaTeXCompileClient("http://localhost:9851")

# 检查服务器状态
if client.check_server_health():
    print("服务器运行正常")

# 同步编译
tex_content = r"""
\documentclass{article}
\usepackage[utf8]{inputenc}
\title{Test Document}
\begin{document}
\maketitle
Hello, LaTeX!
\end{document}
"""

result = client.compile_latex_sync(tex_content, "test_doc")

if result['success']:
    # 保存PDF
    with open('output.pdf', 'wb') as f:
        f.write(result['pdf_content'])
    print("编译成功！")
else:
    print(f"编译失败: {result['error']}")
```

### 带依赖文件的编译

```python
# 准备依赖文件
dependencies = {}

# 读取类文件
with open('custom.cls', 'rb') as f:
    dependencies['custom.cls'] = f.read()

# 读取参考文献
with open('references.bib', 'rb') as f:
    dependencies['references.bib'] = f.read()

# 编译
result = client.compile_latex_sync(
    tex_content=tex_content,
    output_name="paper",
    dependencies=dependencies
)
```

### 异步编译

```python
# 提交异步任务
result = client.compile_latex_async(tex_content, "async_doc")

if result['success']:
    task_id = result['task_id']
    print(f"任务已提交: {task_id}")
    
    # 轮询任务状态
    import time
    while True:
        status = client.get_task_status(task_id)
        print(f"任务状态: {status['status']} ({status['progress']:.1f}%)")
        
        if status['status'] in ['completed', 'failed']:
            break
        
        time.sleep(2)
    
    # 获取结果
    if status['status'] == 'completed':
        pdf_content = status['result']['pdf_content']
        with open('async_output.pdf', 'wb') as f:
            f.write(pdf_content)
        print("异步编译完成！")
```

### 便捷函数

```python
from latex_compile_client import compile_latex_to_pdf

# 一步完成编译
success, result = compile_latex_to_pdf(
    tex_content=tex_content,
    output_name="simple",
    server_url="http://localhost:9851"
)

if success:
    # result是PDF的bytes内容
    with open('simple.pdf', 'wb') as f:
        f.write(result)
    print("编译成功！")
else:
    print(f"编译失败: {result}")
```

## 🔍 故障排除

### 常见问题

1. **服务器启动失败**
   ```bash
   # 检查端口是否被占用
   netstat -tlnp | grep 9851
   
   # 检查LaTeX环境
   pdflatex --version
   bibtex --version
   ```

2. **编译失败**
   - 检查LaTeX语法是否正确
   - 确认依赖文件是否完整
   - 查看编译日志获取详细错误信息

3. **Docker部署问题**
   ```bash
   # 查看容器状态
   docker-compose ps
   
   # 查看详细日志
   docker-compose logs latex-compile-server
   
   # 进入容器调试
   docker-compose exec latex-compile-server bash
   ```

4. **内存不足**
   - 增加Docker内存限制
   - 减少MAX_WORKERS数量
   - 清理临时文件

### 调试模式

启用详细日志：

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# 然后启动服务器或客户端
```

### 性能优化

1. **并发设置**
   ```python
   # 根据CPU核心数调整
   MAX_WORKERS = min(4, os.cpu_count())
   ```

2. **内存管理**
   ```python
   # 定期清理临时文件
   CLEANUP_INTERVAL = 1800  # 30分钟
   ```

3. **网络优化**
   ```python
   # 调整超时设置
   client = LaTeXCompileClient(timeout=300)
   ```

## 📊 监控和日志

### 健康检查

```bash
# 检查服务器状态
curl http://localhost:9851/health

# 使用jq格式化输出
curl -s http://localhost:9851/health | jq
```

### 日志管理

服务器日志包含：
- 编译请求和结果
- 错误信息和堆栈跟踪
- 性能统计
- 任务管理信息

Docker日志查看：
```bash
# 实时日志
docker-compose logs -f latex-compile-server

# 最近100行日志
docker-compose logs --tail=100 latex-compile-server
```

### 性能监控

```python
# 获取服务器状态
import requests
response = requests.get("http://localhost:9851/health")
data = response.json()

print(f"活跃任务数: {data['active_tasks']}")
print(f"服务器状态: {data['status']}")
```

## 🔒 安全考虑

### 网络安全
- 生产环境建议使用反向代理（nginx）
- 启用HTTPS加密
- 限制访问IP范围

### 文件安全
- 自动清理临时文件
- 防止路径遍历攻击
- 限制文件大小和数量

### 资源限制
```yaml
# Docker资源限制
deploy:
  resources:
    limits:
      cpus: '2.0'
      memory: 2G
    reservations:
      cpus: '0.5'
      memory: 512M
```

## 🚀 高级用法

### 自定义LaTeX环境

```dockerfile
# 在Dockerfile中添加额外包
RUN tlmgr install collection-fontsrecommended \
    collection-fontutils \
    collection-langjapanese \
    collection-langchinese
```

### 批量编译

```python
import concurrent.futures
from latex_compile_client import LaTeXCompileClient

client = LaTeXCompileClient()

def compile_document(tex_content, name):
    return client.compile_latex_sync(tex_content, name)

# 并发编译多个文档
documents = [
    ("doc1.tex", "document1"),
    ("doc2.tex", "document2"),
    ("doc3.tex", "document3")
]

with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
    futures = [
        executor.submit(compile_document, tex, name) 
        for tex, name in documents
    ]
    
    for future in concurrent.futures.as_completed(futures):
        result = future.result()
        if result['success']:
            print(f"编译成功: {result}")
        else:
            print(f"编译失败: {result['error']}")
```

### 集成到Web应用

```python
from flask import Flask, request, jsonify
from latex_compile_client import compile_latex_to_pdf

app = Flask(__name__)

@app.route('/compile', methods=['POST'])
def compile_latex():
    data = request.json
    tex_content = data.get('tex_content')
    
    success, result = compile_latex_to_pdf(tex_content)
    
    if success:
        # 返回base64编码的PDF
        import base64
        pdf_base64 = base64.b64encode(result).decode()
        return jsonify({
            'success': True,
            'pdf_content': pdf_base64
        })
    else:
        return jsonify({
            'success': False,
            'error': result
        }), 400

if __name__ == '__main__':
    app.run(debug=True)
```

## 📚 API文档

完整的API文档可以通过以下方式访问：

1. **Swagger UI**：http://localhost:9851/docs
2. **ReDoc**：http://localhost:9851/redoc
3. **OpenAPI JSON**：http://localhost:9851/openapi.json

## 🤝 贡献指南

欢迎提交Issue和Pull Request！

### 开发环境
```bash
# 克隆项目
git clone <repository-url>
cd latex2pdf

# 安装依赖
pip install -r requirements-latex-server.txt

# 运行测试
python latex_compile_client.py
```

### 测试
```bash
# 启动服务器
python latex_compile_server.py

# 在另一个终端运行测试
python latex_compile_client.py
```

## 📄 许可证

本项目遵循相应的开源许可证。

---

**注意**：LaTeX编译服务器需要完整的LaTeX环境支持，建议使用TeX Live完整版以确保最佳兼容性。