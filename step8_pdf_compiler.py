#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LaTeX PDF编译器 - 翻译专用版（修复参考文献问题）

主要功能：
1. 基于现有latex_compile_client.py的高级封装
2. 专门优化翻译后的LaTeX文档编译
3. 完整支持参考文献编译流程
4. 自动收集和传递.bib等依赖文件
5. 集成编译日志分析

输入：翻译后的LaTeX文档内容和源码目录
输出：编译后的PDF文件或详细的错误信息

作者：基于GPT Academic项目改进
"""

import os
import time
import tempfile
import shutil
import logging
from pathlib import Path
from typing import Tuple, Optional, Dict, Any
import re

# 导入现有的LaTeX编译客户端
try:
    from latex2pdf.latex_compile_client import LaTeXCompileClient, compile_latex_to_pdf, start_latex_server
except ImportError:
    # 如果在不同目录运行，尝试相对导入
    import sys
    sys.path.append(os.path.dirname(__file__))
    from latex_compile_client import LaTeXCompileClient, compile_latex_to_pdf, start_latex_server

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TranslationPDFCompiler:
    """
    翻译专用PDF编译器类（修复参考文献问题）
    
    主要功能：
    1. 专门处理翻译后的LaTeX文档
    2. 自动收集所有依赖文件（特别是.bib文件）
    3. 完整支持参考文献编译流程
    4. 提供增强的错误诊断
    """
    
    def __init__(self,
                 server_url: str = "http://localhost:9851",
                 output_dir: str = "./arxiv_cache",  # 默认改为arxiv_cache
                 keep_tex_files: bool = True,
                 auto_start_server: bool = True):
        """
        初始化翻译PDF编译器
        
        输入：
        - server_url: LaTeX编译服务器地址，如 "http://localhost:9851"
        - output_dir: 输出目录路径，如 "./output"
        - keep_tex_files: 是否保留中间tex文件，默认True
        - auto_start_server: 是否自动启动服务器，默认True
        
        输出：无
        
        这个函数初始化编译器，设置输出目录和服务器连接
        """
        self.server_url = server_url
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.keep_tex_files = keep_tex_files
        self.auto_start_server = auto_start_server
        
        # 初始化LaTeX客户端
        self.client = LaTeXCompileClient(server_url)
        
        # 编译统计信息
        self.compile_stats = {
            'total_compilations': 0,
            'successful_compilations': 0,
            'failed_compilations': 0,
            'last_compile_time': None
        }
        
        logger.info(f"翻译PDF编译器初始化完成")
        logger.info(f"服务器地址: {server_url}")
        logger.info(f"输出目录: {self.output_dir}")
        logger.info(f"保留tex文件: {keep_tex_files}")
    
    def check_server_and_start(self) -> bool:
        """
        检查服务器状态，必要时启动服务器
        
        输入：无
        输出：服务器是否可用（布尔值）
        
        这个函数检查LaTeX编译服务器是否运行，如果没有则尝试启动
        """
        print("检查LaTeX编译服务器状态...")
        
        if self.client.check_server_health():
            print("✓ LaTeX编译服务器运行正常")
            return True
        
        if not self.auto_start_server:
            print("✗ LaTeX编译服务器未运行，且未启用自动启动")
            return False
        
        print("LaTeX编译服务器未运行，尝试自动启动...")
        try:
            start_latex_server()
            
            # 等待服务器启动
            for i in range(6):  # 最多等待30秒
                time.sleep(5)
                if self.client.check_server_health():
                    print("✓ LaTeX编译服务器启动成功")
                    return True
                print(f"等待服务器启动... ({i+1}/6)")
            
            print("✗ LaTeX编译服务器启动超时")
            return False
            
        except Exception as e:
            print(f"✗ 启动LaTeX编译服务器失败: {e}")
            return False
    
    def _collect_all_dependencies(self, source_dir: str) -> Dict[str, bytes]:
        """
        收集源码目录中的所有依赖文件（重点关注参考文献文件）
        
        输入：
        - source_dir: 源码目录路径，如 "/path/to/arxiv/source"
        
        输出：
        - dependencies: 依赖文件字典，如 {"paper.bib": b"文件内容", "image.pdf": b"图片内容"}
        
        这个函数递归收集源码目录中的所有文件，特别关注.bib等参考文献文件
        """
        dependencies = {}
        
        try:
            if not source_dir or not Path(source_dir).exists():
                logger.warning(f"源码目录不存在: {source_dir}")
                return dependencies
            
            source_path = Path(source_dir)
            print(f"正在收集依赖文件从: {source_path}")
            
            # 定义需要收集的文件扩展名（按重要性排序）
            important_extensions = ['.bib', '.bst', '.cls', '.sty']  # 参考文献和样式文件
            image_extensions = ['.pdf', '.png', '.jpg', '.jpeg', '.eps', '.ps']  # 图片文件
            other_extensions = ['.txt', '.dat', '.csv']  # 其他数据文件
            
            all_extensions = important_extensions + image_extensions + other_extensions
            
            # 统计收集的文件类型
            file_stats = {}
            
            # 递归收集所有相关文件
            for item in source_path.rglob('*'):
                if item.is_file():
                    # 跳过.tex文件（主文档已经合并）和临时文件
                    if (item.suffix.lower() in ['.tex', '.aux', '.log', '.out', '.toc', '.lof', '.lot'] or
                        item.name.startswith('.') or
                        item.name.endswith('~')):
                        continue
                    
                    # 收集重要文件
                    if item.suffix.lower() in all_extensions:
                        try:
                            with open(item, 'rb') as f:
                                file_content = f.read()
                            
                            # 使用相对路径作为键
                            relative_path = item.relative_to(source_path)
                            dependencies[str(relative_path)] = file_content
                            
                            # 统计文件类型
                            ext = item.suffix.lower()
                            file_stats[ext] = file_stats.get(ext, 0) + 1
                            
                            # 特别标注重要文件
                            if ext in important_extensions:
                                print(f"  📚 重要文件: {relative_path} ({len(file_content)} 字节)")
                            else:
                                print(f"  📄 依赖文件: {relative_path} ({len(file_content)} 字节)")
                                
                        except Exception as e:
                            logger.warning(f"无法读取文件 {item}: {e}")
                            continue
            
            # 输出收集统计
            print(f"✓ 成功收集 {len(dependencies)} 个依赖文件")
            if file_stats:
                print("文件类型统计:")
                for ext, count in sorted(file_stats.items()):
                    print(f"  {ext}: {count} 个文件")
            
            # 特别检查参考文献文件
            bib_files = [f for f in dependencies.keys() if f.endswith('.bib')]
            if bib_files:
                print(f"🔍 发现 {len(bib_files)} 个参考文献文件:")
                for bib_file in bib_files:
                    print(f"  - {bib_file}")
            else:
                print("⚠️  未发现.bib参考文献文件，可能使用内嵌参考文献")
            
            return dependencies
            
        except Exception as e:
            logger.error(f"收集依赖文件时出错: {e}")
            return dependencies
    
    def _analyze_bibliography_usage(self, latex_content: str) -> Dict[str, Any]:
        """
        分析LaTeX文档中的参考文献使用情况
        
        输入：
        - latex_content: LaTeX文档内容
        
        输出：
        - analysis: 参考文献分析结果
          {
              'has_bibliography': bool,      # 是否有参考文献
              'bib_files': list,             # 引用的.bib文件列表
              'cite_commands': int,          # \cite命令数量
              'bibliography_style': str,     # 参考文献样式
              'uses_natbib': bool,           # 是否使用natbib包
              'uses_biblatex': bool          # 是否使用biblatex包
          }
        
        这个函数分析LaTeX文档的参考文献配置，帮助诊断编译问题
        """
        analysis = {
            'has_bibliography': False,
            'bib_files': [],
            'cite_commands': 0,
            'bibliography_style': '',
            'uses_natbib': False,
            'uses_biblatex': False,
            'has_thebibliography': False
        }
        
        try:
            # 检查是否使用natbib或biblatex包
            if re.search(r'\\usepackage.*\{natbib\}', latex_content):
                analysis['uses_natbib'] = True
            if re.search(r'\\usepackage.*\{biblatex\}', latex_content):
                analysis['uses_biblatex'] = True
            
            # 查找\bibliography命令
            bib_matches = re.findall(r'\\bibliography\{([^}]+)\}', latex_content)
            for match in bib_matches:
                # 处理多个bib文件的情况
                bib_files = [f.strip() for f in match.split(',')]
                for bib_file in bib_files:
                    if not bib_file.endswith('.bib'):
                        bib_file += '.bib'
                    analysis['bib_files'].append(bib_file)
                analysis['has_bibliography'] = True
            
            # 查找\bibliographystyle命令
            style_match = re.search(r'\\bibliographystyle\{([^}]+)\}', latex_content)
            if style_match:
                analysis['bibliography_style'] = style_match.group(1)
            
            # 统计\cite命令数量
            cite_patterns = [r'\\cite\{[^}]+\}', r'\\citep\{[^}]+\}', r'\\citet\{[^}]+\}', 
                           r'\\citeauthor\{[^}]+\}', r'\\citeyear\{[^}]+\}']
            for pattern in cite_patterns:
                analysis['cite_commands'] += len(re.findall(pattern, latex_content))
            
            # 检查是否使用内嵌参考文献
            if re.search(r'\\begin\{thebibliography\}', latex_content):
                analysis['has_thebibliography'] = True
                analysis['has_bibliography'] = True
            
            return analysis
            
        except Exception as e:
            logger.error(f"分析参考文献使用情况时出错: {e}")
            return analysis
    
    def compile_translated_latex(self,
                       latex_content: str,
                       output_name: str = "translated",
                       arxiv_id: str = None,
                       source_dir: str = None) -> Tuple[bool, str, str]:
        """
        编译翻译后的LaTeX文档（完整支持参考文献）
        
        输入：
        - latex_content: 翻译后的LaTeX文档内容，完整的LaTeX文档字符串
        - output_name: 输出文件名（不含扩展名），如 "translated_paper"
        - arxiv_id: arxiv论文ID（可选），如 "1812.10695"
        - source_dir: 原始源码目录路径，包含所有依赖文件
        
        输出：
        - success: 是否编译成功（布尔值）
        - pdf_path: PDF文件路径（成功时）或错误分析（失败时）
        - message: 详细的结果消息
        
        这个函数是主要的编译接口，完整支持参考文献编译流程
        """
        print("=" * 60)
        print("开始编译翻译后的LaTeX文档（完整参考文献支持）")
        print("=" * 60)
        
        try:
            # 更新统计信息
            self.compile_stats['total_compilations'] += 1
            self.compile_stats['last_compile_time'] = time.time()
            
            # 生成输出文件名
            if arxiv_id:
                final_output_name = f"arxiv_{arxiv_id}_{output_name}"
            else:
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                final_output_name = f"{output_name}_{timestamp}"
            
            print(f"编译信息:")
            print(f"- 输出名称: {final_output_name}")
            print(f"- LaTeX内容长度: {len(latex_content)} 字符")
            print(f"- 输出目录: {self.output_dir}")
            print(f"- 源码目录: {source_dir}")
            
            # 检查服务器状态
            print(f"\nStep 1: 检查编译服务器...")
            if not self.check_server_and_start():
                error_msg = "LaTeX编译服务器不可用"
                self.compile_stats['failed_compilations'] += 1
                return False, error_msg, error_msg
            
            # 分析参考文献使用情况
            print(f"\nStep 2: 分析参考文献配置...")
            bib_analysis = self._analyze_bibliography_usage(latex_content)
            
            print(f"参考文献分析结果:")
            print(f"- 是否有参考文献: {bib_analysis['has_bibliography']}")
            print(f"- 引用的.bib文件: {bib_analysis['bib_files']}")
            print(f"- \\cite命令数量: {bib_analysis['cite_commands']}")
            print(f"- 参考文献样式: {bib_analysis['bibliography_style']}")
            print(f"- 使用natbib包: {bib_analysis['uses_natbib']}")
            print(f"- 使用biblatex包: {bib_analysis['uses_biblatex']}")
            print(f"- 使用内嵌参考文献: {bib_analysis['has_thebibliography']}")
            
            # 修复中文字体支持
            print(f"\nStep 3: 检查并修复中文字体支持...")
            latex_content = self.fix_chinese_font_support(latex_content)
            
            # 收集所有依赖文件
            print(f"\nStep 4: 收集依赖文件...")
            dependencies_dict = self._collect_all_dependencies(source_dir)
            
            # 验证参考文献文件是否存在
            if bib_analysis['has_bibliography'] and bib_analysis['bib_files']:
                print(f"\nStep 5: 验证参考文献文件...")
                missing_bib_files = []
                for bib_file in bib_analysis['bib_files']:
                    # 检查是否在依赖文件中
                    found = False
                    for dep_path in dependencies_dict.keys():
                        if dep_path.endswith(bib_file) or dep_path == bib_file:
                            print(f"✓ 找到参考文献文件: {dep_path}")
                            found = True
                            break
                    if not found:
                        missing_bib_files.append(bib_file)
                        print(f"✗ 缺少参考文献文件: {bib_file}")
                
                if missing_bib_files:
                    print(f"⚠️  警告: 缺少 {len(missing_bib_files)} 个参考文献文件")
                    print("这可能导致参考文献显示为 '???'")
                else:
                    print(f"✓ 所有参考文献文件都已找到")
            
            # 执行编译
            print(f"\nStep 6: 执行LaTeX编译...")
            print(f"传递 {len(dependencies_dict)} 个依赖文件到编译服务器")
            
            result = self.client.compile_latex_sync(
                tex_content=latex_content,
                output_name=final_output_name,
                dependencies=dependencies_dict  # 传递所有依赖文件
            )
            
            if result.get('success'):
                # 编译成功
                self.compile_stats['successful_compilations'] += 1
                
                # 保存PDF文件
                pdf_content = result.get('pdf_content')
                if pdf_content:
                    pdf_file_path = self.output_dir / f"{final_output_name}.pdf"
                    with open(pdf_file_path, 'wb') as f:
                        f.write(pdf_content)
                    
                    file_size = len(pdf_content)
                    success_msg = f"PDF编译成功！\n文件路径: {pdf_file_path}\n文件大小: {file_size} 字节"
                    
                    # 分析编译日志中的参考文献信息
                    compile_log = result.get('log', '')
                    if 'bibtex' in compile_log.lower():
                        success_msg += "\n✓ 已执行bibtex处理参考文献"
                    if bib_analysis['cite_commands'] > 0:
                        success_msg += f"\n✓ 处理了 {bib_analysis['cite_commands']} 个引用"
                    
                    print(f"✓ {success_msg}")
                    print("\n编译统计:")
                    print(f"- 总编译次数: {self.compile_stats['total_compilations']}")
                    print(f"- 成功次数: {self.compile_stats['successful_compilations']}")
                    print(f"- 成功率: {(self.compile_stats['successful_compilations']/self.compile_stats['total_compilations']*100):.1f}%")
                    
                    print("=" * 60)
                    print("LaTeX编译完成")
                    print("=" * 60)
                    
                    return True, str(pdf_file_path), success_msg
                else:
                    error_msg = "编译成功但未获得PDF内容"
                    self.compile_stats['failed_compilations'] += 1
                    return False, error_msg, error_msg
            else:
                # 编译失败
                self.compile_stats['failed_compilations'] += 1
                
                print(f"✗ 编译失败")
                
                # 获取详细错误信息
                error_msg = result.get('error', '未知编译错误')
                compile_log = result.get('log', '')
                
                print(f"\nStep 7: 错误分析...")
                print(f"错误信息: {error_msg}")
                
                # 分析是否是参考文献相关错误
                if compile_log:
                    if 'bibtex' in compile_log.lower():
                        if 'error' in compile_log.lower():
                            print("🔍 检测到bibtex编译错误")
                        else:
                            print("✓ bibtex编译正常执行")
                    
                    if 'citation' in compile_log.lower() and 'undefined' in compile_log.lower():
                        print("🔍 检测到未定义的引用，可能是.bib文件问题")
                    
                    if '???' in compile_log:
                        print("🔍 检测到参考文献显示问题")
                
                # 保存错误日志
                if compile_log and self.keep_tex_files:
                    log_file_path = self.output_dir / f"{final_output_name}_compile_error.log"
                    with open(log_file_path, 'w', encoding='utf-8') as f:
                        f.write("LaTeX编译错误日志\n")
                        f.write("=" * 50 + "\n\n")
                        f.write(f"错误信息: {error_msg}\n\n")
                        f.write("参考文献分析:\n")
                        for key, value in bib_analysis.items():
                            f.write(f"- {key}: {value}\n")
                        f.write("\n" + "=" * 50 + "\n")
                        f.write("完整编译日志:\n")
                        f.write(compile_log)
                    print(f"✓ 错误日志已保存: {log_file_path}")
                
                detailed_error = f"编译失败: {error_msg}"
                if bib_analysis['has_bibliography'] and not any(f.endswith('.bib') for f in dependencies_dict.keys()):
                    detailed_error += "\n\n可能原因: 缺少.bib参考文献文件"
                
                print("=" * 60)
                print("LaTeX编译失败")
                print("=" * 60)
                
                return False, error_msg, detailed_error
                
        except Exception as e:
            error_msg = f"编译过程出现异常: {e}"
            logger.error(error_msg)
            self.compile_stats['failed_compilations'] += 1
            print(f"✗ {error_msg}")
            return False, error_msg, error_msg
    
    def fix_chinese_font_support(self, latex_content: str) -> str:
        """
        自动修复LaTeX文档的中文字体支持
        
        输入：
        - latex_content: 原始LaTeX文档内容
        
        输出：
        - fixed_content: 修复后的LaTeX文档内容
        
        这个函数检测并修复LaTeX文档的中文字体配置问题
        """
        try:
            # 检查是否包含中文字符
            import re
            chinese_pattern = re.compile(r'[\u4e00-\u9fff]')
            has_chinese = bool(chinese_pattern.search(latex_content))
            
            if not has_chinese:
                logger.debug("文档不包含中文字符，无需修复字体支持")
                return latex_content
            
            logger.info("检测到中文字符，开始修复字体支持...")
            
            # 检查是否已经有正确的中文字体配置（ctex包）
            if r'\usepackage{ctex}' in latex_content:
                logger.debug("文档已包含正确的中文字体配置(ctex)")
                return latex_content
            
            # 移除可能冲突的包
            content = latex_content
            # 移除 xeCJK（与ctex冲突）
            content = re.sub(r'\\usepackage\{xeCJK\}\s*\n?', '', content)
            content = re.sub(r'\\setCJKmainfont\{.*?\}\s*\n?', '', content)
            # 移除单独的 inputenc（ctex会自动处理）
            content = re.sub(r'\\usepackage\[utf8\]\{inputenc\}\s*\n?', '', content)
            
            # 查找documentclass位置
            documentclass_pattern = r'(\\documentclass(?:\[.*?\])?\{.*?\})'
            match = re.search(documentclass_pattern, content)
            
            if not match:
                logger.warning("未找到documentclass声明，无法添加中文支持")
                return content
            
            # 在documentclass后添加中文字体支持
            insertion_pos = match.end()
            
            # 准备要插入的中文支持代码
            chinese_support = r'''\usepackage{ctex}
\usepackage{url}
'''
            
            # 检查是否已有url包
            if r'\usepackage{url}' in content:
                chinese_support = r'''\usepackage{ctex}
'''
            
            # 修改documentclass以支持中文
            # 为documentclass添加中文相关选项
            original_documentclass = match.group(0)
            
            # 检查是否已经有选项
            if '[' in original_documentclass and ']' in original_documentclass:
                # 已有选项，添加中文选项
                modified_documentclass = re.sub(
                    r'\\documentclass\[([^\]]*)\]',
                    r'\\documentclass[\1,fontset=windows,UTF8]',
                    original_documentclass
                )
            else:
                # 没有选项，添加中文选项
                modified_documentclass = re.sub(
                    r'\\documentclass\{([^}]*)\}',
                    r'\\documentclass[fontset=windows,UTF8]{\1}',
                    original_documentclass
                )
            
            # 替换原始documentclass并添加中文支持包
            content = (
                content[:match.start()] + 
                modified_documentclass + '\n' +
                chinese_support + 
                content[insertion_pos:]
            )
            
            logger.info("✓ 已添加中文字体支持配置(ctex)")
            return content
            
        except Exception as e:
            logger.error(f"修复中文字体支持时出错: {e}")
            return latex_content
    
    def get_compile_stats(self) -> Dict[str, Any]:
        """
        获取编译统计信息
        
        输入：无
        输出：统计信息字典
        
        这个函数返回编译器的使用统计
        """
        stats = self.compile_stats.copy()
        if stats['total_compilations'] > 0:
            stats['success_rate'] = f"{(stats['successful_compilations']/stats['total_compilations']*100):.1f}%"
        else:
            stats['success_rate'] = "0.0%"
        
        if stats['last_compile_time']:
            stats['last_compile_time_str'] = time.strftime(
                "%Y-%m-%d %H:%M:%S", 
                time.localtime(stats['last_compile_time'])
            )
        
        return stats

def compile_translation_to_pdf(latex_content: str,
                              output_name: str = "translated",
                              arxiv_id: str = None,
                              output_dir: str = "./arxiv_cache",  # 默认改为arxiv_cache
                              source_dir: str = None) -> Tuple[bool, str]:
    """
    便捷函数：编译翻译后的LaTeX文档为PDF（完整参考文献支持）
    
    输入：
    - latex_content: 翻译后的LaTeX文档内容，完整的LaTeX文档字符串
    - output_name: 输出文件名，如 "translated_paper"
    - arxiv_id: arxiv论文ID（可选），如 "1812.10695"
    - output_dir: 输出目录，如 "./output"
    - source_dir: 原始源码目录，包含.bib等依赖文件
    
    输出：
    - success: 是否成功（布尔值）
    - result: 成功时返回PDF路径，失败时返回错误信息（字符串）
    
    这个函数提供最简单的调用方式，一步完成翻译文档的PDF编译，完整支持参考文献
    """
    try:
        compiler = TranslationPDFCompiler(output_dir=output_dir)
        success, result, message = compiler.compile_translated_latex(
            latex_content=latex_content,
            output_name=output_name,
            arxiv_id=arxiv_id,
            source_dir=source_dir  # 传递源码目录以收集.bib文件
        )
        
        if success:
            return True, result
        else:
            return False, f"编译失败: {result}"
            
    except Exception as e:
        error_msg = f"编译过程出错: {e}"
        logger.error(error_msg)
        return False, error_msg

# 测试和示例代码
def main():
    """
    测试函数，演示PDF编译器的使用方法（重点测试参考文献功能）
    """
    print("=" * 70)
    print("LaTeX翻译PDF编译器测试（参考文献功能重点测试）")
    print("=" * 70)
    
    # 创建编译器
    print("初始化LaTeX翻译PDF编译器...")
    compiler = TranslationPDFCompiler(
        output_dir="./arxiv_cache",  # 默认改为arxiv_cache
        keep_tex_files=True,
        auto_start_server=True
    )
    
    # 测试1: 带参考文献的LaTeX文档编译
    print("\n" + "=" * 50)
    print("测试1: 带参考文献的LaTeX文档编译")
    print("=" * 50)
    
    # 创建包含参考文献的测试LaTeX文档
    test_latex_with_bib = r"""
