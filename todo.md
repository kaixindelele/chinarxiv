# Arxiv论文翻译功能抽取 - 任务规划

## 项目目标
从复杂的gpt_academic项目中抽取arxiv翻译功能，实现简单易用的独立接口。

## 核心功能流程
1. 输入arxiv链接/ID → 自动下载tex压缩包
2. 解压并找到主文档文件
3. 智能切分翻译文段
4. 调用LLM进行翻译
5. 整合为新的tex文件
6. 编译生成翻译后的PDF

## 文件结构规划

### ✅ 已完成
- [x] `latex_compile_client.py` - PDF编译客户端
- [x] `latex_compile_server.py` - PDF编译服务器
- [x] `latex_text_splitter.py` - 文本分割工具

### 🚧 待创建文件

#### 1. step1_arxiv_downloader.py
**功能**: arxiv论文下载和解压
**输入**: arxiv URL或ID (如: "1812.10695" 或 "https://arxiv.org/abs/1812.10695")
**输出**: 解压后的源码目录路径
**参考代码**: `crazy_functions/Latex_Function.py` 中的 `arxiv_download()` 函数
**状态**: 待创建

#### 2. step2_latex_parser.py  
**功能**: LaTeX文件解析、主文件定位、多文件合并
**输入**: 源码目录路径
**输出**: 合并后的完整tex内容
**参考代码**: 
- `crazy_functions/latex_fns/latex_toolbox.py` 中的文件合并逻辑
- `crazy_functions/latex_fns/latex_actions.py` 中的 `find_main_tex_file()` 和 `merge_tex_files()`
**状态**: 待创建

#### 3. step3_content_splitter.py
**功能**: 智能内容切分，保留LaTeX结构
**输入**: 完整tex内容
**输出**: 切分后的文本段落列表
**参考代码**: 
- `crazy_functions/latex_fns/latex_actions.py` 中的 `LatexPaperSplit` 类
- `crazy_functions/latex_fns/latex_toolbox.py` 中的分割逻辑
**状态**: 待创建

#### 4. step4_translation_manager.py
**功能**: 翻译管理，LLM调用，术语处理
**输入**: 文本段落列表
**输出**: 翻译后的段落列表  
**参考代码**:
- `crazy_functions/Latex_Function.py` 中的 `switch_prompt()` 函数
- `crazy_functions/crazy_utils.py` 中的多线程LLM调用
- `all_terms.json` 术语词典
**状态**: 待创建

#### 5. step5_result_merger.py
**功能**: 翻译结果合并，生成新tex文件
**输入**: 翻译后的段落列表
**输出**: 完整的翻译后tex内容
**参考代码**: `crazy_functions/latex_fns/latex_actions.py` 中的 `LatexPaperSplit.merge_result()`
**状态**: 待创建

#### 6. step6_pdf_compiler.py
**功能**: PDF编译封装（基于现有client）
**输入**: tex内容
**输出**: PDF文件路径
**参考代码**: `simpletex/latex_compile_client.py`
**状态**: 待创建

#### 7. arxiv_translator.py
**功能**: 主接口文件，整合所有步骤
**输入**: arxiv链接/ID，配置参数
**输出**: 翻译后的PDF文件
**状态**: 待创建

## 依赖关系
