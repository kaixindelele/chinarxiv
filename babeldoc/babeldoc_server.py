"""
BabelDoc FastAPI 服务器
提供 PDF 翻译服务的 Web API
"""

import asyncio
import json
import os
import re
from pathlib import Path
from typing import Optional, List
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import uvicorn


app = FastAPI(
    title="BabelDoc Translation Service",
    description="PDF 翻译服务 API",
    version="1.0.0"
)


class TranslationRequest(BaseModel):
    """翻译请求模型"""
    pdf_path: str = Field(..., description="输入 PDF 文件路径")
    output_dir: str = Field(default="babeldoc_output", description="输出文件夹路径")
    config_file: Optional[str] = Field(
        default="babeldoc/babeldoc_config.toml",
        description="配置文件路径（可选，使用 babeldoc 的 --config 参数）"
    )
    openai_model: Optional[str] = Field(default=None, description="OpenAI 模型名称")
    openai_base_url: Optional[str] = Field(default=None, description="OpenAI API 基础 URL")
    openai_api_key: Optional[str] = Field(default=None, description="OpenAI API Key")
    glossary_files: Optional[str] = Field(
        default=None, 
        description="术语表文件路径（可选）"
    )
    lang_in: Optional[str] = Field(default=None, description="源语言")
    lang_out: Optional[str] = Field(default=None, description="目标语言")
    qps: Optional[int] = Field(default=None, description="每秒查询数")
    max_pages_per_part: Optional[int] = Field(default=None, description="每部分最大页数")
    no_dual: Optional[bool] = Field(default=None, description="不生成双语 PDF")
    no_mono: Optional[bool] = Field(default=None, description="不生成单语 PDF")


class TranslationResponse(BaseModel):
    """翻译响应模型"""
    success: bool
    message: str
    pdf_paths: List[str] = []
    total_time: Optional[float] = None
    error: Optional[str] = None


async def stream_process_output(process: asyncio.subprocess.Process):
    """
    异步流式读取进程输出
    
    Args:
        process: 异步进程对象
        
    Yields:
        dict: 包含日志信息的字典
    """
    async def read_stream(stream, queue):
        """读取单个流（stdout 或 stderr）并放入队列"""
        try:
            while True:
                line = await stream.readline()
                if not line:
                    break
                
                try:
                    decoded_line = line.decode('utf-8', errors='replace').strip()
                    if decoded_line:
                        await queue.put({"type": "log", "message": decoded_line})
                except Exception as e:
                    await queue.put({"type": "log", "message": f"Error decoding line: {str(e)}"})
        except Exception as e:
            await queue.put({"type": "log", "message": f"Stream error: {str(e)}"})
        finally:
            await queue.put(None)  # 标记流结束
    
    # 创建队列用于合并输出
    queue = asyncio.Queue()
    
    # 启动两个读取任务
    tasks = []
    if process.stdout:
        tasks.append(asyncio.create_task(read_stream(process.stdout, queue)))
    if process.stderr:
        tasks.append(asyncio.create_task(read_stream(process.stderr, queue)))
    
    # 从队列中读取并yield
    streams_done = 0
    total_streams = len(tasks)
    
    try:
        while streams_done < total_streams:
            item = await queue.get()
            if item is None:
                streams_done += 1
            else:
                yield item
    except Exception as e:
        yield {"type": "log", "message": f"Error reading from queue: {str(e)}"}
    
    # 等待所有任务完成
    await asyncio.gather(*tasks, return_exceptions=True)
    
    # 等待进程完成
    await process.wait()
    
    # 返回进程返回码
    yield {
        "type": "result",
        "return_code": process.returncode
    }


async def find_generated_pdfs(original_pdf_path: str, output_dir: str) -> List[str]:
    """
    查找生成的 PDF 文件
    
    Args:
        original_pdf_path: 原始 PDF 路径
        output_dir: 输出目录
        
    Returns:
        生成的 PDF 文件路径列表（绝对路径）
    """
    try:
        # 获取原始文件名（不含扩展名）
        original_name = Path(original_pdf_path).stem
        
        # 确定输出目录的绝对路径
        project_root = Path(__file__).parent.parent
        output_path = Path(output_dir)
        if not output_path.is_absolute():
            output_path = project_root / output_dir
        
        # 确保输出目录存在
        if not output_path.exists():
            return []
        
        # 使用集合去重
        pdf_paths = set()
        
        # 查找所有匹配的 PDF 文件
        # babeldoc 生成的文件名格式：{basename}.{lang_code}.mono.pdf 或 {basename}.{lang_code}.dual.pdf
        patterns = [
            f"{original_name}*.mono.pdf",
            f"{original_name}*.dual.pdf",
        ]
        
        for pattern in patterns:
            for pdf_file in output_path.glob(pattern):
                if pdf_file.is_file():
                    pdf_paths.add(str(pdf_file.absolute()))
        
        return sorted(list(pdf_paths))
    except Exception as e:
        # 记录错误但不抛出
        return []


