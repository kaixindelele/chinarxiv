# BabelDoc Translation Server

基于 FastAPI 的 BabelDoc PDF 翻译服务

## 功能特性

- ✅ RESTful API 接口
- ✅ 实时流式日志输出（SSE）
- ✅ 同步和异步两种翻译模式
- ✅ 灵活的参数配置
- ✅ 自动创建输出目录
- ✅ 健康检查端点

## 安装依赖

```bash
pip install fastapi uvicorn requests
```

或使用 uv:

```bash
uv pip install fastapi uvicorn requests
```

## 启动服务器

```bash
# 方式 1：直接运行
python babeldoc/babeldoc_server.py

# 方式 2：使用 uvicorn
uvicorn babeldoc.babeldoc_server:app --host 0.0.0.0 --port 8321

# 方式 3：开发模式（自动重载）
uvicorn babeldoc.babeldoc_server:app --reload
```

服务器将在 `http://localhost:8321` 启动

## API 端点

### 1. 健康检查

**GET** `/health`

检查服务器是否正常运行。

```bash
curl http://localhost:8321/health
```

响应：
```json
{
  "status": "healthy",
  "timestamp": "2025-10-25T10:30:00"
}
```

### 2. 流式翻译（推荐）

**POST** `/translate/stream`

使用 Server-Sent Events (SSE) 实时返回翻译日志和进度。

**请求参数：**

```json
{
  "pdf_path": "path/to/input.pdf",
  "output_dir": "babeldoc_output",
  "openai_model": "gpt-4o-mini",
  "openai_base_url": "https://apis.bltcy.ai/v1",
  "openai_api_key": "your-api-key",
  "glossary_files": "all_terms.csv",
  "lang_in": "en-US",
  "lang_out": "zh-CN",
  "qps": 10,
  "max_pages_per_part": 50,
  "no_dual": false,
  "no_mono": false
}
```

**参数说明：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `pdf_path` | string | **必填** | 输入 PDF 文件路径 |
| `output_dir` | string | `"babeldoc_output"` | 输出文件夹路径 |
| `openai_model` | string | `"gpt-4o-mini"` | OpenAI 模型名称 |
| `openai_base_url` | string | `"https://apis.bltcy.ai/v1"` | OpenAI API 基础 URL |
| `openai_api_key` | string | - | OpenAI API Key |
| `glossary_files` | string | `null` | 术语表文件路径（可选） |
| `lang_in` | string | `"en-US"` | 源语言 |
| `lang_out` | string | `"zh-CN"` | 目标语言 |
| `qps` | integer | `10` | 每秒查询数 |
| `max_pages_per_part` | integer | `50` | 每部分最大页数 |
| `no_dual` | boolean | `false` | 不生成双语 PDF |
| `no_mono` | boolean | `false` | 不生成单语 PDF |

**响应格式（SSE）：**

流式响应，每行格式为 `data: {...}\n\n`

事件类型：

1. **info** - 信息消息
```json
{
  "type": "info",
  "message": "开始翻译...",
  "command": "uv run babeldoc ..."
}
```

2. **log** - 翻译日志
```json
{
  "type": "log",
  "message": "INFO: start to translate: input.pdf"
}
```

3. **success** - 翻译成功
```json
{
  "type": "success",
  "message": "翻译完成！",
  "pdf_paths": [
    "/path/to/output.zh.mono.pdf",
    "/path/to/output.zh.dual.pdf"
  ]
}
```

4. **error** - 错误消息
```json
{
  "type": "error",
  "message": "翻译失败，返回码: 1"
}
```

5. **done** - 传输完成
```json
{
  "type": "done"
}
```

**示例：**

```bash
curl -X POST http://localhost:8321/translate/stream \
  -H "Content-Type: application/json" \
  -d '{
    "pdf_path": "babeldoc/2510-20817.pdf",
    "output_dir": "babeldoc_output"
  }'
```

### 3. 同步翻译

**POST** `/translate`

等待翻译完成后一次性返回结果。

**请求参数：** 与流式翻译相同

**响应：**

```json
{
  "success": true,
  "message": "翻译成功完成",
  "pdf_paths": [
    "/path/to/output.zh.mono.pdf",
    "/path/to/output.zh.dual.pdf"
  ],
  "total_time": 121.03,
  "error": null
}
```

**示例：**

