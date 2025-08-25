#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Arxiv论文翻译器 - Gradio网页界面

主要功能：
1. 提供友好的网页界面
2. 支持arxiv链接或ID输入
3. 实时显示翻译进度
4. 自动缓存翻译结果
5. 支持PDF下载
6. 错误处理和用户反馈

作者：基于ArxivTranslator改进
"""

import os
import sys
import time
import json
import hashlib
import logging
from pathlib import Path
from typing import Tuple, Optional, Dict, Any, List
from datetime import datetime

import gradio as gr

# 添加当前目录到Python路径
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

# 导入主翻译器
try:
    from arxiv_translator import ArxivTranslator, translate_arxiv_paper
    from config import API_KEY, BASE_URL, LLM_MODEL
    from step1_arxiv_downloader import ArxivDownloader
except ImportError as e:
    print(f"模块导入失败: {e}")
    print("请确保main_translator.py和config.py文件存在")
    sys.exit(1)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ArxivTranslatorWebUI:
    """
    Arxiv翻译器网页界面类
    
    主要功能：
    1. 管理翻译缓存
    2. 处理用户请求
    3. 提供进度反馈
    4. 管理文件下载
    """
    
    def __init__(self):
        """初始化网页界面"""
        # 创建必要目录
        self.cache_dir = Path("./arxiv_cache")
        self.translation_cache_dir = Path("./arxiv_cache")
        
        # 创建基础缓存目录
        self.cache_dir.mkdir(exist_ok=True)
        
        # 缓存元数据文件
        self.cache_metadata_file = self.translation_cache_dir / "cache_metadata.json"
        self.cache_metadata = self.load_cache_metadata()
        
        # 翻译器将在翻译时动态初始化，因为需要arxiv_id来确定路径
        self.translator = None
        
        # 当前翻译状态
        self.current_translation = {
            'arxiv_id': None,
            'status': 'idle',
            'progress': 0,
            'message': '',
            'result_path': None,
            'error': None
        }
        
        logger.info("Arxiv翻译器网页界面初始化完成")
    
    def load_cache_metadata(self) -> Dict[str, Any]:
        """加载缓存元数据"""
        try:
            if self.cache_metadata_file.exists():
                with open(self.cache_metadata_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"加载缓存元数据失败: {e}")
        
        return {}
    
    def save_cache_metadata(self):
        """保存缓存元数据"""
        try:
            with open(self.cache_metadata_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache_metadata, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存缓存元数据失败: {e}")
    
    def get_cache_key(self, arxiv_input: str, user_requirements: str, user_terms: str) -> str:
        """生成缓存键"""
        # 解析arxiv ID
        downloader = ArxivDownloader()
        success, arxiv_id, _ = downloader.parse_arxiv_input(arxiv_input)
        
        if not success:
            # 如果解析失败，使用原始输入
            arxiv_id = arxiv_input
        
        # 创建包含所有参数的缓存键
        cache_content = f"{arxiv_id}|{user_requirements}|{user_terms}"
        cache_key = hashlib.md5(cache_content.encode('utf-8')).hexdigest()
        
        return cache_key, arxiv_id
    
    def check_cache(self, arxiv_input: str, user_requirements: str, user_terms: str) -> Tuple[bool, Optional[str]]:
        """检查是否有缓存的翻译结果"""
        try:
            cache_key, arxiv_id = self.get_cache_key(arxiv_input, user_requirements, user_terms)
            
            if cache_key in self.cache_metadata:
                cache_info = self.cache_metadata[cache_key]
                cached_file = Path(cache_info['file_path'])
                
                # 检查文件是否存在
                if cached_file.exists():
                    logger.info(f"找到缓存翻译: {arxiv_id}")
                    return True, str(cached_file)
                else:
                    # 文件不存在，清理缓存记录
                    del self.cache_metadata[cache_key]
                    self.save_cache_metadata()
                    logger.warning(f"缓存文件不存在，已清理记录: {cached_file}")
            
            return False, None
            
        except Exception as e:
            logger.error(f"检查缓存失败: {e}")
            return False, None
    
    def add_to_cache(self, arxiv_input: str, user_requirements: str, user_terms: str, result_path: str):
        """添加翻译结果到缓存"""
        try:
            cache_key, arxiv_id = self.get_cache_key(arxiv_input, user_requirements, user_terms)
            
            # 翻译结果已经在正确的位置（./arxiv_cache/arxiv_id/translation/），
            # 只需要更新缓存元数据，不需要复制文件
            result_file = Path(result_path)
            if result_file.exists():
                # 更新缓存元数据
                self.cache_metadata[cache_key] = {
                    'arxiv_id': arxiv_id,
                    'arxiv_input': arxiv_input,
                    'user_requirements': user_requirements,
                    'user_terms': user_terms,
                    'file_path': result_path,  # 直接使用原始路径
                    'original_path': result_path,
                    'created_time': datetime.now().isoformat(),
                    'file_size': result_file.stat().st_size
                }
                
                self.save_cache_metadata()
                logger.info(f"翻译结果已缓存: {arxiv_id} -> {result_path}")
                
        except Exception as e:
            logger.error(f"添加缓存失败: {e}")
    
    def translate_paper(self,
                       arxiv_input: str,
                       user_requirements: str = "",
                       user_terms_text: str = "",
                       progress: gr.Progress = None) -> Tuple[str, Optional[str], str]:
        """
        翻译论文的主函数
        
        返回：(状态信息, PDF文件路径, 详细信息)
        """
        if not arxiv_input.strip():
            return "❌ 请输入arxiv链接或ID", None, "输入为空"
        
        try:
            # 重置状态
            self.current_translation = {
                'arxiv_id': None,
                'status': 'starting',
                'progress': 0,
                'message': '开始翻译...',
                'result_path': None,
                'error': None
            }
            
            # 解析arxiv_id以确定目录结构
            from step1_arxiv_downloader import ArxivDownloader
            downloader = ArxivDownloader()
            success_parse, arxiv_id, _ = downloader.parse_arxiv_input(arxiv_input)
            
            if not success_parse:
                return "❌ 无法解析arxiv输入", None, "输入格式错误"
            
            # 根据arxiv_id创建专用目录
            arxiv_translation_dir = self.cache_dir / arxiv_id / "translation"
            arxiv_translation_dir.mkdir(parents=True, exist_ok=True)
            
            # 动态初始化翻译器，使用arxiv_id专用目录
            self.translator = ArxivTranslator(
                cache_dir=str(self.cache_dir),
                output_dir=str(arxiv_translation_dir),
                work_dir=str(arxiv_translation_dir),
                api_key=API_KEY,
                base_url=BASE_URL,
                llm_model=LLM_MODEL
            )
            
            # 解析用户术语
            user_terms = {}
            if user_terms_text.strip():
                try:
                    for line in user_terms_text.strip().split('\n'):
                        if ':' in line or '：' in line:
                            # 支持中英文冒号
                            separator = ':' if ':' in line else '：'
                            key, value = line.split(separator, 1)
                            user_terms[key.strip()] = value.strip()
                except Exception as e:
                    logger.warning(f"解析用户术语失败: {e}")
            
            # 设置默认翻译要求
            if not user_requirements.strip():
                user_requirements = "保持学术性和专业性，确保术语翻译的一致性"
            
            # 检查缓存
            if progress:
                progress(0.05, desc="检查缓存...")
            
            has_cache, cached_file = self.check_cache(arxiv_input, user_requirements, user_terms_text)
            
            if has_cache and cached_file:
                logger.info(f"使用缓存结果: {cached_file}")
                return "✅ 翻译完成（使用缓存）", cached_file, f"从缓存加载: {cached_file}"
            
            # 定义进度回调
            def progress_callback(step, prog, message):
                self.current_translation.update({
                    'status': 'translating',
                    'progress': prog,
                    'message': message
                })
                
                if progress:
                    progress(prog/100, desc=f"Step {step}: {message}")
                
                logger.info(f"Step {step} - {prog:.1f}%: {message}")
            
            # 执行翻译
            if progress:
                progress(0.1, desc="开始翻译...")
            
            success, result, details = self.translator.translate_arxiv(
                arxiv_input=arxiv_input,
                user_requirements=user_requirements,
                user_terms=user_terms,
                progress_callback=progress_callback,
                compile_pdf=True
            )
            
            if success:
                # 翻译成功
                self.current_translation.update({
                    'status': 'completed',
                    'progress': 100,
                    'message': '翻译完成',
                    'result_path': result
                })
                
                # 添加到缓存
                self.add_to_cache(arxiv_input, user_requirements, user_terms_text, result)
                
                # 生成详细信息
                stats = self.translator.get_translation_stats()
                detail_info = f"""翻译完成！