async def run_babeldoc(request: TranslationRequest):
    """
    运行 babeldoc 命令
    
    Args:
        request: 翻译请求参数
        
    Yields:
        str: SSE 格式的日志和结果
    """
    # 检查输入文件是否存在（相对于项目根目录）
    project_root = Path(__file__).parent.parent
    pdf_path = Path(request.pdf_path)
    if not pdf_path.is_absolute():
        pdf_path = project_root / pdf_path
    
    if not pdf_path.exists():
        yield f"data: {json.dumps({'type': 'error', 'message': f'PDF 文件不存在: {request.pdf_path} (检查路径: {pdf_path})'})}\n\n"
        return
    
    # 创建输出目录
    output_dir = Path(request.output_dir)
    if not output_dir.is_absolute():
        output_dir = project_root / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 构建命令
    cmd = [
        "uv", "run", "babeldoc",
        "--files", request.pdf_path,
        "--output", request.output_dir,
    ]
    
    # 添加配置文件参数（如果指定）
    if request.config_file:
        config_path = Path(request.config_file)
        if not config_path.is_absolute():
            config_path = project_root / config_path
        
        if config_path.exists():
            cmd.extend(["--config", str(config_path)])
        else:
            yield f"data: {json.dumps({'type': 'log', 'message': f'[警告] 配置文件不存在: {config_path}，将使用参数或默认值'})}\n\n"
    
    # 添加可选参数（这些参数会覆盖配置文件中的设置）
    if request.openai_model:
        cmd.extend(["--openai", "--openai-model", request.openai_model])
    
    if request.openai_base_url:
        cmd.extend(["--openai-base-url", request.openai_base_url])
    
    if request.openai_api_key:
        cmd.extend(["--openai-api-key", request.openai_api_key])
    
    if request.lang_in:
        cmd.extend(["--lang-in", request.lang_in])
    
    if request.lang_out:
        cmd.extend(["--lang-out", request.lang_out])
    
    if request.qps:
        cmd.extend(["--qps", str(request.qps)])
    
    if request.max_pages_per_part:
        cmd.extend(["--max-pages-per-part", str(request.max_pages_per_part)])
    
    if request.glossary_files:
        cmd.extend(["--glossary-files", request.glossary_files])
    
    if request.no_dual:
        cmd.append("--no-dual")
    
    if request.no_mono:
        cmd.append("--no-mono")
    
    # 发送开始信息
    yield f"data: {json.dumps({'type': 'info', 'message': '开始翻译...', 'command': ' '.join(cmd)})}\n\n"
    
    try:
        # 创建异步进程
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(Path(__file__).parent.parent)  # 在项目根目录执行
        )
        
        # 流式输出日志
        async for output in stream_process_output(process):
            if output.get("type") == "result":
                # 这是最终结果
                return_code = output.get("return_code", -1)
                
                # 翻译完成后，扫描输出目录获取生成的 PDF 文件
                pdf_paths = []
                if return_code == 0:
                    yield f"data: {json.dumps({'type': 'log', 'message': '正在扫描输出目录查找生成的 PDF...'})}\n\n"
                    pdf_paths = await find_generated_pdfs(request.pdf_path, request.output_dir)
                    if pdf_paths:
                        yield f"data: {json.dumps({'type': 'log', 'message': f'找到 {len(pdf_paths)} 个生成的 PDF 文件'})}\n\n"
                    else:
                        yield f"data: {json.dumps({'type': 'log', 'message': '警告：未找到生成的 PDF 文件'})}\n\n"
                
                if return_code == 0:
                    yield f"data: {json.dumps({'type': 'success', 'message': '翻译完成！', 'pdf_paths': pdf_paths})}\n\n"
                else:
                    yield f"data: {json.dumps({'type': 'error', 'message': f'翻译失败，返回码: {return_code}'})}\n\n"
            elif output.get("type") == "log":
                # 普通日志输出
                yield f"data: {json.dumps({'type': 'log', 'message': output.get('message', '')})}\n\n"
        
        yield "data: {\"type\": \"done\"}\n\n"
        
    except Exception as e:
        error_msg = f"执行过程中出错: {str(e)}"
        yield f"data: {json.dumps({'type': 'error', 'message': error_msg})}\n\n"


