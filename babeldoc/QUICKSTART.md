# BabelDoc Server 快速开始

## 🚀 快速启动（5 分钟）

### 1. 安装依赖

```bash
pip install -r babeldoc/requirements_server.txt
```

或使用 uv:

```bash
uv pip install -r babeldoc/requirements_server.txt
```

### 2. 启动服务器

**方式一：使用启动脚本**
```bash
bash babeldoc/start_server.sh
```

**方式二：直接运行**
```bash
python babeldoc/babeldoc_server.py
```

**方式三：使用 uvicorn（开发模式）**
```bash
uvicorn babeldoc.babeldoc_server:app --reload
```

服务器启动后，你会看到：
```
INFO:     Started server process [xxxxx]
INFO:     Uvicorn running on http://0.0.0.0:8321
```

### 3. 测试服务器

```bash
python babeldoc/test_server.py
```

如果所有测试通过，说明服务器运行正常！

### 4. 使用服务

有三种方式使用翻译服务：

#### 方式一：Web 界面（推荐，最简单）

1. 在浏览器中打开 `babeldoc/babeldoc_web_client.html`
2. 输入 PDF 路径
3. 点击"开始翻译"
4. 实时查看翻译进度

#### 方式二：Python 客户端

```bash
python babeldoc/babeldoc_client_example.py
```

或在你的代码中：

```python
import requests
import json

# 流式翻译（推荐）
url = "http://localhost:8321/translate/stream"
payload = {
    "pdf_path": "babeldoc/2510-20817.pdf",
    "output_dir": "babeldoc_output"
}

response = requests.post(url, json=payload, stream=True)

for line in response.iter_lines():
    if line and line.startswith(b"data: "):
        data = json.loads(line[6:])
        if data["type"] == "log":
            print(data["message"])
        elif data["type"] == "success":
            print("生成的文件:", data["pdf_paths"])
```

#### 方式三：命令行 curl

```bash
# 流式翻译
curl -X POST http://localhost:8321/translate/stream \
  -H "Content-Type: application/json" \
  -d '{
    "pdf_path": "babeldoc/2510-20817.pdf",
    "output_dir": "babeldoc_output"
  }'

# 同步翻译
curl -X POST http://localhost:8321/translate \
  -H "Content-Type: application/json" \
  -d '{
    "pdf_path": "babeldoc/2510-20817.pdf",
    "output_dir": "babeldoc_output"
  }'
```

## 📚 API 文档

启动服务器后访问：

- **Swagger UI**: http://localhost:8321/docs
- **ReDoc**: http://localhost:8321/redoc

在这里可以交互式地测试所有 API。

## 🎯 常用参数

### 基础参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `pdf_path` | PDF 文件路径（必填） | - |
| `output_dir` | 输出目录 | `babeldoc_output` |

### 翻译参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `openai_model` | OpenAI 模型 | `gpt-4o-mini` |
| `qps` | 每秒查询数 | `10` |
| `glossary_files` | 术语表文件 | `null` |
| `lang_in` | 源语言 | `en-US` |
| `lang_out` | 目标语言 | `zh-CN` |

### 输出控制

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `no_dual` | 不生成双语 PDF | `false` |
| `no_mono` | 不生成单语 PDF | `false` |
| `max_pages_per_part` | 每部分最大页数 | `50` |

## 💡 使用技巧

### 1. 实时查看翻译进度

使用流式 API (`/translate/stream`) 可以实时查看翻译进度和日志。

### 2. 自定义输出位置

```json
{
  "pdf_path": "input.pdf",
  "output_dir": "/absolute/path/to/output"
}
```

### 3. 使用术语表

```json
{
  "pdf_path": "input.pdf",
  "glossary_files": "my_terms.csv"
}
```

### 4. 只生成双语版本

```json
{
  "pdf_path": "input.pdf",
  "no_mono": true
}
```

### 5. 提高翻译速度

```json
{
  "pdf_path": "input.pdf",
  "qps": 20,
  "openai_model": "gpt-3.5-turbo"
}
```

## 🐛 故障排查

### 问题 1: 无法连接到服务器

**解决方案:**
1. 确保服务器已启动
2. 检查端口 8321 是否被占用
3. 尝试访问 http://localhost:8321/health

### 问题 2: PDF 文件找不到

**解决方案:**
1. 使用绝对路径
2. 确保路径相对于项目根目录
3. 检查文件权限

### 问题 3: 翻译失败

**解决方案:**
1. 检查 OpenAI API Key 是否正确
2. 确认网络可以访问 OpenAI API
3. 查看服务器日志中的错误信息
4. 尝试使用较小的 PDF 文件测试

### 问题 4: 翻译很慢

**解决方案:**
1. 增加 `qps` 参数（但不要超过 API 限制）
2. 使用更快的模型（如 `gpt-3.5-turbo`）
3. 检查网络连接质量

## 📖 完整文档

详细文档请查看 `SERVER_README.md`

## 🎉 示例

完整的工作示例：

```python
import requests
import json

def translate_pdf_simple(pdf_path):
    """简单的翻译函数"""
    response = requests.post(
        "http://localhost:8321/translate/stream",
        json={"pdf_path": pdf_path},
        stream=True
    )
    
    for line in response.iter_lines():
        if line and line.startswith(b"data: "):
            data = json.loads(line[6:])
            if data["type"] == "success":
                return data["pdf_paths"]
    return None

# 使用
result = translate_pdf_simple("input.pdf")
print(f"生成的文件: {result}")
```

## ⚡ 性能优化

1. **批量处理**: 如果有多个 PDF，可以并行启动多个翻译任务
2. **资源限制**: 通过 `pool_max_workers` 参数控制并发数
3. **缓存**: BabelDoc 会自动缓存翻译结果

## 🔒 安全提示

1. 不要在公网暴露服务器（除非添加认证）
2. 使用环境变量存储 API Key
3. 定期更新依赖包

## 🤝 获取帮助

- 查看 API 文档: http://localhost:8321/docs
- 运行测试: `python babeldoc/test_server.py`
- 查看完整文档: `SERVER_README.md`

---

**Happy translating! 🎉**