📊 翻译统计:
• Arxiv ID: {stats.get('arxiv_id', 'N/A')}
• 总段落数: {stats.get('total_segments', 0)}
• 成功翻译: {stats.get('translated_segments', 0)}
• 失败段落: {stats.get('failed_segments', 0)}
• 成功率: {stats.get('success_rate', 'N/A')}
• 耗时: {stats.get('duration_str', 'N/A')}

📁 文件信息:
• 结果文件: {result}
• 源码路径: {stats.get('source_path', 'N/A')}
"""
                
                if progress:
                    progress(1.0, desc="翻译完成！")
                
                return "✅ 翻译完成", result, detail_info
                
            else:
                # 翻译失败
                self.current_translation.update({
                    'status': 'failed',
                    'progress': 0,
                    'message': f'翻译失败: {result}',
                    'error': result
                })
                
                error_detail = f"翻译失败: {result}"
                if details.get('errors'):
                    error_detail += f"\n\n详细错误:\n" + "\n".join(f"• {err}" for err in details['errors'])
                
                return f"❌ 翻译失败", None, error_detail
                
        except Exception as e:
            error_msg = f"处理过程出现异常: {e}"
            logger.error(error_msg)
            
            self.current_translation.update({
                'status': 'error',
                'progress': 0,
                'message': error_msg,
                'error': str(e)
            })
            
            import traceback
            traceback.print_exc()
            
            return f"❌ 系统错误", None, f"系统错误: {error_msg}"
    
    def get_cache_info(self) -> str:
        """获取缓存信息"""
        try:
            cache_count = len(self.cache_metadata)
            total_size = 0
            
            for cache_info in self.cache_metadata.values():
                total_size += cache_info.get('file_size', 0)
            
            size_mb = total_size / (1024 * 1024)
            
            info = f"📦 缓存统计:\n"
            info += f"• 缓存文件数: {cache_count}\n"
            info += f"• 总大小: {size_mb:.2f} MB\n"
            
            if cache_count > 0:
                info += f"\n📋 最近缓存:\n"
                # 显示最近的5个缓存
                recent_caches = sorted(
                    self.cache_metadata.values(),
                    key=lambda x: x.get('created_time', ''),
                    reverse=True
                )[:5]
                
                for cache in recent_caches:
                    arxiv_id = cache.get('arxiv_id', 'N/A')
                    created_time = cache.get('created_time', 'N/A')
                    if created_time != 'N/A':
                        try:
                            dt = datetime.fromisoformat(created_time)
                            created_time = dt.strftime("%Y-%m-%d %H:%M")
                        except:
                            pass
                    info += f"• {arxiv_id} ({created_time})\n"
            
            return info
            
        except Exception as e:
            return f"获取缓存信息失败: {e}"
    
    def clear_cache(self) -> str:
        """清理缓存"""
        try:
            # 删除缓存文件和目录
            deleted_count = 0
            for cache_info in self.cache_metadata.values():
                cache_file = Path(cache_info['file_path'])
                if cache_file.exists():
                    cache_file.unlink()
                    deleted_count += 1
                
                # 尝试删除对应的arxiv_id目录（如果为空）
                arxiv_id = cache_info.get('arxiv_id')
                if arxiv_id:
                    arxiv_dir = self.cache_dir / arxiv_id
                    if arxiv_dir.exists():
                        try:
                            # 只删除translation目录下的内容，保留其他内容（如源码）
                            translation_dir = arxiv_dir / "translation"
                            if translation_dir.exists():
                                import shutil
                                shutil.rmtree(translation_dir)
                        except Exception as e:
                            logger.warning(f"清理translation目录失败: {e}")
            
            # 清空元数据
            self.cache_metadata.clear()
            self.save_cache_metadata()
            
            return f"✅ 已清理 {deleted_count} 个缓存文件"
            
        except Exception as e:
            return f"❌ 清理缓存失败: {e}"

# 创建全局实例
web_ui = ArxivTranslatorWebUI()

def create_gradio_interface():
    """创建Gradio界面"""
    
    # 自定义CSS样式
    custom_css = """
    .main-container {
        max-width: 1200px;
        margin: 0 auto;
    }
    .header {
        text-align: center;
        padding: 20px;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border-radius: 10px;
        margin-bottom: 20px;
    }
    .input-section {
        background: #f8f9fa;
        padding: 20px;
        border-radius: 10px;
        margin-bottom: 20px;
    }
    .result-section {
        background: #e8f5e8;
        padding: 20px;
        border-radius: 10px;
    }
    """
    
    with gr.Blocks(css=custom_css, title="ChinArXiv论文翻译器") as interface:
        
        # 标题和说明
        gr.HTML("""
        <div class="header">
            <h1>🌍 ChinArXiv论文翻译器</h1>
            <p>参考gpt_academic，单独抽取出的arxiv论文翻译功能，润色和对话功能，返回请使用https://academic.chatpaper.top.</p>
            <p>有些论文的编译只能返回tex文件，是编译失败，后面我再修复一下Bug，目前成功率大概有8成左右。</p>
            <p>开源代码：https://github.com/kaixindelele/chinarxiv，欢迎点个star。</p>
        </div>
        """)
        
        with gr.Row():
            with gr.Column(scale=1):
                # 输入区域
                gr.HTML('<div class="input-section">')
                gr.Markdown("## 📝 输入论文信息")
                
                arxiv_input = gr.Textbox(
                    label="Arxiv链接或ID",
                    placeholder="例如: 1812.10695 或 https://arxiv.org/abs/1812.10695",
                    info="支持arxiv ID或完整URL"
                )
                
                user_requirements = gr.Textbox(
                    label="翻译要求（可选）",
                    placeholder="例如: 保持学术性和专业性，确保术语翻译的一致性",
                    value="保持学术性和专业性，确保术语翻译的一致性",
                    info="描述您对翻译质量和风格的要求"
                )
                
                user_terms = gr.Textbox(
                    label="术语词典（可选）",
                    placeholder="每行一个术语对，格式: 英文术语:中文翻译\n例如:\ntransformer:变换器\nattention:注意力",
                    lines=5,
                    info="自定义术语翻译，每行一对，用冒号分隔"
                )
                
                translate_btn = gr.Button(
                    "🚀 开始翻译",
                    variant="primary",
                    size="lg"
                )
                            
            with gr.Column(scale=1):
        
                # 结果区域
                gr.HTML('<div class="result-section">')
                gr.Markdown("## 📊 翻译结果")
                
                status_output = gr.Textbox(
                    label="翻译状态",
                    interactive=False
                )
                
                detail_output = gr.Textbox(
                    label="详细信息",
                    interactive=False,
                    lines=10
                )
                
                file_output = gr.File(
                    label="下载翻译结果",
                    interactive=False
                )
                
            with gr.Column(scale=1):
                # 缓存管理区域
                gr.HTML('<div class="input-section">')
                gr.Markdown("## 📦 缓存管理")
                
                cache_info = gr.Textbox(
                    label="缓存信息",
                    value=web_ui.get_cache_info(),
                    interactive=False,
                    lines=10
                )
                
                with gr.Row():
                    refresh_cache_btn = gr.Button("🔄 刷新", size="sm")
                
                gr.HTML('</div>')
                
                # 示例区域
                gr.Markdown("""
                **使用说明：**
                1. 输入arxiv论文的ID或完整链接
                2. 可选：自定义翻译要求和术语词典-已经默认内置了常见AI术语表
                3. 点击"开始翻译"按钮
                4. 等待翻译完成后下载PDF文件
                5. 重复翻译相同论文会自动使用缓存
                """)

        
        # 事件绑定
        translate_btn.click(
            fn=web_ui.translate_paper,
            inputs=[arxiv_input, user_requirements, user_terms],
            outputs=[status_output, file_output, detail_output],
            show_progress=True
        )
        
        refresh_cache_btn.click(
            fn=web_ui.get_cache_info,
            outputs=cache_info
        )
        
        # 页面加载时刷新缓存信息
        interface.load(
            fn=web_ui.get_cache_info,
            outputs=cache_info
        )
    
    return interface

def main():
    """启动Gradio应用"""
    print("=" * 70)
    print("🌍 启动Arxiv论文翻译器网页界面")
    print("=" * 70)
    
    # 检查配置
    if not API_KEY:
        print("⚠️  警告: 未配置API_KEY，请在config.py中设置")
    
    print(f"📊 配置信息:")
    print(f"   LLM模型: {LLM_MODEL}")
    print(f"   API地址: {BASE_URL}")
    print(f"   缓存目录: {web_ui.cache_dir}")
    # print(f"   输出目录: {web_ui.output_dir}")
    
    # 创建并启动界面
    interface = create_gradio_interface()
    
    print(f"\n🚀 启动Gradio服务...")
    print(f"   本地访问: http://localhost:7860")
    print(f"   网络访问: 启动后查看控制台输出")
    
    # 启动服务
    interface.launch(
        server_name="0.0.0.0",  # 允许外部访问
        server_port=12985,       # 端口
        share=False,            # 不创建公共链接
        debug=False,            # 生产环境关闭debug
        show_error=True,        # 显示错误信息
        quiet=False             # 显示启动信息
    )

if __name__ == "__main__":
    main()