@app.get("/")
async def root():
    """根路径"""
    return {
        "service": "BabelDoc Translation Service",
        "version": "1.0.0",
        "status": "running",
        "timestamp": datetime.now().isoformat()
    }


@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.post("/translate/stream")
async def translate_stream(request: TranslationRequest):
    """
    流式翻译端点
    
    使用 Server-Sent Events (SSE) 实时返回日志
    
    Args:
        request: 翻译请求参数
        
    Returns:
        StreamingResponse: SSE 流式响应
    """
    return StreamingResponse(
        run_babeldoc(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # 禁用 nginx 缓冲
        }
    )


@app.post("/translate", response_model=TranslationResponse)
async def translate(request: TranslationRequest):
    """
    同步翻译端点（等待完成后返回）
    
    Args:
        request: 翻译请求参数
        
    Returns:
        TranslationResponse: 翻译结果
    """
    # 检查输入文件是否存在（相对于项目根目录）
    project_root = Path(__file__).parent.parent
    pdf_path = Path(request.pdf_path)
    if not pdf_path.is_absolute():
        pdf_path = project_root / pdf_path
    
    if not pdf_path.exists():
        raise HTTPException(
            status_code=400,
            detail=f"PDF 文件不存在: {request.pdf_path} (检查路径: {pdf_path})"
        )
    
    # 创建输出目录
    output_dir = Path(request.output_dir)
    if not output_dir.is_absolute():
        output_dir = project_root / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 构建命令
    cmd = [
        "uv", "run", "babeldoc",
        "--files", request.pdf_path,
        "--output", request.output_dir,
    ]
    
    # 添加配置文件参数（如果指定）
    if request.config_file:
        config_path = Path(request.config_file)
        if not config_path.is_absolute():
            config_path = project_root / config_path
        
        if config_path.exists():
            cmd.extend(["--config", str(config_path)])
    
    # 添加可选参数（这些参数会覆盖配置文件中的设置）
    if request.openai_model:
        cmd.extend(["--openai", "--openai-model", request.openai_model])
    
    if request.openai_base_url:
        cmd.extend(["--openai-base-url", request.openai_base_url])
    
    if request.openai_api_key:
        cmd.extend(["--openai-api-key", request.openai_api_key])
    
    if request.lang_in:
        cmd.extend(["--lang-in", request.lang_in])
    
    if request.lang_out:
        cmd.extend(["--lang-out", request.lang_out])
    
    if request.qps:
        cmd.extend(["--qps", str(request.qps)])
    
    if request.max_pages_per_part:
        cmd.extend(["--max-pages-per-part", str(request.max_pages_per_part)])
    
    if request.glossary_files:
        cmd.extend(["--glossary-files", request.glossary_files])
    
    if request.no_dual:
        cmd.append("--no-dual")
    
    if request.no_mono:
        cmd.append("--no-mono")
    
    try:
        # 执行命令
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(Path(__file__).parent.parent)
        )
        
        stdout, stderr = await process.communicate()
        
        # 直接扫描输出目录获取生成的 PDF 文件
        pdf_paths = []
        output_text = stderr.decode('utf-8', errors='replace')
        
        if process.returncode == 0:
            pdf_paths = await find_generated_pdfs(request.pdf_path, request.output_dir)
        
        # 提取总时间
        time_match = re.search(r'Total time:\s+([\d.]+)\s+seconds', output_text)
        total_time = float(time_match.group(1)) if time_match else None
        
        if process.returncode == 0:
            return TranslationResponse(
                success=True,
                message="翻译成功完成",
                pdf_paths=pdf_paths,
                total_time=total_time
            )
        else:
            return TranslationResponse(
                success=False,
                message="翻译失败",
                error=output_text,
                pdf_paths=[]
            )
            
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"翻译过程中出错: {str(e)}"
        )


if __name__ == "__main__":
    # 运行服务器
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8321,
        log_level="info"
    )