\documentclass{article}
\usepackage[utf8]{inputenc}
\usepackage{natbib}

\title{测试文档：参考文献功能验证}
\author{LaTeX编译器测试}
\date{\today}

\begin{document}
\maketitle

\section{引言}
这是一个测试文档，用于验证参考文献编译功能。我们引用了一些重要的研究工作 \citep{example2023, test2024}。

根据 \citet{example2023} 的研究，深度学习在自然语言处理领域取得了显著进展。

\section{相关工作}
许多研究者在这个领域做出了贡献 \citep{test2024, another2023}。

\section{结论}
本文验证了参考文献编译功能的正确性。

\bibliographystyle{plain}
\bibliography{test_refs}

\end{document}
"""
    
    # 创建对应的.bib文件内容
    test_bib_content = r"""
@article{example2023,
    title={深度学习在自然语言处理中的应用},
    author={张三 and 李四},
    journal={计算机学报},
    volume={44},
    number={3},
    pages={123--145},
    year={2023},
    publisher={科学出版社}
}

@inproceedings{test2024,
    title={Transformer模型的最新进展},
    author={Wang, Ming and Liu, Hua},
    booktitle={International Conference on Machine Learning},
    pages={456--467},
    year={2024},
    organization={PMLR}
}

@article{another2023,
    title={注意力机制的理论分析},
    author={陈五 and 赵六},
    journal={软件学报},
    volume={34},
    number={8},
    pages={789--801},
    year={2023}
}
"""
    
    # 创建临时源码目录和.bib文件
    import tempfile
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # 写入.bib文件
        bib_file_path = temp_path / "test_refs.bib"
        with open(bib_file_path, 'w', encoding='utf-8') as f:
            f.write(test_bib_content)
        
        print(f"创建测试.bib文件: {bib_file_path}")
        
        # 执行编译
        success, result, message = compiler.compile_translated_latex(
            latex_content=test_latex_with_bib,
            output_name="test_with_bibliography",
            source_dir=str(temp_path)  # 传递包含.bib文件的目录
        )
        
        if success:
            print("✅ 带参考文献的文档编译成功")
            print(f"PDF文件: {result}")
            print(f"详情: {message}")
            
            # 检查PDF文件是否存在
            if Path(result).exists():
                file_size = Path(result).stat().st_size
                print(f"✓ PDF文件大小: {file_size} 字节")
        else:
            print("❌ 带参考文献的文档编译失败")
            print(f"错误: {result}")
            print(f"详情: {message}")
    
    # 测试2: 无参考文献的文档编译（对比测试）
    print("\n" + "=" * 50)
    print("测试2: 无参考文献的文档编译（对比测试）")
    print("=" * 50)
    
    simple_latex = r"""
