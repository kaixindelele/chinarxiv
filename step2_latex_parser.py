#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LaTeX文件解析器

主要功能：
1. 在多个tex文件中找到主文件
2. 解析和处理LaTeX文档结构
3. 合并多文件LaTeX工程为单一文档
4. 清理注释和处理编码问题

输入：解压后的源码目录路径
输出：合并后的完整tex内容

作者：基于GPT Academic项目改进
"""

import os
import re
import glob
import shutil
from pathlib import Path
import logging
from typing import List, Tuple, Optional, Dict
import numpy as np

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class LaTeXParser:
    """
    LaTeX文件解析器类
    
    主要功能：
    1. 识别主tex文件
    2. 递归合并多文件工程
    3. 处理文档结构和依赖
    4. 清理和标准化内容
    """
    
    def __init__(self, work_dir: str = "./latex_work"):
        """
        初始化解析器
        
        输入：
        - work_dir: 工作目录路径，用于存储中间文件
        
        输出：无
        
        这个函数初始化LaTeX解析器，设置工作环境
        """
        self.work_dir = Path(work_dir)
        self.work_dir.mkdir(exist_ok=True)
        
        # 存储解析过程中的信息
        self.main_tex_file = None
        self.all_tex_files = []
        self.file_dependencies = {}
        
        logger.info(f"LaTeX解析器初始化完成")
        logger.info(f"工作目录: {self.work_dir}")
    
    def find_all_tex_files(self, source_dir: str) -> List[str]:
        """
        查找目录中所有tex文件
        
        输入：
        - source_dir: 源码目录路径，如 "/path/to/extracted/arxiv"
        
        输出：
        - tex_files: tex文件路径列表，如 ["/path/to/main.tex", "/path/to/section1.tex"]
        
        这个函数递归搜索目录中的所有tex文件
        """
        try:
            source_path = Path(source_dir)
            tex_files = []
            
            # 递归查找所有.tex文件
            for tex_file in source_path.glob("**/*.tex"):
                if tex_file.is_file():
                    tex_files.append(str(tex_file))
            
            # 排序以保证一致性
            tex_files.sort()
            
            logger.info(f"找到 {len(tex_files)} 个tex文件:")
            for tex_file in tex_files:
                relative_path = Path(tex_file).relative_to(source_path)
                logger.info(f"  - {relative_path}")
            
            self.all_tex_files = tex_files
            return tex_files
            
        except Exception as e:
            logger.error(f"查找tex文件时出错: {e}")
            return []
    
    def find_main_tex_file(self, tex_files: List[str]) -> Tuple[bool, str, str]:
        """
        在多个tex文件中找到主文件
        
        输入：
        - tex_files: tex文件路径列表，如 ["/path/to/main.tex", "/path/to/section1.tex"]
        
        输出：查找结果元组
        - success: 是否找到主文件（布尔值）
        - main_file: 主文件路径（字符串）
        - message: 结果消息（字符串）
        
        这个函数通过分析文档类声明和内容特征来识别主tex文件
        """
        try:
            logger.info("开始查找主tex文件...")
            
            if not tex_files:
                return False, "", "没有找到任何tex文件"
            
            candidates = []
            
            # 分析每个tex文件
            for tex_file in tex_files:
                try:
                    with open(tex_file, 'r', encoding='utf-8', errors='replace') as f:
                        content = f.read()
                    
                    # 检查是否包含documentclass（主文件的标志）
                    if r'\documentclass' in content:
                        score = self._calculate_main_file_score(content, tex_file)
                        candidates.append((tex_file, score, content))
                        logger.info(f"候选主文件: {Path(tex_file).name} (评分: {score})")
                        
                except Exception as e:
                    logger.warning(f"读取文件 {tex_file} 时出错: {e}")
                    continue
            
            if not candidates:
                return False, "", "没有找到包含\\documentclass的主文件"
            
            # 选择评分最高的文件作为主文件
            candidates.sort(key=lambda x: x[1], reverse=True)
            main_file, best_score, _ = candidates[0]
            
            logger.info(f"选择主文件: {Path(main_file).name} (最高评分: {best_score})")
            
            # 如果有多个候选文件，显示详细信息
            if len(candidates) > 1:
                logger.info("其他候选文件:")
                for tex_file, score, _ in candidates[1:]:
                    logger.info(f"  - {Path(tex_file).name} (评分: {score})")
            
            self.main_tex_file = main_file
            return True, main_file, f"找到主文件: {Path(main_file).name}"
            
        except Exception as e:
            error_msg = f"查找主文件时出错: {e}"
            logger.error(error_msg)
            return False, "", error_msg
    
    def _calculate_main_file_score(self, content: str, file_path: str) -> int:
        """
        计算文件作为主文件的可能性评分
        
        输入：
        - content: 文件内容（字符串）
        - file_path: 文件路径（字符串）
        
        输出：
        - score: 评分（整数），分数越高越可能是主文件
        
        这个函数通过多个指标评估文件是否为主文件
        """
        score = 0
        file_name = Path(file_path).name.lower()
        
        # 文件名评分
        if 'main' in file_name:
            score += 10
        elif 'paper' in file_name:
            score += 8
        elif 'article' in file_name:
            score += 6
        elif file_name.startswith('ms'):  # manuscript
            score += 5
        
        # 内容特征评分
        # 包含更多结构元素的文件更可能是主文件
        if r'\begin{document}' in content:
            score += 15
        if r'\maketitle' in content:
            score += 10
        if r'\title{' in content:
            score += 8
        if r'\author{' in content:
            score += 8
        if r'\abstract' in content:
            score += 6
        
        # 包含输入其他文件的指令
        input_commands = len(re.findall(r'\\input\{.*?\}', content))
        include_commands = len(re.findall(r'\\include\{.*?\}', content))
        score += (input_commands + include_commands) * 2
        
        # 包含章节结构
        sections = len(re.findall(r'\\section\{.*?\}', content))
        subsections = len(re.findall(r'\\subsection\{.*?\}', content))
        score += sections * 3 + subsections * 1
        
        # 避免模板文件的特征（扣分项）
        template_keywords = ['template', 'example', 'sample', 'demo', 'test']
        for keyword in template_keywords:
            if keyword in content.lower():
                score -= 5
        
        # 模板常见词汇扣分
        unwanted_words = [
            '\\LaTeX', 'manuscript', 'Guidelines', 'font', 'citations',
            'rejected', 'blind review', 'reviewers', 'submission'
        ]
        for word in unwanted_words:
            if word in content:
                score -= 2
        
        return max(0, score)  # 确保分数不为负
    
    def remove_comments(self, content: str) -> str:
        """
        移除LaTeX注释
        
        输入：
        - content: LaTeX内容（字符串）
        
        输出：
        - cleaned_content: 清理后的内容（字符串）
        
        这个函数移除LaTeX文档中的注释行和行内注释
        """
        try:
            lines = content.splitlines()
            cleaned_lines = []
            
            for line in lines:
                # 跳过整行注释（以%开头的行）
                stripped_line = line.lstrip()
                if stripped_line.startswith('%'):
                    continue
                
                # 移除行内注释（但保留转义的%）
                # 使用正则表达式查找未转义的%
                cleaned_line = re.sub(r'(?<!\\)%.*', '', line)
                cleaned_lines.append(cleaned_line)
            
            cleaned_content = '\n'.join(cleaned_lines)
            
            # 统计清理效果
            original_lines = len(lines)
            cleaned_lines_count = len(cleaned_lines)
            removed_lines = original_lines - cleaned_lines_count
            
            if removed_lines > 0:
                logger.info(f"移除了 {removed_lines} 行注释")
            
            return cleaned_content
            
        except Exception as e:
            logger.warning(f"移除注释时出错: {e}")
            return content
    
    def find_tex_file_ignore_case(self, base_dir: str, target_file: str) -> Optional[str]:
        """
        忽略大小写查找tex文件
        
        输入：
        - base_dir: 基础目录路径，如 "/path/to/source"
        - target_file: 目标文件名，如 "section1" 或 "section1.tex"
        
        输出：
        - file_path: 找到的文件路径（字符串）或None
        
        这个函数在指定目录中查找文件，支持大小写不敏感和自动添加.tex扩展名
        """
        try:
            base_path = Path(base_dir)
            
            # 如果输入的文件路径是绝对路径且存在，直接返回
            if Path(target_file).is_absolute() and Path(target_file).exists():
                return target_file
            
            # 构建可能的文件路径
            possible_paths = [
                base_path / target_file,
                base_path / f"{target_file}.tex"
            ]
            
            # 检查精确匹配
            for path in possible_paths:
                if path.exists() and path.is_file():
                    return str(path)
            
            # 如果精确匹配失败，尝试大小写不敏感匹配
            target_lower = target_file.lower()
            target_lower_tex = f"{target_file.lower()}.tex"
            
            for tex_file in base_path.glob("**/*.tex"):
                file_name = tex_file.name.lower()
                stem_name = tex_file.stem.lower()
                
                if file_name == target_lower_tex or stem_name == target_lower:
                    logger.info(f"找到大小写不匹配的文件: {tex_file}")
                    return str(tex_file)
            
            return None
            
        except Exception as e:
            logger.warning(f"查找文件 {target_file} 时出错: {e}")
            return None
    
    def merge_tex_files_recursive(self, main_file: str, base_dir: str) -> str:
        """
        递归合并LaTeX文件
        
        输入：
        - main_file: 主文件路径，如 "/path/to/main.tex"
        - base_dir: 基础目录路径，如 "/path/to/source"
        
        输出：
        - merged_content: 合并后的完整内容（字符串）
        
        这个函数递归处理\\input和\\include命令，将多文件工程合并为单一文档
        """
        try:
            logger.info(f"开始合并文件: {Path(main_file).name}")
            
            # 读取主文件内容
            with open(main_file, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            
            # 移除注释
            content = self.remove_comments(content)
            
            # 查找所有\input{...}命令（从后往前处理，避免位置偏移）
            input_pattern = r'\\input\{([^}]+)\}'
            matches = list(re.finditer(input_pattern, content))
            
            # 从后往前替换，避免位置变化影响
            for match in reversed(matches):
                input_file = match.group(1)
                start_pos = match.start()
                end_pos = match.end()
                
                logger.info(f"处理输入文件: {input_file}")
                
                # 查找实际文件路径
                actual_file = self.find_tex_file_ignore_case(base_dir, input_file)
                
                if actual_file:
                    # 递归合并子文件
                    sub_content = self.merge_tex_files_recursive(actual_file, base_dir)
                    # 替换\input命令为文件内容
                    content = content[:start_pos] + sub_content + content[end_pos:]
                    logger.info(f"✓ 成功合并: {input_file}")
                else:
                    # 如果找不到文件，保留原始命令并添加警告
                    warning = f"\n% 警告: 找不到输入文件 {input_file}\n"
                    content = content[:start_pos] + warning + content[start_pos:]
                    logger.warning(f"找不到输入文件: {input_file}")
            
            # 处理\include{...}命令（类似处理）
            include_pattern = r'\\include\{([^}]+)\}'
            matches = list(re.finditer(include_pattern, content))
            
            for match in reversed(matches):
                include_file = match.group(1)
                start_pos = match.start()
                end_pos = match.end()
                
                logger.info(f"处理包含文件: {include_file}")
                
                actual_file = self.find_tex_file_ignore_case(base_dir, include_file)
                
                if actual_file:
                    sub_content = self.merge_tex_files_recursive(actual_file, base_dir)
                    # \include命令会自动添加分页，这里也添加
                    content = content[:start_pos] + f"\n\\clearpage\n{sub_content}\n" + content[end_pos:]
                    logger.info(f"✓ 成功包含: {include_file}")
                else:
                    warning = f"\n% 警告: 找不到包含文件 {include_file}\n"
                    content = content[:start_pos] + warning + content[start_pos:]
                    logger.warning(f"找不到包含文件: {include_file}")
            
            return content
            
        except Exception as e:
            logger.error(f"合并文件 {main_file} 时出错: {e}")
            # 返回原始内容作为后备
            try:
                with open(main_file, 'r', encoding='utf-8', errors='replace') as f:
                    return f.read()
            except:
                return f"% 错误: 无法读取文件 {main_file}"
    
    def add_chinese_support(self, content: str) -> str:
        """
        为LaTeX文档添加中文支持
        
        输入：
        - content: 原始LaTeX文档内容
        
        输出：
        - enhanced_content: 添加中文支持后的内容
        
        这个函数在文档中添加必要的中文支持包和配置
        """
        try:
            # 检查是否包含中文字符
            import re
            chinese_pattern = re.compile(r'[\u4e00-\u9fff]')
            has_chinese = bool(chinese_pattern.search(content))
            
            if not has_chinese:
                logger.debug("文档不包含中文字符，无需修复字体支持")
                return content
            
            logger.info("检测到中文字符，开始添加中文支持...")
            
            # 检查是否已经有ctex包
            if r'\usepackage{ctex}' in content:
                logger.debug("文档已包含ctex包")
                return content
            
            # 查找documentclass位置
            documentclass_pattern = re.compile(r"\\documentclass.*\n")
            match = documentclass_pattern.search(content)
            
            if not match:
                logger.warning("未找到documentclass声明，无法添加中文支持")
                return content
            
            position = match.end()
            
            # 准备要插入的中文支持代码
            add_ctex = "\\usepackage{ctex}\n"
            add_url = "\\usepackage{url}\n" if "{url}" not in content else ""
            
            # 在documentclass后插入ctex包
            content = content[:position] + add_ctex + add_url + content[position:]
            
            # 修改documentclass以支持中文
            # 为documentclass添加中文相关选项
            content = re.sub(
                r"\\documentclass\[(.*?)\]\{(.*?)\}",
                r"\\documentclass[\1,fontset=windows,UTF8]{\2}",
                content
            )
            content = re.sub(
                r"\\documentclass\{(.*?)\}",
                r"\\documentclass[fontset=windows,UTF8]{\1}",
                content
            )
            
            logger.info("✓ 已添加中文支持(ctex)")
            return content
            
        except Exception as e:
            logger.warning(f"添加中文支持时出错: {e}")
            return content
    
    def parse_and_merge(self, source_dir: str, add_chinese: bool = True) -> Tuple[bool, str, str]:
        """
        解析并合并LaTeX工程
        
        输入：
        - source_dir: 源码目录路径，如 "/path/to/extracted/arxiv"
        - add_chinese: 是否添加中文支持，默认True
        
        输出：处理结果元组
        - success: 是否成功（布尔值）
        - merged_content: 合并后的tex内容（字符串）
        - message: 结果消息（字符串）
        
        这个函数是主要的公共接口，完成从源码目录到合并文档的完整流程
        """
        print("=" * 60)
        print("开始LaTeX文件解析和合并")
        print("=" * 60)
        
        try:
            # Step 1: 查找所有tex文件
            print("Step 1: 查找tex文件...")
            tex_files = self.find_all_tex_files(source_dir)
            
            if not tex_files:
                return False, "", "未找到任何tex文件"
            
            print(f"✓ 找到 {len(tex_files)} 个tex文件")
            
            # Step 2: 识别主文件
            print("Step 2: 识别主文件...")
            success, main_file, message = self.find_main_tex_file(tex_files)
            
            if not success:
                return False, "", message
            
            print(f"✓ 主文件: {Path(main_file).name}")
            
            # Step 3: 递归合并文件
            print("Step 3: 递归合并文件...")
            merged_content = self.merge_tex_files_recursive(main_file, source_dir)
            
            if not merged_content.strip():
                return False, "", "合并后内容为空"
            
            print(f"✓ 合并完成，内容长度: {len(merged_content)} 字符")
            
            # Step 4: 添加中文支持（如果需要）
            if add_chinese:
                print("Step 4: 添加中文支持...")
                merged_content = self.add_chinese_support(merged_content)
                print("✓ 中文支持已添加")
            else:
                print("Step 4: 跳过中文支持")
            
            # 统计最终结果
            lines_count = len(merged_content.splitlines())
            words_count = len(merged_content.split())
            
            print(f"✓ 最终统计:")
            print(f"  - 总行数: {lines_count}")
            print(f"  - 总词数: {words_count}")
            print(f"  - 字符数: {len(merged_content)}")
            
            print("=" * 60)
            print("LaTeX解析合并完成")
            print("=" * 60)
            
            return True, merged_content, f"成功合并 {len(tex_files)} 个文件"
            
        except Exception as e:
            error_msg = f"解析合并过程出错: {e}"
            logger.error(error_msg)
            return False, "", error_msg
    
    def save_merged_content(self, content: str, output_path: str) -> bool:
        """
        保存合并后的内容到文件
        
        输入：
        - content: 合并后的tex内容（字符串）
        - output_path: 输出文件路径，如 "./output/merged.tex"
        
        输出：
        - success: 是否保存成功（布尔值）
        
        这个函数将合并后的内容保存到指定文件
        """
        try:
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(content)
            
            logger.info(f"合并内容已保存到: {output_file}")
            return True
            
        except Exception as e:
            logger.error(f"保存文件时出错: {e}")
            return False

def parse_latex_project(source_dir: str, output_path: str = None, 
                       add_chinese: bool = True) -> Tuple[bool, str]:
    """
    便捷函数：解析LaTeX项目
    
    输入：
    - source_dir: 源码目录路径，如 "/path/to/extracted/arxiv"
    - output_path: 输出文件路径（可选），如 "./output/merged.tex"
    - add_chinese: 是否添加中文支持，默认True
    
    输出：
    - success: 是否成功（布尔值）
    - result: 成功时返回合并内容，失败时返回错误信息（字符串）
    
    这个函数提供最简单的调用方式，一步完成LaTeX项目的解析和合并
    """
    parser = LaTeXParser()
    success, merged_content, message = parser.parse_and_merge(source_dir, add_chinese)
    
    if success:
        # 如果指定了输出路径，保存文件
        if output_path:
            if parser.save_merged_content(merged_content, output_path):
                return True, f"解析成功，已保存到: {output_path}"
            else:
                return False, "解析成功但保存失败"
        else:
            return True, merged_content
    else:
        return False, message

# 测试和示例代码
def main():
    """
    测试函数，演示解析器的使用方法
    """
    print("=" * 70)
    print("LaTeX解析器测试")
    print("=" * 70)
    
    # 测试目录（需要先运行step1下载论文）
    test_dirs = [
        "./test_arxiv_cache/1812.10695/extract",
        "./test_arxiv_cache/2402.14207/extract",
        "./arxiv_cache/1812.10695/extract",  # 如果使用了不同的缓存目录
    ]
    
    # 创建解析器
    parser = LaTeXParser(work_dir="./test_latex_work")
    
    # 测试每个目录
    for i, test_dir in enumerate(test_dirs, 1):
        if not Path(test_dir).exists():
            print(f"跳过测试 {i}: 目录不存在 {test_dir}")
            continue
            
        print(f"\n{'='*50}")
        print(f"测试 {i}: {test_dir}")
        print(f"{'='*50}")
        
        try:
            success, merged_content, message = parser.parse_and_merge(
                test_dir, 
                add_chinese=True
            )
            
            if success:
                print(f"✅ 解析成功")
                print(f"消息: {message}")
                
                # 保存结果用于检查
                output_file = f"./test_output/merged_test_{i}.tex"
                if parser.save_merged_content(merged_content, output_file):
                    print(f"✓ 结果已保存到: {output_file}")
                
                # 显示内容摘要
                lines = merged_content.splitlines()
                print(f"内容摘要:")
                print(f"  - 总行数: {len(lines)}")
                print(f"  - 字符数: {len(merged_content)}")
                
                # 显示前几行内容
                print(f"前10行内容:")
                for j, line in enumerate(lines[:10], 1):
                    print(f"  {j:2d}: {line[:80]}{'...' if len(line) > 80 else ''}")
                
            else:
                print(f"❌ 解析失败: {message}")
                
        except KeyboardInterrupt:
            print("\n用户中断测试")
            break
        except Exception as e:
            print(f"❌ 测试异常: {e}")
    
    print(f"\n{'='*70}")
    print("测试完成")
    print(f"{'='*70}")

if __name__ == "__main__":
    main()
