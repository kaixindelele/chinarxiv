#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ChinArXiv论文翻译器 - FastAPI Web应用

主要功能：
1. 支持arxiv链接/ID输入翻译
2. 支持本地PDF上传翻译
3. 实时日志更新（SSE）
4. 缓存管理
5. 文件下载

技术栈：FastAPI + HTML + JS + CSS
"""

import os
import sys
import json
import asyncio
import hashlib
import shutil
import logging
import requests
import threading
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# 添加当前目录到Python路径
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

# 导入翻译器
from arxiv_translator import ArxivTranslator
from step1_arxiv_downloader import ArxivDownloader
from config import API_KEY, BASE_URL, LLM_MODEL

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 全局变量
CACHE_DIR = Path("./arxiv_cache")
UPLOADS_DIR = Path("./uploads")
STATIC_DIR = Path("./static")
CACHE_METADATA_FILE = CACHE_DIR / "cache_metadata.json"

# 创建必要目录
CACHE_DIR.mkdir(exist_ok=True)
UPLOADS_DIR.mkdir(exist_ok=True)
STATIC_DIR.mkdir(exist_ok=True)

# 翻译状态管理
translation_tasks = {}

# 线程池执行器
executor = ThreadPoolExecutor(max_workers=3)

class TranslationStatus:
    """翻译状态管理"""
    def __init__(self, task_id: str):
        self.task_id = task_id
        self.status = "pending"
        self.progress = 0
        self.logs = []
        self.result_files = []
        self.error = None
        self.start_time = datetime.now()
        self._lock = threading.Lock()  # 线程安全的锁
        
    def add_log(self, message: str):
        """添加日志（线程安全）"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        with self._lock:
            self.logs.append(log_entry)
        logger.info(message)
        
    def set_progress(self, progress: int):
        """设置进度（线程安全）"""
        with self._lock:
            self.progress = progress
            
    def set_status(self, status: str):
        """设置状态（线程安全）"""
        with self._lock:
            self.status = status
            
    def add_result_file(self, file_path: str):
        """添加结果文件（线程安全）"""
        with self._lock:
            self.result_files.append(file_path)
            
    def set_error(self, error: str):
        """设置错误（线程安全）"""
        with self._lock:
            self.error = error
        
    def to_dict(self):
        """转换为字典（线程安全）"""
        with self._lock:
            return {
                "task_id": self.task_id,
                "status": self.status,
                "progress": self.progress,
                "logs": self.logs.copy(),
                "result_files": self.result_files.copy(),
                "error": self.error,
                "elapsed_time": (datetime.now() - self.start_time).seconds
            }


