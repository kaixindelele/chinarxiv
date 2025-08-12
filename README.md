# ChinarXiv - Arxiv论文翻译工具

将GPT Academic的arxiv论文翻译功能单独抽取出来，更方便部署和集成arxiv论文翻译服务。

**0812: 抱歉，目前的编译成功率只有30%左右，我尽量尽快修复一下，也欢迎大家一起找bug。**


## 🌟 项目特色

- **完整翻译流程**：从arxiv链接到翻译PDF的一站式服务
- **智能内容切分**：基于LaTeX结构的智能分段，保持文档完整性
- **并发翻译**：支持多线程并发翻译，提高效率
- **缓存机制**：支持翻译缓存，避免重复翻译
- **LaTeX编译**：内置LaTeX编译服务器，支持依赖文件处理
- **术语一致性**：支持自定义术语词典，确保翻译一致性
- **错误恢复**：智能错误处理和恢复机制

## 📋 功能特性

### 核心功能
- ✅ **Arxiv论文下载**：支持多种arxiv输入格式（ID、URL等）
- ✅ **LaTeX解析**：智能解析和合并LaTeX文档结构
- ✅ **内容切分**：基于token限制的智能分段
- ✅ **批量翻译**：支持GPT-4等大语言模型的并发翻译
- ✅ **结果合并**：智能合并翻译结果，保持LaTeX格式
- ✅ **PDF编译**：支持中文字体的PDF编译
- ✅ **缓存系统**：支持下载缓存和翻译缓存

### 高级特性
- 🔧 **自定义配置**：支持API配置、模型选择、并发数等
- 📚 **术语管理**：支持自定义术语词典
- 🎯 **翻译要求**：支持自定义翻译风格和要求
- 📊 **进度跟踪**：实时翻译进度反馈
- 🛠️ **错误处理**：详细的错误信息和恢复建议

## 🚀 快速开始

最简单的部署：
```
1. cd latex2pdf
2. docker compose -f docker-compose-latex-server.yml up --build -d
3. 编辑 config.py 文件，填入你的API配置；
4. python arxiv_translator.py
```

### 环境要求

- Python 3.8+
- LaTeX环境（推荐TeX Live）
- OpenAI API密钥或兼容的LLM API

### 安装依赖

```bash
pip install -r requirements.txt
```

主要依赖包括：
- `requests` - HTTP请求
- `openai` - OpenAI API客户端
- `tiktoken` - Token计算
- `fastapi` - LaTeX编译服务器
- `uvicorn` - ASGI服务器

### 配置设置

1. 复制配置模板：
```bash
cp config_temp-需要修改成config-填入自己的API.py config.py
```

2. 编辑 [`config.py`](config.py) 文件，填入你的API配置：
```python
# OpenAI API配置
API_KEY = "your-api-key-here"
BASE_URL = "https://api.openai.com/v1"  # 或其他兼容的API地址
LLM_MODEL = "gpt-4o-mini"  # 或其他支持的模型
```

### 基本使用

#### 方式1：使用主接口（推荐）

```python
from arxiv_translator import translate_arxiv_paper

# 翻译arxiv论文
success, result = translate_arxiv_paper(
    arxiv_input="1812.10695",  # arxiv ID或URL
    user_requirements="保持学术性和专业性，确保术语翻译的一致性",
    compile_pdf=True  # 是否编译PDF
)

if success:
    print(f"翻译成功！文件保存在: {result}")
else:
    print(f"翻译失败: {result}")
```

#### 方式2：使用完整API

```python
from arxiv_translator import ArxivTranslator

# 创建翻译器
translator = ArxivTranslator(
    output_dir="./output",
    max_workers=9,  # 并发线程数
    max_token_limit=800  # 每段最大token数
)

# 自定义术语词典
user_terms = {
    "transformer": "变换器",
    "attention": "注意力机制",
    "neural network": "神经网络"
}

# 执行翻译
success, result, details = translator.translate_arxiv(
    arxiv_input="https://arxiv.org/abs/1812.10695",
    user_requirements="翻译要保持学术性，专业术语首次出现时标注英文原词",
    user_terms=user_terms,
    compile_pdf=True
)
```

#### 方式3：命令行使用

```bash
python arxiv_translator.py
```

然后按提示输入arxiv ID或选择测试用例。

## 📁 项目结构

```
chinarxiv/
├── README.md                    # 项目说明文档
├── config.py                    # 配置文件（需要创建）
├── config_temp-需要修改成config-填入自己的API.py  # 配置模板
├── arxiv_translator.py          # 主翻译接口
├── step1_arxiv_downloader.py    # Arxiv论文下载器
├── step2_latex_parser.py        # LaTeX文档解析器
├── step3_content_splitter.py    # 内容智能切分器
├── step4_gpt_model.py          # GPT模型接口
├── step5_result_merger.py       # 翻译结果合并器
├── step6_translation_manager.py # 翻译管理器
├── step7_trans_cache.py        # 翻译缓存管理
├── step8_pdf_compiler.py       # PDF编译器
├── all_terms.json              # 术语词典
├── todo.md                     # 开发计划
└── latex2pdf/                  # LaTeX编译服务
    ├── README-latex-server.md   # LaTeX服务器说明
    ├── latex_compile_server.py  # LaTeX编译服务器
    ├── latex_compile_client.py  # LaTeX编译客户端
    ├── docker-compose-latex-server.yml  # Docker配置
    ├── Dockerfile-latex-compile-server   # Docker镜像
    └── requirements-latex-server.txt     # 服务器依赖
```