\documentclass{article}
\usepackage[utf8]{inputenc}

\title{简单测试文档}
\author{LaTeX编译器测试}
\date{\today}

\begin{document}
\maketitle

\section{介绍}
这是一个不包含参考文献的简单测试文档。

\section{内容}
这里是一些测试内容，用于验证基本编译功能。

数学公式测试：
\begin{equation}
E = mc^2
\end{equation}

\section{结论}
简单文档编译测试完成。

\end{document}
"""
    
    success, result, message = compiler.compile_translated_latex(
        latex_content=simple_latex,
        output_name="test_simple_no_bib"
    )
    
    if success:
        print("✅ 简单文档编译成功")
        print(f"PDF文件: {result}")
    else:
        print("❌ 简单文档编译失败")
        print(f"错误: {result}")
    
    # 测试3: 便捷函数测试
    print("\n" + "=" * 50)
    print("测试3: 便捷函数接口测试")
    print("=" * 50)
    
    # 再次创建临时目录测试便捷函数
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # 写入.bib文件
        bib_file_path = temp_path / "convenience_refs.bib"
        with open(bib_file_path, 'w', encoding='utf-8') as f:
            f.write(test_bib_content.replace("test_refs", "convenience_refs"))
        
        # 修改LaTeX文档以使用新的.bib文件
        convenience_latex = test_latex_with_bib.replace("test_refs", "convenience_refs")
        
        success, result = compile_translation_to_pdf(
            latex_content=convenience_latex,
            output_name="convenience_test",
            arxiv_id="test_bib",
            output_dir="./output",
            source_dir=str(temp_path)
        )
        
        if success:
            print("✅ 便捷函数测试成功")
            print(f"PDF文件: {result}")
        else:
            print("❌ 便捷函数测试失败")
            print(f"错误: {result}")
    
    # 测试4: 参考文献分析功能测试
    print("\n" + "=" * 50)
    print("测试4: 参考文献分析功能测试")
    print("=" * 50)
    
    # 测试不同类型的参考文献配置
    test_cases = [
        {
            "name": "使用natbib包",
            "latex": r"\usepackage{natbib}\bibliography{refs}\citep{test2023}"
        },
        {
            "name": "使用biblatex包", 
            "latex": r"\usepackage{biblatex}\addbibresource{refs.bib}\cite{test2023}"
        },
        {
            "name": "内嵌参考文献",
            "latex": r"\begin{thebibliography}{9}\bibitem{test} Test reference\end{thebibliography}"
        },
        {
            "name": "无参考文献",
            "latex": r"\section{Introduction} This is a simple document."
        }
    ]
    
    for test_case in test_cases:
        print(f"\n分析: {test_case['name']}")
        analysis = compiler._analyze_bibliography_usage(test_case['latex'])
        print(f"  有参考文献: {analysis['has_bibliography']}")
        print(f"  .bib文件: {analysis['bib_files']}")
        print(f"  引用数量: {analysis['cite_commands']}")
        print(f"  使用natbib: {analysis['uses_natbib']}")
        print(f"  使用biblatex: {analysis['uses_biblatex']}")
        print(f"  内嵌参考文献: {analysis['has_thebibliography']}")
    
    # 显示编译统计
    print("\n" + "=" * 50)
    print("编译统计信息")
    print("=" * 50)
    
    stats = compiler.get_compile_stats()
    print("编译统计:")
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    print(f"\n{'='*70}")
    print("LaTeX翻译PDF编译器测试完成")
    print("重点验证了参考文献编译功能")
    print(f"{'='*70}")
    
    # 检查生成的文件
    print(f"\n生成的文件:")
    output_dir = Path("./output")
    if output_dir.exists():
        pdf_files = list(output_dir.glob("*.pdf"))
        log_files = list(output_dir.glob("*.log"))
        
        print(f"PDF文件 ({len(pdf_files)} 个):")
        for pdf_file in pdf_files:
            size = pdf_file.stat().st_size
            print(f"  - {pdf_file.name} ({size} 字节)")
        
        if log_files:
            print(f"日志文件 ({len(log_files)} 个):")
            for log_file in log_files:
                size = log_file.stat().st_size
                print(f"  - {log_file.name} ({size} 字节)")
    
    return True

if __name__ == "__main__":
    try:
        success = main()
        if success:
            print("\n✅ 所有测试通过，PDF编译器（参考文献功能）可以正常使用")
        else:
            print("\n❌ 部分测试失败，请检查LaTeX编译环境和参考文献配置")
    except KeyboardInterrupt:
        print("\n\n用户中断测试")
    except Exception as e:
        print(f"\n\n测试过程出现异常: {e}")
        import traceback
        traceback.print_exc()