# 缓存管理
class CacheManager:
    """缓存管理器"""
    
    def __init__(self):
        self._lock = threading.Lock()  # 线程安全的锁，必须先初始化
        self.metadata = self.load_metadata()
        
    def load_metadata(self) -> Dict[str, Any]:
        """加载缓存元数据（线程安全）"""
        with self._lock:
            try:
                if CACHE_METADATA_FILE.exists():
                    with open(CACHE_METADATA_FILE, 'r', encoding='utf-8') as f:
                        return json.load(f)
            except Exception as e:
                logger.warning(f"加载缓存元数据失败: {e}")
            return {}
    
    def save_metadata(self):
        """保存缓存元数据（线程安全，增量保存）"""
        with self._lock:
            try:
                # 先读取最新的元数据文件
                existing_metadata = {}
                if CACHE_METADATA_FILE.exists():
                    try:
                        with open(CACHE_METADATA_FILE, 'r', encoding='utf-8') as f:
                            existing_metadata = json.load(f)
                    except Exception as e:
                        logger.warning(f"读取现有元数据失败: {e}")
                
                # 合并当前metadata到existing_metadata（新增模式）
                existing_metadata.update(self.metadata)
                
                # 写回文件
                with open(CACHE_METADATA_FILE, 'w', encoding='utf-8') as f:
                    json.dump(existing_metadata, f, ensure_ascii=False, indent=2)
                
                # 更新内存中的metadata
                self.metadata = existing_metadata
                
            except Exception as e:
                logger.error(f"保存缓存元数据失败: {e}")
    
    def get_cache_key(self, identifier: str, params: dict) -> str:
        """生成缓存键"""
        cache_content = f"{identifier}|{json.dumps(params, sort_keys=True)}"
        return hashlib.md5(cache_content.encode('utf-8')).hexdigest()
    
    def check_cache(self, identifier: str, params: dict) -> Optional[List[str]]:
        """检查缓存（线程安全）"""
        cache_key = self.get_cache_key(identifier, params)
        
        with self._lock:
            # 先重新加载元数据，确保获取最新数据
            if CACHE_METADATA_FILE.exists():
                try:
                    with open(CACHE_METADATA_FILE, 'r', encoding='utf-8') as f:
                        self.metadata = json.load(f)
                except Exception as e:
                    logger.warning(f"重新加载元数据失败: {e}")
            
            if cache_key in self.metadata:
                cache_info = self.metadata[cache_key]
                files = cache_info.get('files', [])
                
                # 检查文件是否存在
                existing_files = [f for f in files if Path(f).exists()]
                if existing_files:
                    logger.info(f"找到缓存: {identifier}")
                    return existing_files
        
        return None
    
    def check_local_pdf_cache(self, pdf_path: str, output_bilingual: bool) -> Optional[List[str]]:
        """检查本地PDF翻译缓存"""
        try:
            pdf_file = Path(pdf_path)
            if not pdf_file.exists():
                return None
            
            # 根据原始文件路径确定翻译输出目录和文件名
            # 例如: arxiv_cache/DeepSeek_OCR_paper/DeepSeek_OCR_paper.pdf
            #   -> arxiv_cache/DeepSeek_OCR_paper/translation/DeepSeek_OCR_paper.zh-CN.{dual|mono}.pdf
            
            parent_dir = pdf_file.parent
            translation_dir = parent_dir / "translation"
            basename = pdf_file.stem  # 不含扩展名的文件名
            
            # 检查翻译文件是否存在
            existing_files = []
            
            # 检查双语版本
            dual_pdf = translation_dir / f"{basename}.zh-CN.dual.pdf"
            if dual_pdf.exists():
                existing_files.append(str(dual_pdf))
            
            # 检查单语版本
            mono_pdf = translation_dir / f"{basename}.zh-CN.mono.pdf"
            if mono_pdf.exists():
                existing_files.append(str(mono_pdf))
            
            if existing_files:
                logger.info(f"找到本地PDF翻译缓存: {pdf_path}")
                return existing_files
            
            return None
            
        except Exception as e:
            logger.error(f"检查本地PDF缓存失败: {e}")
            return None
    
    def add_local_pdf_cache(self, pdf_path: str, files: List[str], user_requirements: str = ""):
        """添加本地PDF翻译到缓存（线程安全，增量模式）"""
        try:
            # 使用原始PDF路径作为标识符
            pdf_file = Path(pdf_path)
            identifier = str(pdf_file.relative_to(CACHE_DIR)) if pdf_file.is_relative_to(CACHE_DIR) else str(pdf_file)
            
            # 生成缓存键
            cache_params = {
                "user_requirements": user_requirements,
                "output_bilingual": True,
                "type": "local_pdf"
            }
            cache_key = self.get_cache_key(identifier, cache_params)
            
            total_size = sum(Path(f).stat().st_size for f in files if Path(f).exists())
            
            with self._lock:
                # 先重新加载最新元数据
                if CACHE_METADATA_FILE.exists():
                    try:
                        with open(CACHE_METADATA_FILE, 'r', encoding='utf-8') as f:
                            self.metadata = json.load(f)
                    except Exception as e:
                        logger.warning(f"重新加载元数据失败: {e}")
                
                # 新增缓存条目（arxiv_id等字段置空）
                self.metadata[cache_key] = {
                    'arxiv_id': "",  # 本地PDF没有arxiv_id
                    'arxiv_input': "",  # 本地PDF没有arxiv输入
                    'user_requirements': user_requirements,
                    'user_terms': "",
                    'identifier': identifier,
                    'file_path': files[0] if files else "",  # 主要文件路径
                    'original_path': pdf_path,  # 原始PDF路径
                    'files': files,  # 所有翻译文件
                    'created_time': datetime.now().isoformat(),
                    'total_size': total_size,
                    'type': 'local_pdf'
                }
            
            # 保存时会自动合并
            self.save_metadata()
            logger.info(f"本地PDF翻译已缓存: {identifier}")
            
        except Exception as e:
            logger.error(f"添加本地PDF缓存失败: {e}")
    
    def add_cache(self, identifier: str, params: dict, files: List[str]):
        """添加arxiv缓存（线程安全，增量模式）"""
        cache_key = self.get_cache_key(identifier, params)
        
        total_size = sum(Path(f).stat().st_size for f in files if Path(f).exists())
        
        with self._lock:
            # 先重新加载最新元数据
            if CACHE_METADATA_FILE.exists():
                try:
                    with open(CACHE_METADATA_FILE, 'r', encoding='utf-8') as f:
                        self.metadata = json.load(f)
                except Exception as e:
                    logger.warning(f"重新加载元数据失败: {e}")
            
            # 新增缓存条目
            self.metadata[cache_key] = {
                'arxiv_id': identifier,
                'arxiv_input': identifier,
                'user_requirements': params.get('user_requirements', ''),
                'user_terms': params.get('user_terms', ''),
                'identifier': identifier,
                'file_path': files[0] if files else "",
                'original_path': files[0] if files else "",
                'files': files,
                'created_time': datetime.now().isoformat(),
                'total_size': total_size,
                'type': 'arxiv'
            }
        
        # 保存时会自动合并
        self.save_metadata()
        logger.info(f"Arxiv缓存已添加: {identifier}")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计（线程安全，刷新最新数据）"""
        with self._lock:
            # 重新加载最新元数据
            if CACHE_METADATA_FILE.exists():
                try:
                    with open(CACHE_METADATA_FILE, 'r', encoding='utf-8') as f:
                        self.metadata = json.load(f)
                except Exception as e:
                    logger.warning(f"重新加载元数据失败: {e}")
            
            total_count = len(self.metadata)
            total_size = sum(info.get('total_size', 0) for info in self.metadata.values())
            
            return {
                'count': total_count,
                'size_mb': total_size / (1024 * 1024)
            }
    
    def clear_cache(self) -> int:
        """清理缓存（已禁用 - 不再清空缓存，仅用于未来扩展）"""
        logger.warning("clear_cache已禁用，不会清空任何缓存数据")
        return 0


# 创建全局缓存管理器
cache_manager = CacheManager()


# FastAPI应用
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("启动ChinArXiv翻译器...")
    yield
    logger.info("关闭ChinArXiv翻译器...")

app = FastAPI(
    title="ChinArXiv论文翻译器",
    description="支持arxiv论文和本地PDF翻译",
    version="1.0.0",
    lifespan=lifespan
)

# CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============= 路由处理 =============

@app.get("/", response_class=HTMLResponse)
async def index():
    """主页"""
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    else:
        return HTMLResponse("<h1>请创建 static/index.html 文件</h1>")


@app.get("/api/health")
async def health_check():
    """健康检查"""
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat()
    }


@app.get("/api/cache/stats")
async def get_cache_stats():
    """获取缓存统计"""
    stats = cache_manager.get_cache_stats()
    return {
        "success": True,
        "stats": stats
    }


@app.post("/api/cache/clear")
async def clear_cache():
    """清理缓存"""
    deleted_count = cache_manager.clear_cache()
    return {
        "success": True,
        "message": f"已清理 {deleted_count} 个缓存文件"
    }


@app.post("/api/translate/arxiv")
async def translate_arxiv(
    arxiv_input: str = Form(...),
    user_requirements: str = Form("保持学术性和专业性，确保术语翻译的一致性"),
    user_terms: str = Form(""),
    output_bilingual: bool = Form(False),
    force_retranslate: bool = Form(False),
    background_tasks: BackgroundTasks = None
):
    """
    翻译arxiv论文
    
    流程：
    1. 检查缓存（如果不强制重新翻译）
    2. 尝试ArxivTranslator（latex翻译）
    3. 失败则下载PDF到 arxiv_cache/arxiv_id/extract/
    4. 用babeldoc翻译，输出到 arxiv_cache/arxiv_id/translation/
    """
    task_id = hashlib.md5(f"{arxiv_input}{datetime.now()}".encode()).hexdigest()[:8]
    
    # 创建翻译状态
    status = TranslationStatus(task_id)
    translation_tasks[task_id] = status
    
    # 在线程池中启动翻译任务
    executor.submit(
        translate_arxiv_task_sync,
        task_id,
        arxiv_input,
        user_requirements,
        user_terms,
        output_bilingual,
        force_retranslate
    )
    
    return {
        "success": True,
        "task_id": task_id,
        "message": "翻译任务已启动"
    }


@app.post("/api/translate/upload")
async def translate_upload(
    file: UploadFile = File(...),
    user_requirements: str = Form("保持学术性和专业性，确保术语翻译的一致性"),
    output_bilingual: bool = Form(False),
    background_tasks: BackgroundTasks = None
):
    """
    翻译上传的PDF
    
    流程：
    1. 保存到 arxiv_cache/filename/
    2. 用babeldoc翻译，输出到 arxiv_cache/filename/translation/
    """
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="只支持PDF文件")
    
    task_id = hashlib.md5(f"{file.filename}{datetime.now()}".encode()).hexdigest()[:8]
    
    # 创建翻译状态
    status = TranslationStatus(task_id)
    translation_tasks[task_id] = status
    
    # 保存上传的文件
    filename = Path(file.filename).stem
    upload_dir = CACHE_DIR / filename
    upload_dir.mkdir(exist_ok=True)
    
    file_path = upload_dir / file.filename
    
    try:
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        status.add_log(f"文件已保存: {file_path}")
        
    except Exception as e:
        status.status = "error"
        status.error = f"文件保存失败: {e}"
        return {"success": False, "error": str(e)}
    
    # 在线程池中启动翻译任务
    executor.submit(
        translate_upload_task_sync,
        task_id,
        str(file_path),
        filename,
        user_requirements,
        output_bilingual
    )
    
    return {
        "success": True,
        "task_id": task_id,
        "message": "上传成功，翻译任务已启动"
    }


@app.get("/api/translate/status/{task_id}")
async def get_translation_status(task_id: str):
    """获取翻译状态"""
    if task_id not in translation_tasks:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    status = translation_tasks[task_id]
    return {
        "success": True,
        "status": status.to_dict()
    }


@app.get("/api/translate/logs/{task_id}")
async def stream_logs(task_id: str):
    """实时日志流（SSE）"""
    if task_id not in translation_tasks:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    async def generate():
        status = translation_tasks[task_id]
        last_log_index = 0
        
        while True:
            try:
                # 获取新日志（线程安全）
                with status._lock:
                    current_logs = status.logs[last_log_index:]
                    current_progress = status.progress
                    current_status = status.status
                    current_files = status.result_files.copy()
                    current_error = status.error
                
                # 发送新日志
                for log in current_logs:
                    yield f"data: {json.dumps({'type': 'log', 'message': log}, ensure_ascii=False)}\n\n"
                
                last_log_index += len(current_logs)
                
                # 发送进度更新
                yield f"data: {json.dumps({'type': 'progress', 'progress': current_progress, 'status': current_status}, ensure_ascii=False)}\n\n"
                
                # 如果完成或失败，发送最终消息
                if current_status in ["completed", "error"]:
                    if current_status == "completed":
                        yield f"data: {json.dumps({'type': 'success', 'files': current_files}, ensure_ascii=False)}\n\n"
                    else:
                        yield f"data: {json.dumps({'type': 'error', 'message': current_error}, ensure_ascii=False)}\n\n"
                    
                    yield f"data: {json.dumps({'type': 'done'})}\n\n"
                    break
                
                await asyncio.sleep(0.3)  # 更频繁的更新
                
            except Exception as e:
                logger.error(f"日志流错误: {e}")
                break
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@app.get("/api/download/{task_id}/{filename}")
async def download_file(task_id: str, filename: str):
    """下载翻译结果"""
    if task_id not in translation_tasks:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    status = translation_tasks[task_id]
    
    # 查找文件
    for file_path in status.result_files:
        if Path(file_path).name == filename:
            if Path(file_path).exists():
                return FileResponse(
                    file_path,
                    filename=filename,
                    media_type="application/pdf"
                )
    
    raise HTTPException(status_code=404, detail="文件不存在")


# ============= 后台翻译任务 =============

def translate_arxiv_task_sync(
    task_id: str,
    arxiv_input: str,
    user_requirements: str,
    user_terms: str,
    output_bilingual: bool,
    force_retranslate: bool
):
    """arxiv翻译任务（同步版本，在线程池中运行）"""
    status = translation_tasks[task_id]
    
    try:
        status.set_status("running")
        status.add_log("开始翻译arxiv论文...")
        status.set_progress(5)
        
        # 解析arxiv ID
        downloader = ArxivDownloader()
        success_parse, arxiv_id, _ = downloader.parse_arxiv_input(arxiv_input)
        
        if not success_parse:
            raise ValueError("无法解析arxiv输入")
        
        status.add_log(f"arxiv ID: {arxiv_id}")
        status.set_progress(10)
        
        # 检查缓存
        cache_params = {
            "user_requirements": user_requirements,
            "user_terms": user_terms,
            "output_bilingual": output_bilingual
        }
        
        if not force_retranslate:
            cached_files = cache_manager.check_cache(arxiv_id, cache_params)
            if cached_files:
                status.add_log("使用缓存结果")
                for f in cached_files:
                    status.add_result_file(f)
                status.set_status("completed")
                status.set_progress(100)
                return
        
        status.add_log("尝试使用ArxivTranslator翻译...")
        status.set_progress(20)
        
        # 尝试ArxivTranslator翻译
        arxiv_dir = CACHE_DIR / arxiv_id
        translation_dir = arxiv_dir / "translation"
        translation_dir.mkdir(parents=True, exist_ok=True)
        
        # 初始化翻译器
        translator = ArxivTranslator(
            cache_dir=str(CACHE_DIR),
            output_dir=str(translation_dir),
            work_dir=str(translation_dir),
            api_key=API_KEY,
            base_url=BASE_URL,
            llm_model=LLM_MODEL
        )
        
        # 解析用户术语
        user_terms_dict = {}
        if user_terms.strip():
            for line in user_terms.strip().split('\n'):
                if ':' in line or '：' in line:
                    separator = ':' if ':' in line else '：'
                    key, value = line.split(separator, 1)
                    user_terms_dict[key.strip()] = value.strip()
        
        # 进度回调
        def progress_callback(step, prog, message):
            status.set_progress(20 + int(prog * 0.5))  # 20-70%
            status.add_log(f"Step {step}: {message}")
        
        # 执行翻译
        success, result, details = translator.translate_arxiv(
            arxiv_input=arxiv_input,
            user_requirements=user_requirements,
            user_terms=user_terms_dict,
            progress_callback=progress_callback,
            compile_pdf=True
        )
        
        if success:
            # 检查返回的是PDF还是TEX文件
            result_path = Path(result)
            if result_path.suffix.lower() == '.pdf':
                # 返回的是PDF文件，翻译成功
                status.add_log("ArxivTranslator翻译成功！")
                status.add_result_file(result)
                status.set_progress(100)
                status.set_status("completed")
                
                # 添加到缓存
                cache_manager.add_cache(arxiv_id, cache_params, [result])
                return
            elif result_path.suffix.lower() == '.tex':
                # 返回的是TEX文件，说明PDF编译失败，需要使用babeldoc
                status.add_log(f"ArxivTranslator返回tex文件: {result_path.name}")
                status.add_log("PDF编译失败，尝试使用babeldoc翻译...")
                status.set_progress(70)
                # 继续执行下面的babeldoc翻译流程
            else:
                # 未知文件类型
                status.add_log(f"警告: 未知的返回文件类型: {result_path.suffix}")
                status.add_result_file(result)
                status.set_progress(100)
                status.set_status("completed")
                cache_manager.add_cache(arxiv_id, cache_params, [result])
                return
        else:
            # ArxivTranslator失败，使用babeldoc
            status.add_log("ArxivTranslator翻译失败，尝试使用babeldoc...")
            status.set_progress(70)
        
        # 下载PDF到extract目录
        extract_dir = arxiv_dir / "extract"
        extract_dir.mkdir(parents=True, exist_ok=True)
        
        pdf_path = extract_dir / f"{arxiv_id}.pdf"
        
        if not pdf_path.exists():
            status.add_log("下载arxiv PDF...")
            pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
            
            response = requests.get(pdf_url, timeout=60)
            if response.status_code == 200:
                with open(pdf_path, 'wb') as f:
                    f.write(response.content)
                status.add_log(f"PDF已下载: {pdf_path}")
            else:
                raise Exception(f"下载PDF失败: HTTP {response.status_code}")
        
        status.set_progress(80)
        
        # 使用babeldoc翻译
        status.add_log("使用babeldoc翻译PDF...")
        result_files = translate_with_babeldoc_sync(
            status,
            str(pdf_path),
            str(translation_dir),
            output_bilingual
        )
        
        if result_files:
            for f in result_files:
                status.add_result_file(f)
            status.set_status("completed")
            status.set_progress(100)
            status.add_log("翻译完成！")
            
            # 添加到缓存
            cache_manager.add_cache(arxiv_id, cache_params, result_files)
        else:
            raise Exception("babeldoc翻译失败")
        
    except Exception as e:
        status.set_status("error")
        status.set_error(str(e))
        status.add_log(f"错误: {e}")
        logger.error(f"翻译失败: {e}", exc_info=True)


def translate_upload_task_sync(
    task_id: str,
    pdf_path: str,
    filename: str,
    user_requirements: str,
    output_bilingual: bool
):
    """上传文件翻译任务（同步版本，在线程池中运行）"""
    status = translation_tasks[task_id]
    
    try:
        status.set_status("running")
        status.add_log("开始翻译上传的PDF...")
        status.set_progress(5)
        
        # 检查是否已有翻译缓存
        status.add_log("检查翻译缓存...")
        cached_files = cache_manager.check_local_pdf_cache(pdf_path, output_bilingual)
        
        if cached_files:
            status.add_log(f"找到已翻译的文件，使用缓存结果")
            for f in cached_files:
                status.add_result_file(f)
                status.add_log(f"缓存文件: {Path(f).name}")
            status.set_status("completed")
            status.set_progress(100)
            status.add_log("翻译完成（使用缓存）！")
            return
        
        status.add_log("未找到缓存，开始新的翻译任务")
        status.set_progress(10)
        
        # 输出目录
        output_dir = CACHE_DIR / filename / "translation"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        status.add_log(f"输出目录: {output_dir}")
        status.set_progress(20)
        
        # 使用babeldoc翻译
        status.add_log("使用babeldoc翻译PDF...")
        result_files = translate_with_babeldoc_sync(
            status,
            pdf_path,
            str(output_dir),
            output_bilingual
        )
        
        if result_files:
            for f in result_files:
                status.add_result_file(f)
            status.set_status("completed")
            status.set_progress(100)
            status.add_log("翻译完成！")
            
            # 添加到缓存
            status.add_log("保存翻译结果到缓存...")
            cache_manager.add_local_pdf_cache(pdf_path, result_files, user_requirements)
            status.add_log("缓存已更新")
        else:
            raise Exception("babeldoc翻译失败")
        
    except Exception as e:
        status.set_status("error")
        status.set_error(str(e))
        status.add_log(f"错误: {e}")
        logger.error(f"翻译失败: {e}", exc_info=True)


def translate_with_babeldoc_sync(
    status: TranslationStatus,
    pdf_path: str,
    output_dir: str,
    no_dual: bool = True
) -> List[str]:
    """使用babeldoc翻译PDF（同步版本）"""
    try:
        url = "http://localhost:8321/translate/stream"
        
        payload = {
            "pdf_path": pdf_path,
            "output_dir": output_dir,
            "no_dual": no_dual
        }
        
        status.add_log("连接babeldoc服务...")
        
        # 发送请求
        response = requests.post(url, json=payload, stream=True, timeout=3600,
                                 proxies={'http': None, 'https': None})
        
        if response.status_code != 200:
            status.add_log(f"babeldoc服务错误: HTTP {response.status_code}")
            return []
        
        pdf_files = []
        
        # 获取当前进度
        with status._lock:
            base_progress = status.progress
        
        # 逐行读取SSE响应
        for line in response.iter_lines():
            if not line:
                continue
            
            line_str = line.decode('utf-8')
            
            if line_str.startswith("data: "):
                data_str = line_str[6:]
                
                try:
                    data = json.loads(data_str)
                    msg_type = data.get("type", "unknown")
                    
                    if msg_type == "log":
                        status.add_log(data.get("message", ""))
                    
                    elif msg_type == "success":
                        pdf_files = data.get("pdf_paths", [])
                        status.add_log(f"生成了 {len(pdf_files)} 个PDF文件")
                    
                    elif msg_type == "error":
                        status.add_log(f"错误: {data.get('message', '未知错误')}")
                    
                    elif msg_type == "done":
                        status.add_log("babeldoc翻译完成")
                        break
                    
                    # 更新进度
                    status.set_progress(min(base_progress + 20, 95))
                    
                except json.JSONDecodeError:
                    pass
        
        return pdf_files
        
    except Exception as e:
        status.add_log(f"babeldoc翻译异常: {e}")
        logger.error(f"babeldoc翻译异常: {e}", exc_info=True)
        return []


# ============= 静态文件服务 =============

# 挂载静态文件目录
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


if __name__ == "__main__":
    import uvicorn
    
    print("=" * 70)
    print("🌍 ChinArXiv论文翻译器")
    print("=" * 70)
    print(f"📊 配置信息:")
    print(f"   LLM模型: {LLM_MODEL}")
    print(f"   API地址: {BASE_URL}")
    print(f"   缓存目录: {CACHE_DIR}")
    print(f"\n🚀 启动Web服务...")
    print(f"   访问地址: http://localhost:12985")
    print("=" * 70)
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=12985,
        log_level="info"
    )