```bash
curl -X POST http://localhost:8321/translate \
  -H "Content-Type: application/json" \
  -d '{
    "pdf_path": "babeldoc/2510-20817.pdf",
    "output_dir": "babeldoc_output"
  }'
```

## 使用客户端示例

### Python 客户端

运行提供的示例客户端：

```bash
python babeldoc/babeldoc_client_example.py
```

或在你的代码中使用：

```python
import requests
import json

def translate_pdf(pdf_path, output_dir="babeldoc_output"):
    """流式翻译 PDF"""
    url = "http://localhost:8321/translate/stream"
    
    payload = {
        "pdf_path": pdf_path,
        "output_dir": output_dir
    }
    
    response = requests.post(url, json=payload, stream=True)
    
    for line in response.iter_lines():
        if line and line.startswith(b"data: "):
            data = json.loads(line[6:])
            
            if data["type"] == "log":
                print(data["message"])
            elif data["type"] == "success":
                print("翻译完成！")
                print("生成的文件:", data["pdf_paths"])
                return data["pdf_paths"]
            elif data["type"] == "error":
                print("错误:", data["message"])
                return None

# 使用示例
pdf_paths = translate_pdf("input.pdf")
```

### JavaScript/TypeScript 客户端

```javascript
async function translatePDF(pdfPath, outputDir = "babeldoc_output") {
  const response = await fetch("http://localhost:8321/translate/stream", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      pdf_path: pdfPath,
      output_dir: outputDir,
    }),
  });

  const reader = response.body.getReader();
  const decoder = new TextDecoder();

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    const chunk = decoder.decode(value);
    const lines = chunk.split("\n");

    for (const line of lines) {
      if (line.startsWith("data: ")) {
        const data = JSON.parse(line.slice(6));
        
        if (data.type === "log") {
          console.log(data.message);
        } else if (data.type === "success") {
          console.log("翻译完成！", data.pdf_paths);
          return data.pdf_paths;
        } else if (data.type === "error") {
          console.error("错误:", data.message);
          return null;
        }
      }
    }
  }
}

// 使用示例
translatePDF("input.pdf");
```

## API 文档

启动服务器后，访问以下地址查看自动生成的 API 文档：

- **Swagger UI**: http://localhost:8321/docs
- **ReDoc**: http://localhost:8321/redoc

## 配置说明

服务器会在项目根目录执行 `babeldoc` 命令，因此：

1. 确保 `babeldoc` 已正确安装（可以通过 `uv run babeldoc --help` 测试）
2. PDF 路径可以是相对路径（相对于项目根目录）或绝对路径
3. 输出目录会自动创建（如果不存在）

## 常见问题

### Q: 服务器启动失败

**A:** 检查端口 8321 是否被占用，可以在启动时指定其他端口：

```bash
uvicorn babeldoc.babeldoc_server:app --port 8080
```

### Q: PDF 文件找不到

**A:** 确保提供的路径正确。可以使用绝对路径，或相对于项目根目录的相对路径。

### Q: 翻译很慢或超时

**A:** 
1. 检查网络连接和 OpenAI API 可用性
2. 调整 `qps` 参数（每秒查询数）
3. 对于大文件，考虑调整 `max_pages_per_part` 参数

### Q: 如何查看详细日志

**A:** 使用流式翻译端点 `/translate/stream`，可以实时查看所有日志输出。

## 生产环境部署

### 使用 systemd（Linux）

创建服务文件 `/etc/systemd/system/babeldoc.service`:

```ini
[Unit]
Description=BabelDoc Translation Service
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/chinarxiv
ExecStart=/usr/bin/python3 babeldoc/babeldoc_server.py
Restart=always

[Install]
WantedBy=multi-user.target
```

启动服务：

```bash
sudo systemctl start babeldoc
sudo systemctl enable babeldoc
```

### 使用 Docker

创建 `Dockerfile`:

```dockerfile
FROM python:3.10

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8321

CMD ["python", "babeldoc/babeldoc_server.py"]
```

构建和运行：

```bash
docker build -t babeldoc-server .
docker run -d -p 8321:8321 babeldoc-server
```

### 使用 nginx 反向代理

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:8321;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        
        # SSE 支持
        proxy_buffering off;
        proxy_cache off;
    }
}
```

## 许可证

与 BabelDoc 项目保持一致。