## 🔧 详细配置

### API配置选项

在 [`config.py`](config.py) 中可以配置：

```python
# LLM API配置
API_KEY = "your-api-key"           # API密钥
BASE_URL = "https://api.openai.com/v1"  # API地址
LLM_MODEL = "gpt-4o-mini"          # 模型名称

# 翻译配置
MAX_WORKERS = 9                    # 最大并发数
MAX_TOKEN_LIMIT = 800             # 每段最大token数
TEMPERATURE = 0.3                  # 翻译温度参数

# 缓存配置
USE_CACHE = True                   # 是否使用缓存
CACHE_DIR = "./arxiv_cache"        # 缓存目录

# LaTeX编译配置
LATEX_SERVER_URL = "http://localhost:9851"  # LaTeX服务器地址
```

### 自定义翻译要求

```python
user_requirements = """
翻译要求：
1. 保持学术性和专业性
2. 确保术语翻译的一致性
3. 专业术语首次出现时用括号标注英文原词
4. 保持数学公式和引用格式不变
5. 翻译要流畅自然，符合中文表达习惯
"""
```

### 术语词典管理

```python
user_terms = {
    # 机器学习相关
    "machine learning": "机器学习",
    "deep learning": "深度学习",
    "neural network": "神经网络",
    "transformer": "变换器",
    "attention": "注意力机制",
    
    # 数学相关
    "gradient": "梯度",
    "optimization": "优化",
    "convergence": "收敛",
    
    # 领域特定术语
    "reinforcement learning": "强化学习",
    "natural language processing": "自然语言处理"
}
```

## 🐳 Docker部署

### LaTeX编译服务器

项目包含独立的LaTeX编译服务器，支持Docker部署：

```bash
cd latex2pdf
docker-compose -f docker-compose-latex-server.yml up -d
```

详细说明请参考：[`latex2pdf/README-latex-server.md`](latex2pdf/README-latex-server.md)

## 📊 使用示例

### 示例1：翻译经典论文

```python
from arxiv_translator import translate_arxiv_paper

# 翻译GPT-1论文
success, result = translate_arxiv_paper(
    arxiv_input="1812.10695",
    user_requirements="保持学术严谨性，术语翻译要准确",
    compile_pdf=True
)

print(f"翻译结果: {result}")
```

### 示例2：批量翻译

```python
from arxiv_translator import ArxivTranslator

translator = ArxivTranslator(max_workers=6)

papers = ["1812.10695", "2402.14207", "1706.03762"]

for paper_id in papers:
    print(f"正在翻译: {paper_id}")
    success, result, details = translator.translate_arxiv(paper_id)
    if success:
        print(f"✅ {paper_id} 翻译完成: {result}")
    else:
        print(f"❌ {paper_id} 翻译失败: {result}")
```

### 示例3：进度监控

```python
def progress_callback(step, progress, message):
    print(f"Step {step} - {progress:.1f}%: {message}")

translator = ArxivTranslator()
success, result, details = translator.translate_arxiv(
    arxiv_input="1812.10695",
    progress_callback=progress_callback
)
```

## 🔍 故障排除

### 常见问题

1. **API配置错误**
   - 检查 [`config.py`](config.py) 中的API_KEY和BASE_URL是否正确
   - 确认API密钥有足够的额度

2. **LaTeX编译失败**
   - 确保安装了完整的LaTeX环境（推荐TeX Live）
   - 检查LaTeX编译服务器是否正常运行
   - 查看编译日志获取详细错误信息

3. **下载失败**
   - 检查网络连接
   - 如需要，配置代理设置
   - 确认arxiv ID格式正确

4. **翻译质量问题**
   - 调整MAX_TOKEN_LIMIT参数，减小分段大小
   - 使用更强的模型（如gpt-4）
   - 完善术语词典和翻译要求

### 调试模式

启用详细日志：

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# 然后运行翻译
translator = ArxivTranslator()
```

## 🤝 贡献指南

欢迎提交Issue和Pull Request！

### 开发环境设置

1. Fork项目
2. 创建开发分支
3. 安装开发依赖：`pip install -r requirements.txt`
4. 运行测试：`python arxiv_translator.py`

### 提交规范

- 遵循PEP 8代码规范
- 添加必要的注释和文档
- 确保测试通过

## 📄 许可证

本项目基于GPT Academic项目改进，遵循相应的开源许可证。

## 🙏 致谢

- 感谢 [GPT Academic](https://github.com/binary-husky/gpt_academic) 项目提供的基础代码

## 📞 联系方式

如有问题或建议，请通过以下方式联系：

- 提交Issue：[GitHub Issues](https://github.com/kaixindelele/chinarxiv/issues)
- QQ群：816116844
---

**注意**：使用本工具翻译论文时，请遵守相关的版权和学术规范，确保翻译结果仅用于学习和研究目的。
