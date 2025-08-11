#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Arxiv论文翻译器 - 主接口

主要功能：
1. 整合所有翻译步骤（step1-step6）
2. 提供一站式arxiv论文翻译服务
3. 从arxiv链接到翻译PDF的完整流程
4. 支持配置参数和错误处理
5. 提供简单易用的API接口

输入：arxiv链接或ID
输出：翻译后的PDF文件

作者：基于GPT Academic项目改进
"""

import os
import sys
import time
import logging
from pathlib import Path
from typing import Tuple, Optional, Dict, Any, List

# 添加当前目录到Python路径
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

# 导入各个步骤的模块
try:
    from step1_arxiv_downloader import ArxivDownloader, download_arxiv_paper
    from step2_latex_parser import LaTeXParser, parse_latex_project
    from step3_content_splitter import LaTeXContentSplitter, split_latex_content
    from step6_translation_manager import TranslationManager, translate_latex_segments
    from step5_result_merger import LaTeXResultMerger, merge_translation_result
    from step8_pdf_compiler import TranslationPDFCompiler, compile_translation_to_pdf
    from config import API_KEY, BASE_URL, LLM_MODEL

except ImportError as e:
    print(f"模块导入失败: {e}")
    print("请确保所有step文件都在同一目录下")
    sys.exit(1)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ArxivTranslator:
    """
    Arxiv论文翻译器主类
    
    主要功能：
    1. 整合完整的翻译流程
    2. 管理各个步骤的协调
    3. 提供进度反馈
    4. 处理错误和异常
    """
    
    def __init__(self, 
                 cache_dir: str = "./arxiv_cache",
                 output_dir: str = "./output", 
                 work_dir: str = "./work",
                 api_key: str = "",
                 base_url: str = "",
                 llm_model: str = "gpt-4o-mini",
                 latex_server_url: str = "http://localhost:9851",
                 max_workers: int = 9,
                 max_token_limit: int = 800,
                 use_cache: bool = True,
                 proxies: dict = None):
        """
        初始化Arxiv翻译器
        
        输入：
        - cache_dir: arxiv缓存目录，如 "./arxiv_cache"
        - output_dir: 输出目录，如 "./output"
        - work_dir: 工作目录，如 "./work"
        - api_key: LLM API密钥
        - base_url: LLM API地址
        - llm_model: LLM模型名称，如 "gpt-4o-mini"
        - latex_server_url: LaTeX编译服务器地址
        - max_workers: 最大并发翻译线程数
        - max_token_limit: 每段最大token限制
        - use_cache: 是否使用缓存
        - proxies: 代理配置
        
        输出：无
        
        这个函数初始化翻译器，设置所有必要的组件和参数
        """
        # 创建必要的目录
        self.cache_dir = Path(cache_dir)
        self.output_dir = Path(output_dir) 
        self.work_dir = Path(work_dir)
        
        for dir_path in [self.cache_dir, self.output_dir, self.work_dir]:
            dir_path.mkdir(exist_ok=True)
        
        # 保存配置参数
        self.api_key = api_key
        self.base_url = base_url
        self.llm_model = llm_model
        self.latex_server_url = latex_server_url
        self.max_workers = max_workers
        self.max_token_limit = max_token_limit
        self.use_cache = use_cache
        self.proxies = proxies or {}
        
        # 初始化各个组件
        self.downloader = ArxivDownloader(
            cache_dir=str(self.cache_dir),
            proxies=self.proxies
        )
        
        self.parser = LaTeXParser(
            work_dir=str(self.work_dir)
        )
        
        self.splitter = LaTeXContentSplitter(
            max_token_limit=self.max_token_limit
        )
        
        self.translator = TranslationManager(
            api_key=self.api_key,
            base_url=self.base_url,
            llm_model=self.llm_model,
            max_workers=self.max_workers
        )
        
        self.merger = LaTeXResultMerger()
        
        self.compiler = TranslationPDFCompiler(
            server_url=self.latex_server_url,
            output_dir=str(self.output_dir),
            keep_tex_files=True
        )
        
        # 翻译统计信息
        self.translation_stats = {
            'start_time': None,
            'end_time': None,
            'arxiv_id': None,
            'source_path': None,  # 新增：保存源码路径
            'total_segments': 0,
            'translated_segments': 0,
            'failed_segments': 0,
            'final_success': False
        }
        
        logger.info(f"Arxiv翻译器初始化完成")
        logger.info(f"LLM模型: {self.llm_model}")
        logger.info(f"最大并发: {self.max_workers}")
        logger.info(f"输出目录: {self.output_dir}")
    
    def translate_arxiv(self, 
                       arxiv_input: str,
                       user_requirements: str = "保持学术性和专业性，确保术语翻译的一致性",
                       user_terms: Dict[str, str] = None,
                       progress_callback = None,
                       compile_pdf: bool = True) -> Tuple[bool, str, Dict[str, Any]]:
        """
        翻译arxiv论文的主函数
        
        输入：
        - arxiv_input: arxiv输入，如 "1812.10695" 或 "https://arxiv.org/abs/1812.10695"
        - user_requirements: 用户翻译要求，如 "保持学术性"
        - user_terms: 用户术语字典，如 {"agent": "智能体"}
        - progress_callback: 进度回调函数，接收 (step, progress, message) 参数
        - compile_pdf: 是否编译PDF，默认True
        
        输出：
        - success: 是否成功（布尔值）
        - result: 成功时返回PDF路径，失败时返回错误信息（字符串）
        - details: 详细信息字典，包含统计和中间结果
        
        这个函数是主要的公共接口，完成从arxiv输入到翻译PDF的完整流程
        """
        print("=" * 80)
        print("🚀 开始Arxiv论文翻译")
        print("=" * 80)
        
        # 初始化统计信息
        self.translation_stats['start_time'] = time.time()
        
        details = {
            'arxiv_id': None,
            'source_path': None,
            'merged_latex': None,
            'segments': [],
            'translations': [],
            'merged_content': None,
            'pdf_path': None,
            'errors': []
        }
        
        try:
            # Step 1: 下载Arxiv论文源码
            print(f"\n📥 Step 1: 下载Arxiv论文源码")
            print(f"输入: {arxiv_input}")
            
            if progress_callback:
                progress_callback(1, 10, "正在下载Arxiv论文...")
            
            success, extract_path, message = self.downloader.download_and_extract(
                arxiv_input, self.use_cache
            )
            
            if not success:
                error_msg = f"Step 1 失败: {message}"
                details['errors'].append(error_msg)
                print(f"❌ {error_msg}")
                return False, error_msg, details
            
            details['source_path'] = extract_path
            self.translation_stats['source_path'] = extract_path  # 保存源码路径到统计信息
            
            # 提取arxiv ID
            parsed_success, arxiv_id, _ = self.downloader.parse_arxiv_input(arxiv_input)
            if parsed_success:
                details['arxiv_id'] = arxiv_id
                self.translation_stats['arxiv_id'] = arxiv_id
            
            print(f"✅ Step 1 完成: {message}")
            print(f"   源码路径: {extract_path}")
            
            # Step 2: 解析和合并LaTeX文件
            print(f"\n📝 Step 2: 解析和合并LaTeX文件")
            
            if progress_callback:
                progress_callback(2, 20, "正在解析LaTeX文件...")
            
            success, merged_content, message = self.parser.parse_and_merge(
                extract_path, add_chinese=True
            )
            
            if not success:
                error_msg = f"Step 2 失败: {message}"
                details['errors'].append(error_msg)
                print(f"❌ {error_msg}")
                return False, error_msg, details
            
            details['merged_latex'] = merged_content
            print(f"✅ Step 2 完成: {message}")
            print(f"   合并后文档长度: {len(merged_content)} 字符")
            
            # Step 3: 智能切分内容
            print(f"\n✂️ Step 3: 智能切分内容")
            
            if progress_callback:
                progress_callback(3, 30, "正在切分文档内容...")
            
            success, segments = split_latex_content(
                merged_content, self.max_token_limit
            )
            
            if not success:
                error_msg = f"Step 3 失败: {segments[0] if segments else '未知错误'}"
                details['errors'].append(error_msg)
                print(f"❌ {error_msg}")
                return False, error_msg, details
            
            details['segments'] = segments
            self.translation_stats['total_segments'] = len(segments)
            
            print(f"✅ Step 3 完成: 切分为 {len(segments)} 个段落")
            
            # Step 4: 批量翻译
            print(f"\n🌍 Step 4: 批量翻译文档")
            
            if progress_callback:
                progress_callback(4, 40, f"正在翻译 {len(segments)} 个段落...")
            
            # 定义进度回调
            def translation_progress_callback(current, total):
                if progress_callback:
                    progress = 40 + (current / total) * 40  # 40%-80%
                    progress_callback(4, progress, f"翻译进度: {current}/{total}")
            
            # 调用翻译，传递arxiv_id以支持缓存
            success, translations, errors = self.translator.translate_segments(
                segments=segments,
                user_requirements=user_requirements,
                user_terms=user_terms,
                progress_callback=translation_progress_callback,
                arxiv_id=details['arxiv_id']  # 传递arxiv_id用于缓存
            )
            
            details['translations'] = translations
            
            if not success:
                error_msg = f"Step 4 失败: 翻译过程出现严重错误"
                details['errors'].extend(errors)
                print(f"❌ {error_msg}")
                return False, error_msg, details
            
            # 统计翻译结果
            successful_translations = sum(1 for i, error in enumerate(errors) if not error)
            failed_translations = len(segments) - successful_translations
            
            self.translation_stats['translated_segments'] = successful_translations
            self.translation_stats['failed_segments'] = failed_translations
            
            print(f"✅ Step 4 完成: 成功翻译 {successful_translations}/{len(segments)} 个段落")
            
            if failed_translations > 0:
                print(f"⚠️  {failed_translations} 个段落翻译失败，将使用原文")
            
            # Step 5: 合并翻译结果
            print(f"\n🔗 Step 5: 合并翻译结果")

            if progress_callback:
                progress_callback(5, 80, "正在合并翻译结果...")

            success, merged_content, message = self.merger.merge_translated_segments(
                translated_segments=translations,
                original_segments=segments,
                original_full_content=details['merged_latex'],  # 传递完整原文
                llm_model=self.llm_model,
                temperature=0.3
            )
            
            if not success:
                error_msg = f"Step 5 失败: {message}"
                details['errors'].append(error_msg)
                print(f"❌ {error_msg}")
                return False, error_msg, details
            
            details['merged_content'] = merged_content
            print(f"✅ Step 5 完成: {message}")
            
            # 保存翻译后的tex文件
            if details['arxiv_id']:
                tex_filename = f"arxiv_{details['arxiv_id']}_translated.tex"
            else:
                tex_filename = f"translated_{time.strftime('%Y%m%d_%H%M%S')}.tex"
            
            tex_path = self.output_dir / tex_filename
            self.merger.save_merged_content(merged_content, str(tex_path))
            print(f"   翻译后tex文件已保存: {tex_path}")
            
            # Step 6: 编译PDF（可选）
            if compile_pdf:
                print(f"\n📄 Step 6: 编译PDF文档")
                
                if progress_callback:
                    progress_callback(6, 90, "正在编译PDF...")
                
                # 关键修改：传递源码目录路径
                success, pdf_result, message = self.compiler.compile_translated_latex(
                    latex_content=merged_content,
                    output_name="translated",
                    arxiv_id=details['arxiv_id'],
                    source_dir=details['source_path']  # 传递源码目录，确保能找到依赖文件
                )
                
                if success:
                    details['pdf_path'] = pdf_result
                    print(f"✅ Step 6 完成: PDF编译成功")
                    print(f"   PDF文件路径: {pdf_result}")
                    final_result = pdf_result
                    final_message = f"翻译完成！PDF保存至: {pdf_result}"
                else:
                    print(f"⚠️  Step 6 PDF编译失败: {pdf_result}")
                    print(f"   翻译的tex文件仍可用: {tex_path}")
                    final_result = str(tex_path)
                    final_message = f"翻译完成，但PDF编译失败。tex文件保存至: {tex_path}\n编译错误: {pdf_result}"
            else:
                print(f"\n⏭️  跳过PDF编译")
                final_result = str(tex_path)
                final_message = f"翻译完成！tex文件保存至: {tex_path}"
            
            # 更新最终统计
            self.translation_stats['end_time'] = time.time()
            self.translation_stats['final_success'] = True
            
            duration = self.translation_stats['end_time'] - self.translation_stats['start_time']
            
            print(f"\n📊 翻译统计:")
            print(f"   总耗时: {duration:.2f} 秒")
            print(f"   成功段落: {self.translation_stats['translated_segments']}")
            print(f"   失败段落: {self.translation_stats['failed_segments']}")
            print(f"   源码路径: {self.translation_stats['source_path']}")
            
            if progress_callback:
                progress_callback(6, 100, "翻译完成！")
            
            print("=" * 80)
            print("🎉 Arxiv论文翻译完成")
            print("=" * 80)
            
            return True, final_result, details
            
        except Exception as e:
            error_msg = f"翻译过程出现异常: {e}"
            logger.error(error_msg)
            details['errors'].append(error_msg)
            print(f"❌ {error_msg}")
            
            self.translation_stats['end_time'] = time.time()
            self.translation_stats['final_success'] = False
            
            import traceback
            traceback.print_exc()
            
            return False, error_msg, details
    
    def get_translation_stats(self) -> Dict[str, Any]:
        """
        获取翻译统计信息
        
        输入：无
        输出：统计信息字典
        
        这个函数返回详细的翻译统计信息
        """
        stats = self.translation_stats.copy()
        
        if stats['start_time'] and stats['end_time']:
            stats['duration'] = stats['end_time'] - stats['start_time']
            stats['duration_str'] = f"{stats['duration']:.2f} 秒"
        
        if stats['total_segments'] > 0:
            stats['success_rate'] = f"{(stats['translated_segments']/stats['total_segments']*100):.1f}%"
        else:
            stats['success_rate'] = "0.0%"
        
        return stats

def translate_arxiv_paper(arxiv_input: str,
                         user_requirements: str = "保持学术性和专业性，确保术语翻译的一致性",
                         user_terms: Dict[str, str] = None,
                         output_dir: str = "./output",
                         api_key: str = "",
                         base_url: str = "",
                         llm_model: str = "",
                         compile_pdf: bool = True) -> Tuple[bool, str]:
    """
    便捷函数：翻译arxiv论文（改进版，支持依赖文件）
    
    输入：
    - arxiv_input: arxiv输入，如 "1812.10695" 或完整URL
    - user_requirements: 用户翻译要求
    - user_terms: 用户术语字典
    - output_dir: 输出目录
    - api_key: LLM API密钥
    - base_url: LLM API地址
    - compile_pdf: 是否编译PDF
    
    输出：
    - success: 是否成功（布尔值）
    - result: 成功时返回文件路径，失败时返回错误信息（字符串）
    
    这个函数提供最简单的调用方式，一步完成arxiv论文翻译，并确保依赖文件正确处理
    """
    try:
        translator = ArxivTranslator(
            output_dir=output_dir,
            api_key=api_key,
            base_url=base_url,
            llm_model=llm_model
        )
        
        success, result, details = translator.translate_arxiv(
            arxiv_input=arxiv_input,
            user_requirements=user_requirements,
            user_terms=user_terms,
            compile_pdf=compile_pdf
        )
        
        if success:
            return True, result
        else:
            return False, f"翻译失败: {result}"
            
    except Exception as e:
        error_msg = f"翻译过程出错: {e}"
        logger.error(error_msg)
        return False, error_msg

# 测试和示例代码
def main():
    """
    主函数，演示Arxiv翻译器的使用方法
    """
    print("=" * 70)
    print("Arxiv论文翻译器测试（改进版）")
    print("=" * 70)
    
    # 测试用例
    test_cases = [
        {
            "name": "经典机器学习论文",
            "arxiv_id": "1812.10695",
            "description": "GPT-1 原始论文"
        },
        {
            "name": "最新论文",
            "arxiv_id": "2402.14207", 
            "description": "最新发表论文"
        }
    ]
    
    print("可选测试用例:")
    for i, case in enumerate(test_cases, 1):
        print(f"  {i}. {case['name']} ({case['arxiv_id']}) - {case['description']}")
    
    # 让用户选择测试用例或输入自定义ID
    print(f"\n请选择测试用例 (1-{len(test_cases)}) 或直接输入arxiv ID:")
    try:
        user_input = input("> ").strip()
        
        if user_input.isdigit() and 1 <= int(user_input) <= len(test_cases):
            selected_case = test_cases[int(user_input) - 1]
            test_arxiv_id = selected_case["arxiv_id"]
            print(f"选择了: {selected_case['name']}")
        else:
            test_arxiv_id = user_input
            print(f"使用自定义输入: {test_arxiv_id}")
            
    except KeyboardInterrupt:
        print("\n用户中断，使用默认测试用例")
        test_arxiv_id = test_cases[0]["arxiv_id"]
    except:
        print("输入无效，使用默认测试用例") 
        test_arxiv_id = test_cases[0]["arxiv_id"]
    
    # # 自定义翻译要求和术语
    # user_requirements = "翻译要保持学术性和专业性，确保术语翻译的一致性，对于专业术语首次出现时用括号标注英文原词"
    
    # user_terms = {
    #     "transformer": "变换器",
    #     "attention": "注意力", 
    #     "neural network": "神经网络",
    #     "machine learning": "机器学习",
    #     "deep learning": "深度学习",
    #     "artificial intelligence": "人工智能"
    # }
    
    # print(f"\n自定义配置:")
    # print(f"翻译要求: {user_requirements}")
    # print(f"术语词典: {len(user_terms)} 条")
    
    # # 定义进度回调函数
    # def progress_callback(step, progress, message):
    #     print(f"Step {step} - {progress:.1f}%: {message}")
    
    # # 创建翻译器
    # print(f"\n创建Arxiv翻译器...")
    # translator = ArxivTranslator(
    #     output_dir="./output",
    #     cache_dir="./arxiv_cache",
    #     work_dir="./work"
    # )
    
    # # 执行翻译
    # print(f"\n开始翻译 {test_arxiv_id}...")
    # success, result, details = translator.translate_arxiv(
    #     arxiv_input=test_arxiv_id,
    #     user_requirements=user_requirements,
    #     user_terms=user_terms,
    #     progress_callback=progress_callback,
    #     compile_pdf=True  # 尝试编译PDF，现在应该能找到依赖文件了
    # )
    
    # # 输出结果
    # print(f"\n{'='*50}")
    # print("翻译结果")
    # print(f"{'='*50}")
    
    # if success:
    #     print(f"✅ 翻译成功！")
    #     print(f"结果文件: {result}")
        
    #     # 显示详细信息
    #     if details['arxiv_id']:
    #         print(f"Arxiv ID: {details['arxiv_id']}")
    #     if details['source_path']:
    #         print(f"源码路径: {details['source_path']}")
    #     print(f"切分段落数: {len(details.get('segments', []))}")
    #     print(f"翻译段落数: {len(details.get('translations', []))}")
        
    #     # 显示统计信息
    #     stats = translator.get_translation_stats()
    #     print(f"\n翻译统计:")
    #     for key, value in stats.items():
    #         if key not in ['start_time', 'end_time']:
    #             print(f"  {key}: {value}")
                
    # else:
    #     print(f"❌ 翻译失败")
    #     print(f"错误信息: {result}")
        
    #     if details['errors']:
    #         print(f"\n详细错误:")
    #         for error in details['errors']:
    #             print(f"  - {error}")
    
    # 测试便捷函数
    print(f"\n{'='*50}")
    print("测试便捷函数接口")
    print(f"{'='*50}")
    
    # 只测试tex生成，跳过PDF编译避免重复
    success, result = translate_arxiv_paper(
        arxiv_input=test_arxiv_id,
        output_dir="./output",
        compile_pdf=True,  # 跳过PDF编译，避免重复测试
        api_key=API_KEY,
        base_url=BASE_URL,
        llm_model=LLM_MODEL
    )
    
    if success:
        print(f"✅ 便捷函数测试成功")
        print(f"结果: {result}")
    else:
        print(f"❌ 便捷函数测试失败")
        print(f"错误: {result}")
    
    print(f"\n{'='*70}")
    print("Arxiv翻译器测试完成")
    print(f"{'='*70}")

if __name__ == "__main__":
    main()
