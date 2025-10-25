#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LaTeX编译服务器 - 支持依赖文件处理（修复编码问题）

主要功能：
1. 提供HTTP API接口用于LaTeX编译
2. 支持同步和异步编译模式
3. 支持依赖文件接收和处理（修复二进制文件编码问题）
4. 提供任务状态查询和健康检查
5. 自动清理临时文件和过期任务

输入：LaTeX文档内容和依赖文件
输出：编译后的PDF文件或错误信息

作者：基于GPT Academic项目改进
"""

import os
import shutil
import tempfile
import subprocess
import threading
import time
import base64
import uuid
import logging
from pathlib import Path
from typing import Dict, Optional, Any, List
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

# FastAPI相关导入
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 请求模型
class CompileRequest(BaseModel):
    """
    编译请求模型
    
    包含LaTeX文档内容、输出名称和依赖文件
    """
    tex_content: str                           # LaTeX文档内容
    output_name: str = "output"               # 输出文件名
    dependencies: Optional[Dict[str, str]] = None  # 依赖文件（base64编码）

class CompileResponse(BaseModel):
    """
    编译响应模型
    
    包含编译结果、PDF内容和日志信息
    """
    success: bool                             # 是否成功
    pdf_content: Optional[str] = None        # PDF内容（base64编码）
    log: str = ""                           # 编译日志
    error: Optional[str] = None             # 错误信息

class AsyncCompileResponse(BaseModel):
    """
    异步编译响应模型
    
    包含任务ID和提交状态
    """
    success: bool                            # 是否成功提交
    task_id: Optional[str] = None           # 任务ID
    error: Optional[str] = None             # 错误信息

class TaskStatus(BaseModel):
    """
    任务状态模型
    
    包含任务状态、进度和结果
    """
    task_id: str                            # 任务ID
    status: str                             # 状态：pending/running/completed/failed
    progress: float = 0.0                   # 进度百分比
    result: Optional[CompileResponse] = None # 编译结果
    created_at: datetime                    # 创建时间
    updated_at: datetime                    # 更新时间

# 全局变量
app = FastAPI(title="LaTeX编译服务器", version="1.0.0")
task_storage: Dict[str, TaskStatus] = {}    # 任务存储
executor = ThreadPoolExecutor(max_workers=4)  # 线程池
active_tasks = 0                            # 活跃任务计数

class LaTeXCompiler:
    """
    LaTeX编译器类
    
    主要功能：
    1. 管理临时工作目录
    2. 处理依赖文件（修复编码问题）
    3. 执行LaTeX编译
    4. 清理临时文件
    """
    
    def __init__(self, work_dir: str = None):
        """
        初始化LaTeX编译器
        
        输入：
        - work_dir: 工作目录路径（可选），如 "/tmp/latex_work"
        
        输出：无
        
        这个函数初始化编译器，设置工作目录和编译环境
        """
        self.work_dir = Path(work_dir) if work_dir else Path(tempfile.mkdtemp(prefix="latex_"))
        self.work_dir.mkdir(exist_ok=True, parents=True)
        
        # 编译配置
        self.latex_cmd = "pdflatex"
        self.latex_args = [
            "-interaction=nonstopmode",
            "-file-line-error",
            "-synctex=1"
        ]
        
        logger.info(f"LaTeX编译器初始化完成，工作目录: {self.work_dir}")
    
    def _decode_dependencies(self, dependencies: Dict[str, str]) -> Dict[str, bytes]:
        """
        解码base64编码的依赖文件
        
        输入：
        - dependencies: base64编码的依赖文件字典，如 {"file.cls": "base64字符串"}
        
        输出：
        - decoded_deps: 解码后的依赖文件字典，如 {"file.cls": b"文件内容"}
        
        这个函数将base64编码的文件内容解码为二进制数据
        """
        try:
            decoded_deps = {}
            for filename, base64_content in dependencies.items():
                try:
                    decoded_content = base64.b64decode(base64_content)
                    decoded_deps[filename] = decoded_content
                    logger.debug(f"成功解码依赖文件: {filename} ({len(decoded_content)} 字节)")
                except Exception as e:
                    logger.error(f"解码依赖文件 {filename} 失败: {e}")
                    continue
            
            logger.info(f"成功解码 {len(decoded_deps)} 个依赖文件")
            return decoded_deps
            
        except Exception as e:
            logger.error(f"解码依赖文件时出错: {e}")
            return {}
    
    def _write_dependencies(self, dependencies: Dict[str, bytes]) -> List[str]:
        """
        将依赖文件写入工作目录
        
        输入：
        - dependencies: 依赖文件字典，如 {"file.cls": b"文件内容"}
        
        输出：
        - written_files: 成功写入的文件路径列表，如 ["/tmp/latex_work/file.cls"]
        
        这个函数将依赖文件写入到编译工作目录中
        """
        written_files = []
        
        try:
            for filename, content in dependencies.items():
                # 处理可能的子目录路径
                file_path = self.work_dir / filename
                file_path.parent.mkdir(parents=True, exist_ok=True)
                
                # 写入文件
                try:
                    with open(file_path, 'wb') as f:
                        f.write(content)
                    written_files.append(str(file_path))
                    logger.info(f"成功写入依赖文件: {filename} -> {file_path}")
                except Exception as e:
                    logger.error(f"写入依赖文件 {filename} 失败: {e}")
                    continue
            
            logger.info(f"成功写入 {len(written_files)} 个依赖文件")
            return written_files
            
        except Exception as e:
            logger.error(f"写入依赖文件时出错: {e}")
            return written_files
    
    def _safe_write_tex_file(self, tex_content: str, tex_file_path: Path) -> bool:
        """
        安全写入LaTeX文件（处理编码问题）
        
        输入：
        - tex_content: LaTeX文档内容
        - tex_file_path: tex文件路径
        
        输出：
        - success: 是否写入成功
        
        这个函数安全地写入LaTeX文件，处理各种编码问题
        """
        try:
            # 首先尝试UTF-8编码写入
            with open(tex_file_path, 'w', encoding='utf-8') as f:
                f.write(tex_content)
            logger.info(f"成功以UTF-8编码写入tex文件: {tex_file_path}")
            return True
            
        except UnicodeEncodeError as e:
            logger.warning(f"UTF-8编码失败，尝试其他编码方式: {e}")
            
            try:
                # 尝试latin-1编码（兼容性更好）
                with open(tex_file_path, 'w', encoding='latin-1') as f:
                    f.write(tex_content)
                logger.info(f"成功以latin-1编码写入tex文件: {tex_file_path}")
                return True
                
            except Exception as e2:
                logger.error(f"latin-1编码也失败: {e2}")
                
                try:
                    # 最后尝试二进制写入
                    with open(tex_file_path, 'wb') as f:
                        f.write(tex_content.encode('utf-8', errors='replace'))
                    logger.info(f"成功以二进制方式写入tex文件: {tex_file_path}")
                    return True
                    
                except Exception as e3:
                    logger.error(f"二进制写入也失败: {e3}")
                    return False
        
        except Exception as e:
            logger.error(f"写入tex文件时出现未知错误: {e}")
            return False
    
    def compile_latex(self, tex_content: str, output_name: str, 
                 dependencies: Dict[str, str] = None) -> CompileResponse:
        """
        编译LaTeX文档（完整编译流程，支持参考文献）
        
        输入：
        - tex_content: LaTeX文档内容，如 "\\documentclass{article}..."
        - output_name: 输出文件名，如 "my_document"
        - dependencies: 依赖文件字典（base64编码），如 {"file.bib": "base64字符串"}
        
        输出：
        - result: 编译结果对象，包含成功状态、PDF内容和日志
        
        这个函数执行完整的LaTeX编译流程：pdflatex → bibtex → pdflatex → pdflatex
        """
        compile_log = []
        
        try:
            logger.info(f"开始完整LaTeX编译流程: {output_name}")
            compile_log.append(f"开始编译: {datetime.now()}")
            
            # 生成唯一的tex文件名
            tex_filename = f"{output_name}.tex"
            tex_file_path = self.work_dir / tex_filename
            
            # 安全写入LaTeX文件
            compile_log.append(f"写入LaTeX文件: {tex_file_path}")
            if not self._safe_write_tex_file(tex_content, tex_file_path):
                error_msg = "写入LaTeX文件失败"
                compile_log.append(error_msg)
                return CompileResponse(
                    success=False,
                    error=error_msg,
                    log="\n".join(compile_log)
                )
            
            # 处理依赖文件（特别关注.bib文件）
            bib_files = []
            if dependencies:
                compile_log.append(f"处理 {len(dependencies)} 个依赖文件")
                decoded_deps = self._decode_dependencies(dependencies)
                written_files = self._write_dependencies(decoded_deps)
                compile_log.append(f"成功写入 {len(written_files)} 个依赖文件")
                
                # 记录.bib文件
                for filename in dependencies.keys():
                    if filename.endswith('.bib'):
                        bib_files.append(filename)
                        compile_log.append(f"发现参考文献文件: {filename}")
                    compile_log.append(f"依赖文件: {filename}")
            
            # 执行完整的LaTeX编译流程
            pdf_file_path = self.work_dir / f"{output_name}.pdf"
            aux_file_path = self.work_dir / f"{output_name}.aux"
            bbl_file_path = self.work_dir / f"{output_name}.bbl"
            
            # 第一次pdflatex编译 - 生成.aux文件
            compile_log.append("第1步: 执行第一次pdflatex编译（生成.aux文件）")
            success = self._run_latex_command("pdflatex", tex_filename, compile_log, 1)
            if not success:
                return CompileResponse(
                    success=False,
                    error="第一次pdflatex编译失败",
                    log="\n".join(compile_log)
                )
            
            # 检查是否需要bibtex编译
            need_bibtex = False
            if aux_file_path.exists():
                try:
                    with open(aux_file_path, 'r', encoding='utf-8', errors='replace') as f:
                        aux_content = f.read()
                    # 检查.aux文件中是否有\bibdata或\citation命令
                    if '\\bibdata' in aux_content or '\\citation' in aux_content:
                        need_bibtex = True
                        compile_log.append("检测到参考文献引用，需要运行bibtex")
                except Exception as e:
                    compile_log.append(f"读取.aux文件时出错: {e}")
            
            # 如果需要，执行bibtex编译
            if need_bibtex or bib_files:
                compile_log.append("第2步: 执行bibtex编译（处理参考文献）")
                success = self._run_bibtex_command(output_name, compile_log)
                if not success:
                    compile_log.append("bibtex编译失败，但继续后续编译")
                elif bbl_file_path.exists():
                    compile_log.append("bibtex编译成功，生成.bbl文件")
                
                # 第二次pdflatex编译 - 处理参考文献
                compile_log.append("第3步: 执行第二次pdflatex编译（处理参考文献）")
                success = self._run_latex_command("pdflatex", tex_filename, compile_log, 2)
                if not success:
                    compile_log.append("第二次pdflatex编译失败，但继续最后编译")
                
                # 第三次pdflatex编译 - 处理交叉引用
                compile_log.append("第4步: 执行第三次pdflatex编译（处理交叉引用）")
                success = self._run_latex_command("pdflatex", tex_filename, compile_log, 3)
            else:
                compile_log.append("未检测到参考文献，跳过bibtex编译")
                # 第二次pdflatex编译 - 处理交叉引用
                compile_log.append("第2步: 执行第二次pdflatex编译（处理交叉引用）")
                success = self._run_latex_command("pdflatex", tex_filename, compile_log, 2)
            
            # 检查最终是否生成了PDF - 关键修改：只要PDF文件存在就认为成功
            if not pdf_file_path.exists():
                error_msg = "PDF文件生成失败"
                compile_log.append(error_msg)
                
                # 尝试查找.log文件获取详细错误信息
                log_file_path = self.work_dir / f"{output_name}.log"
                if log_file_path.exists():
                    try:
                        with open(log_file_path, 'r', encoding='utf-8', errors='replace') as f:
                            latex_log = f.read()
                        compile_log.append("LaTeX详细日志:")
                        compile_log.append(latex_log)
                    except Exception as e:
                        compile_log.append(f"读取LaTeX日志失败: {e}")
                
                return CompileResponse(
                    success=False,
                    error=error_msg,
                    log="\n".join(compile_log)
                )
            else:
                # PDF文件存在，即使有编译警告也认为成功
                compile_log.append(f"PDF文件已生成: {pdf_file_path}")
            
            # 读取生成的PDF文件
            compile_log.append(f"读取PDF文件: {pdf_file_path}")
            with open(pdf_file_path, 'rb') as f:
                pdf_content = f.read()
            
            # 编码为base64
            pdf_base64 = base64.b64encode(pdf_content).decode('utf-8')
            
            compile_log.append(f"完整编译流程成功完成，PDF大小: {len(pdf_content)} 字节")
            if bib_files:
                compile_log.append(f"已处理 {len(bib_files)} 个参考文献文件")
            
            logger.info(f"LaTeX完整编译成功: {output_name}, PDF大小: {len(pdf_content)} 字节")
            
            return CompileResponse(
                success=True,
                pdf_content=pdf_base64,
                log="\n".join(compile_log)
            )
            
        except Exception as e:
            error_msg = f"编译过程异常: {e}"
            compile_log.append(error_msg)
            logger.error(error_msg)
            
            return CompileResponse(
                success=False,
                error=error_msg,
                log="\n".join(compile_log)
            )
        
        finally:
            # 清理工作目录
            try:
                shutil.rmtree(self.work_dir)
                logger.debug(f"清理工作目录: {self.work_dir}")
            except Exception as e:
                logger.warning(f"清理工作目录失败: {e}")

    def _run_latex_command(self, command: str, tex_filename: str, compile_log: list, round_num: int) -> bool:
        """
        执行LaTeX编译命令
        
        输入：
        - command: 编译命令，如 "pdflatex"
        - tex_filename: tex文件名，如 "document.tex"
        - compile_log: 编译日志列表
        - round_num: 编译轮次，如 1
        
        输出：
        - success: 是否编译成功（布尔值）
        
        这个函数执行单次LaTeX编译命令并记录日志
        """
        try:
            cmd = [command] + self.latex_args + [tex_filename]
            
            result = subprocess.run(
                cmd,
                cwd=self.work_dir,
                capture_output=True,
                text=True,
                timeout=120,
                encoding='utf-8',
                errors='replace'
            )
            
            # 记录编译输出
            if result.stdout:
                compile_log.append(f"{command}编译输出 (第{round_num}次):")
                compile_log.append(result.stdout)
            
            if result.stderr:
                compile_log.append(f"{command}编译错误 (第{round_num}次):")
                compile_log.append(result.stderr)
            
            # 修改逻辑：检查是否生成了PDF文件，而不仅仅依赖返回码
            output_name = tex_filename.replace('.tex', '')
            pdf_file_path = self.work_dir / f"{output_name}.pdf"
            
            if result.returncode == 0:
                compile_log.append(f"第{round_num}次{command}编译成功")
                return True
            elif pdf_file_path.exists():
                # 即使返回码不为0，但如果PDF文件存在，也认为编译成功（可能只是警告）
                compile_log.append(f"第{round_num}次{command}编译有警告但生成了PDF，返回码: {result.returncode}")
                return True
            else:
                compile_log.append(f"第{round_num}次{command}编译失败，返回码: {result.returncode}")
                return False
                
        except subprocess.TimeoutExpired:
            compile_log.append(f"第{round_num}次{command}编译超时")
            return False
        except Exception as e:
            compile_log.append(f"第{round_num}次{command}编译异常: {e}")
            return False

    def _run_bibtex_command(self, output_name: str, compile_log: list) -> bool:
        """
        执行bibtex编译命令
        
        输入：
        - output_name: 输出文件名（不含扩展名），如 "document"
        - compile_log: 编译日志列表
        
        输出：
        - success: 是否编译成功（布尔值）
        
        这个函数执行bibtex编译处理参考文献
        """
        try:
            cmd = ["bibtex", f"{output_name}.aux"]
            
            result = subprocess.run(
                cmd,
                cwd=self.work_dir,
                capture_output=True,
                text=True,
                timeout=60,
                encoding='utf-8',
                errors='replace'
            )
            
            # 记录bibtex输出
            if result.stdout:
                compile_log.append("bibtex编译输出:")
                compile_log.append(result.stdout)
            
            if result.stderr:
                compile_log.append("bibtex编译错误:")
                compile_log.append(result.stderr)
            
            # 检查返回码
            if result.returncode == 0:
                compile_log.append("bibtex编译成功")
                return True
            else:
                compile_log.append(f"bibtex编译失败，返回码: {result.returncode}")
                return False
                
        except subprocess.TimeoutExpired:
            compile_log.append("bibtex编译超时")
            return False
        except Exception as e:
            compile_log.append(f"bibtex编译异常: {e}")
            return False


def compile_task(task_id: str, tex_content: str, output_name: str, 
                dependencies: Dict[str, str] = None):
    """
    异步编译任务函数
    
    输入：
    - task_id: 任务ID，如 "task_12345"
    - tex_content: LaTeX文档内容
    - output_name: 输出文件名
    - dependencies: 依赖文件字典
    
    输出：无（结果存储在全局任务存储中）
    
    这个函数在后台线程中执行编译任务
    """
    global active_tasks, task_storage
    
    try:
        active_tasks += 1
        
        # 更新任务状态为运行中
        if task_id in task_storage:
            task_storage[task_id].status = "running"
            task_storage[task_id].progress = 10.0
            task_storage[task_id].updated_at = datetime.now()
        
        # 创建编译器并执行编译
        compiler = LaTeXCompiler()
        task_storage[task_id].progress = 30.0
        
        result = compiler.compile_latex(tex_content, output_name, dependencies)
        task_storage[task_id].progress = 90.0
        
        # 更新任务状态
        if result.success:
            task_storage[task_id].status = "completed"
            task_storage[task_id].progress = 100.0
        else:
            task_storage[task_id].status = "failed"
        
        task_storage[task_id].result = result
        task_storage[task_id].updated_at = datetime.now()
        
        logger.info(f"异步编译任务完成: {task_id}, 成功: {result.success}")
        
    except Exception as e:
        error_msg = f"异步编译任务异常: {e}"
        logger.error(f"任务 {task_id} 异常: {error_msg}")
        
        if task_id in task_storage:
            task_storage[task_id].status = "failed"
            task_storage[task_id].result = CompileResponse(
                success=False,
                error=error_msg,
                log=""
            )
            task_storage[task_id].updated_at = datetime.now()
    
    finally:
        active_tasks -= 1

# API端点
@app.get("/health")
async def health_check():
    """
    健康检查端点
    
    输入：无
    输出：服务器状态信息
    
    这个端点用于检查服务器是否正常运行
    """
    return {
        "status": "healthy",
        "service": "LaTeX Compile Server",
        "active_tasks": active_tasks,
        "timestamp": datetime.now().isoformat()
    }

@app.post("/compile/sync", response_model=CompileResponse)
async def compile_sync(request: CompileRequest):
    """
    同步编译端点
    
    输入：编译请求对象，包含LaTeX内容和依赖文件
    输出：编译结果对象，包含PDF内容或错误信息
    
    这个端点执行同步LaTeX编译，等待编译完成后返回结果
    """
    try:
        logger.info(f"收到同步编译请求: {request.output_name}")
        
        # 创建编译器并执行编译
        compiler = LaTeXCompiler()
        result = compiler.compile_latex(
            request.tex_content, 
            request.output_name, 
            request.dependencies
        )
        
        logger.info(f"同步编译完成: {request.output_name}, 成功: {result.success}")
        return result
        
    except Exception as e:
        error_msg = f"同步编译异常: {e}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

@app.post("/compile/async", response_model=AsyncCompileResponse)
async def compile_async(request: CompileRequest, background_tasks: BackgroundTasks):
    """
    异步编译端点
    
    输入：编译请求对象
    输出：异步编译响应对象，包含任务ID
    
    这个端点提交异步编译任务，立即返回任务ID
    """
    try:
        # 生成任务ID
        task_id = f"task_{uuid.uuid4().hex[:8]}"
        
        # 创建任务状态
        task_status = TaskStatus(
            task_id=task_id,
            status="pending",
            progress=0.0,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        task_storage[task_id] = task_status
        
        # 提交后台任务
        background_tasks.add_task(
            compile_task,
            task_id,
            request.tex_content,
            request.output_name,
            request.dependencies
        )
        
        logger.info(f"提交异步编译任务: {task_id}")
        
        return AsyncCompileResponse(
            success=True,
            task_id=task_id
        )
        
    except Exception as e:
        error_msg = f"异步编译提交异常: {e}"
        logger.error(error_msg)
        return AsyncCompileResponse(
            success=False,
            error=error_msg
        )

@app.get("/status/{task_id}", response_model=TaskStatus)
async def get_task_status(task_id: str):
    """
    查询任务状态端点
    
    输入：任务ID
    输出：任务状态对象
    
    这个端点用于查询异步编译任务的当前状态
    """
    if task_id not in task_storage:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    return task_storage[task_id]

@app.delete("/task/{task_id}")
async def delete_task(task_id: str):
    """
    删除任务端点
    
    输入：任务ID
    输出：删除结果
    
    这个端点用于删除已完成的任务
    """
    if task_id not in task_storage:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    del task_storage[task_id]
    return {"message": f"任务 {task_id} 已删除"}

# 定期清理过期任务
def cleanup_expired_tasks():
    """
    清理过期任务
    
    输入：无
    输出：无
    
    这个函数定期清理超过24小时的已完成任务
    """
    while True:
        try:
            current_time = datetime.now()
            expired_tasks = []
            
            for task_id, task_status in task_storage.items():
                # 清理超过24小时的已完成任务
                if (task_status.status in ["completed", "failed"] and 
                    current_time - task_status.updated_at > timedelta(hours=24)):
                    expired_tasks.append(task_id)
            
            for task_id in expired_tasks:
                del task_storage[task_id]
                logger.info(f"清理过期任务: {task_id}")
            
            if expired_tasks:
                logger.info(f"清理了 {len(expired_tasks)} 个过期任务")
            
        except Exception as e:
            logger.error(f"清理过期任务时出错: {e}")
        
        # 每小时清理一次
        time.sleep(3600)

# 启动清理线程
cleanup_thread = threading.Thread(target=cleanup_expired_tasks, daemon=True)
cleanup_thread.start()

def main():
    """
    主函数，启动LaTeX编译服务器
    """
    print("=" * 70)
    print("启动LaTeX编译服务器（修复编码问题版本）")
    print("=" * 70)
    
    # 检查LaTeX环境
    try:
        result = subprocess.run(["pdflatex", "--version"], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print("✓ LaTeX环境检查通过")
            print(f"pdflatex版本: {result.stdout.splitlines()[0]}")
        else:
            print("✗ LaTeX环境检查失败")
            print("请确保已安装LaTeX（如TeX Live）")
            return
    except Exception as e:
        print(f"✗ LaTeX环境检查异常: {e}")
        print("请确保已安装LaTeX并添加到PATH")
        return
    
    # 启动服务器
    print("\n启动HTTP服务器...")
    print("服务器地址: http://localhost:9851")
    print("API文档: http://localhost:9851/docs")
    print("健康检查: http://localhost:9851/health")
    print("\n按 Ctrl+C 停止服务器")
    
    try:
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=9851,
            log_level="info"
        )
    except KeyboardInterrupt:
        print("\n服务器已停止")
    except Exception as e:
        print(f"启动服务器时出错: {e}")

if __name__ == "__main__":
    main()


# docker compose -f docker-compose-latex-server.yml down
# docker compose -f docker-compose-latex-server.yml up --build -d
