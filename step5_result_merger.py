#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LaTeX翻译结果合并器

主要功能：
1. 将翻译后的段落重新组合成完整文档
2. 添加翻译警告和版权信息
3. 修复常见的LaTeX格式问题
4. 处理翻译失败的段落回滚
5. 验证LaTeX文档的完整性

输入：翻译后的段落列表
输出：完整的翻译后LaTeX文档

作者：基于GPT Academic项目改进
"""

import re
import logging
from typing import List, Tuple, Optional, Dict, Any
from pathlib import Path
import time

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class LaTeXResultMerger:
    """
    LaTeX翻译结果合并器类
    
    主要功能：
    1. 合并翻译段落
    2. 添加警告信息
    3. 修复格式问题
    4. 验证文档完整性
    """
    
    def __init__(self):
        """
        初始化合并器
        
        输入：无
        输出：无
        
        这个函数初始化合并器，设置警告信息和处理规则
        """
        # 翻译警告信息
        self.warning_message = (
            "*{\\scriptsize\\textbf{警告：该PDF由GPT-Academic开源项目调用大语言模型+Latex翻译插件一键生成，"
            "版权归原文作者所有。翻译内容可靠性无保障，请仔细鉴别并以原文为准。"
            "项目Github地址 \\url{https://github.com/binary-husky/gpt_academic}。"
            "免费使用网页：\\url{https://academic.chatpaper.top/}。"
        )
        
        self.warning_declare = (
            "为了防止大语言模型的意外谬误产生扩散影响，禁止移除或修改此警告。}}\\\\"
        )
        
        # 统计信息
        self.merge_stats = {
            'total_segments': 0,
            'merged_segments': 0,
            'failed_segments': 0,
            'fixed_issues': 0
        }
        
        logger.info(f"LaTeX结果合并器初始化完成")
    
    def fix_latex_format_issues(self, content: str) -> Tuple[str, int]:
        """
        修复常见的LaTeX格式问题（保守修复，避免破坏结构）
        
        输入：
        - content: LaTeX内容，如 "这是一个%测试文档..."
        
        输出：
        - fixed_content: 修复后的内容（字符串）
        - fix_count: 修复的问题数量（整数）
        
        这个函数谨慎修复LLM翻译时的格式错误，避免破坏LaTeX结构
        """
        try:
            fixed_content = content
            fix_count = 0
            
            # 先备份原始内容，用于回滚
            original_content = content
            original_left_braces = content.count('{')
            original_right_braces = content.count('}')
            
            logger.info(f"原始花括号统计: 左{original_left_braces}, 右{original_right_braces}")
            
            # 修复1：处理未转义的%符号（但保护LaTeX注释）
            # 只处理中文后面的%，避免误改LaTeX注释
            pattern = r'([\u4e00-\u9fff])%'
            matches = re.findall(pattern, fixed_content)
            if matches:
                fixed_content = re.sub(pattern, r'\1\%', fixed_content)
                fix_count += len(matches)
                logger.debug(f"修复了 {len(matches)} 个中文后的%符号")
            
            # 修复2：修复命令和花括号之间的多余空格（保守处理）
            # 只处理常见命令
            common_commands = ['section', 'subsection', 'chapter', 'title', 'author', 
                            'textbf', 'textit', 'emph', 'cite', 'ref', 'label']
            for cmd in common_commands:
                pattern = f'\\\\{cmd}\\s+\\{{'
                if re.search(pattern, fixed_content):
                    fixed_content = re.sub(pattern, f'\\\\{cmd}{{', fixed_content)
                    fix_count += 1
                    logger.debug(f"修复了 \\{cmd} 命令的空格问题")
            
            # 修复3：处理中文标点在特定LaTeX命令中的问题
            # 只在标题类命令中替换中文标点
            title_commands = ['title', 'section', 'subsection', 'chapter', 'caption']
            for cmd in title_commands:
                pattern = f'\\\\{cmd}\\{{([^}}]*?)\\}}'
                
                def fix_punctuation_in_command(match):
                    content_inside = match.group(1)
                    # 只替换标题中的中文冒号和逗号
                    if '：' in content_inside or '，' in content_inside:
                        content_inside = content_inside.replace('：', ':')
                        content_inside = content_inside.replace('，', ',')
                        return f'\\{cmd}{{{content_inside}}}'
                    return match.group(0)
                
                new_content = re.sub(pattern, fix_punctuation_in_command, fixed_content)
                if new_content != fixed_content:
                    fixed_content = new_content
                    fix_count += 1
                    logger.debug(f"修复了 \\{cmd} 命令中的中文标点")
            
            # 检查修复后的花括号平衡
            new_left_braces = fixed_content.count('{')
            new_right_braces = fixed_content.count('}')
            
            # 如果修复导致花括号不平衡加剧，回滚
            original_diff = abs(original_left_braces - original_right_braces)
            new_diff = abs(new_left_braces - new_right_braces)
            
            if new_diff > original_diff:
                logger.warning(f"修复导致花括号不平衡加剧（原差值:{original_diff}, 新差值:{new_diff}），回滚修改")
                return original_content, 0
            
            logger.info(f"修复后花括号统计: 左{new_left_braces}, 右{new_right_braces}")
            
            # 不要尝试自动修复花括号不平衡，这可能破坏LaTeX结构
            if new_left_braces != new_right_braces:
                logger.warning(f"检测到花括号不平衡，但不自动修复以避免破坏结构")
            
            return fixed_content, fix_count
            
        except Exception as e:
            logger.warning(f"修复LaTeX格式时出错: {e}")
            return content, 0
    
    def check_latex_completeness(self, content: str) -> Dict[str, Any]:
        """
        检查LaTeX文档的完整性（增强版）
        
        输入：
        - content: LaTeX文档内容，如 "\\documentclass{article}\\begin{document}..."
        
        输出：
        - check_result: 检查结果字典
        {
            'has_documentclass': bool,    # 是否有documentclass
            'has_begin_document': bool,   # 是否有begin{document}
            'has_end_document': bool,     # 是否有end{document}
            'brace_balanced': bool,       # 花括号是否平衡
            'begin_end_balanced': bool,   # begin/end环境是否平衡
            'issues': list,              # 发现的问题列表
            'fixable_issues': list,      # 可修复的问题列表
            'critical_issues': list      # 严重问题列表
        }
        
        这个函数检查LaTeX文档的基本结构完整性，并分类问题严重程度
        """
        check_result = {
            'has_documentclass': False,
            'has_begin_document': False,
            'has_end_document': False,
            'brace_balanced': False,
            'begin_end_balanced': False,
            'issues': [],
            'fixable_issues': [],
            'critical_issues': []
        }
        
        try:
            # 检查documentclass
            if r'\documentclass' in content:
                check_result['has_documentclass'] = True
            else:
                issue = '缺少\\documentclass声明'
                check_result['issues'].append(issue)
                check_result['critical_issues'].append(issue)
            
            # 检查begin{document}
            if r'\begin{document}' in content:
                check_result['has_begin_document'] = True
            else:
                issue = '缺少\\begin{document}'
                check_result['issues'].append(issue)
                check_result['critical_issues'].append(issue)
            
            # 检查end{document}
            if r'\end{document}' in content:
                check_result['has_end_document'] = True
            else:
                issue = '缺少\\end{document}'
                check_result['issues'].append(issue)
                check_result['critical_issues'].append(issue)
            
            # 检查花括号平衡（更详细的分析）
            left_braces = content.count('{')
            right_braces = content.count('}')
            brace_diff = left_braces - right_braces
            
            if brace_diff == 0:
                check_result['brace_balanced'] = True
            else:
                if brace_diff > 0:
                    issue = f'缺少 {brace_diff} 个右花括号'
                else:
                    issue = f'缺少 {-brace_diff} 个左花括号'
                
                check_result['issues'].append(issue)
                
                # 少量花括号不平衡可能可以修复
                if abs(brace_diff) <= 3:
                    check_result['fixable_issues'].append(issue)
                else:
                    check_result['critical_issues'].append(issue)
                
                logger.warning(f"花括号不平衡: 左{left_braces}, 右{right_braces}, 差值{brace_diff}")
            
            # 检查begin/end环境平衡（详细分析）
            begin_commands = re.findall(r'\\begin\{([^}]+)\}', content)
            end_commands = re.findall(r'\\end\{([^}]+)\}', content)
            
            begin_dict = {}
            for cmd in begin_commands:
                begin_dict[cmd] = begin_dict.get(cmd, 0) + 1
            
            end_dict = {}
            for cmd in end_commands:
                end_dict[cmd] = end_dict.get(cmd, 0) + 1
            
            # 找出所有环境
            all_envs = set(list(begin_dict.keys()) + list(end_dict.keys()))
            unmatched = []
            
            for env in all_envs:
                begin_count = begin_dict.get(env, 0)
                end_count = end_dict.get(env, 0)
                
                if begin_count != end_count:
                    diff = begin_count - end_count
                    if diff > 0:
                        unmatched.append(f'{env}(缺少{diff}个\\end)')
                    else:
                        unmatched.append(f'{env}(缺少{-diff}个\\begin)')
                    
                    # 记录详细信息
                    logger.warning(f"环境 {env} 不平衡: begin={begin_count}, end={end_count}")
                    
                    # document环境不平衡是严重问题
                    if env == 'document':
                        check_result['critical_issues'].append(f'document环境不平衡')
            
            if not unmatched:
                check_result['begin_end_balanced'] = True
            else:
                issue = f'begin/end环境不平衡: {", ".join(unmatched)}'
                check_result['issues'].append(issue)
                
                # 判断是否可修复
                critical_envs = ['document', 'abstract', 'table*', 'figure*']
                for env_issue in unmatched:
                    env_name = env_issue.split('(')[0]
                    if env_name in critical_envs:
                        check_result['critical_issues'].append(f'{env_name}环境不平衡')
                    else:
                        check_result['fixable_issues'].append(f'{env_name}环境不平衡')
            
            # 统计问题严重程度
            total_issues = len(check_result['issues'])
            critical_count = len(check_result['critical_issues'])
            fixable_count = len(check_result['fixable_issues'])
            
            logger.info(f"LaTeX完整性检查完成:")
            logger.info(f"  总问题数: {total_issues}")
            logger.info(f"  严重问题: {critical_count}")
            logger.info(f"  可修复问题: {fixable_count}")
            
        except Exception as e:
            logger.error(f"检查LaTeX完整性时出错: {e}")
            check_result['issues'].append(f'检查过程出错: {e}')
            check_result['critical_issues'].append(f'检查失败')
        
        return check_result
    
    def add_translation_warning(self, content: str, llm_model: str = "GPT", temperature: float = 0.3) -> str:
        """
        在适当位置添加翻译警告信息
        
        输入：
        - content: LaTeX文档内容，如 "\\documentclass{article}\\begin{abstract}..."
        - llm_model: 使用的LLM模型名称，如 "gpt-4o-mini"
        - temperature: 温度参数，如 0.3
        
        输出：
        - content_with_warning: 添加警告后的内容（字符串）
        
        这个函数在摘要后添加翻译警告和版权信息
        """
        try:
            # 构建完整的警告信息
            model_info = f"当前大语言模型: {llm_model}，当前语言模型温度设定: {temperature}。"
            full_warning = self.warning_message + model_info + self.warning_declare
            
            # 查找摘要位置 - 优先查找 \begin{abstract}
            pattern = re.compile(r'\\begin\{abstract\}.*?\n', re.DOTALL)
            match = pattern.search(content)
            
            if match:
                # 找到 \begin{abstract}，在其后添加警告
                position = match.end()
                result = content[:position] + full_warning + "\n\n" + content[position:]
                logger.info("在\\begin{abstract}后添加了翻译警告")
                return result
            
            # 如果没找到，查找 \abstract{...}
            pattern = re.compile(r'\\abstract\{(.*?)\}', re.DOTALL)
            match = pattern.search(content)
            
            if match:
                # 找到 \abstract{}，在内容开始处添加警告
                start_pos = match.start(1)
                result = content[:start_pos] + full_warning + "\n\n" + content[start_pos:]
                logger.info("在\\abstract{}内添加了翻译警告")
                return result
            
            # 如果都没找到，尝试在 \maketitle 后添加
            if r'\maketitle' in content:
                position = content.find(r'\maketitle') + len(r'\maketitle')
                # 找到下一个换行
                next_line = content.find('\n', position)
                if next_line != -1:
                    position = next_line + 1
                result = content[:position] + "\n" + full_warning + "\n\n" + content[position:]
                logger.info("在\\maketitle后添加了翻译警告")
                return result
            
            # 最后尝试在 \begin{document} 后添加
            if r'\begin{document}' in content:
                position = content.find(r'\begin{document}') + len(r'\begin{document}')
                # 找到下一个换行
                next_line = content.find('\n', position)
                if next_line != -1:
                    position = next_line + 1
                result = content[:position] + "\n" + full_warning + "\n\n" + content[position:]
                logger.info("在\\begin{document}后添加了翻译警告")
                return result
            
            # 如果都找不到合适位置，在文档开头添加
            logger.warning("未找到合适的警告插入位置，在文档开头添加")
            return full_warning + "\n\n" + content
            
        except Exception as e:
            logger.error(f"添加翻译警告时出错: {e}")
            return content
    
    def merge_translated_segments(self, 
                             translated_segments: List[str], 
                             original_segments: List[str] = None,
                             original_full_content: str = "",  # 新增参数：完整原文
                             llm_model: str = "gpt-4o-mini",
                             temperature: float = 0.3,
                             allow_format_fix: bool = True) -> Tuple[bool, str, str]:
        """
        合并翻译后的段落为完整文档
        
        输入：
        - translated_segments: 翻译后的段落列表，如 ["\\section{介绍}", "机器学习是..."]
        - original_segments: 原始段落列表（可选），用于失败时回滚
        - original_full_content: 完整的原始LaTeX文档内容，用于提取文档结构
        - llm_model: LLM模型名称，如 "gpt-4o-mini"
        - temperature: 温度参数，如 0.3
        - allow_format_fix: 是否允许格式修复，默认True
        
        输出：
        - success: 是否成功（布尔值）
        - merged_content: 合并后的完整内容（字符串）
        - message: 结果消息（字符串）
        
        这个函数是主要的合并接口，将翻译段落组合成完整的LaTeX文档
        """
        print("=" * 60)
        print("开始合并翻译结果")
        print("=" * 60)
        
        try:
            # 初始化统计信息
            self.merge_stats['total_segments'] = len(translated_segments)
            self.merge_stats['merged_segments'] = 0
            self.merge_stats['failed_segments'] = 0
            self.merge_stats['fixed_issues'] = 0
            
            print(f"合并信息:")
            print(f"- 翻译段落数: {len(translated_segments)}")
            print(f"- 使用模型: {llm_model}")
            print(f"- 温度参数: {temperature}")
            print(f"- 格式修复: {'开启' if allow_format_fix else '关闭'}")
            print(f"- 原文长度: {len(original_full_content)} 字符")
            
            if not translated_segments:
                return False, "", "翻译段落列表为空"
            
            # Step 1: 智能合并 - 如果有完整原文，则进行结构化合并
            print("\nStep 1: 智能结构化合并...")
            if original_full_content:
                merged_content = self._merge_with_structure_preservation(
                    original_full_content, translated_segments, original_segments
                )
            else:
                # 回退到基础合并
                merged_content = self._basic_merge(translated_segments, original_segments)
            
            print(f"✓ 合并完成，内容长度: {len(merged_content)} 字符")
            
            # Step 2: 格式修复
            if allow_format_fix:
                print("\nStep 2: LaTeX格式修复...")
                fixed_content, fix_count = self.fix_latex_format_issues(merged_content)
                merged_content = fixed_content
                self.merge_stats['fixed_issues'] = fix_count
                print(f"✓ 修复了 {fix_count} 个格式问题")
            else:
                print("\nStep 2: 跳过格式修复")
            
            # Step 3: 添加翻译警告
            print("\nStep 3: 添加翻译警告...")
            merged_content = self.add_translation_warning(merged_content, llm_model, temperature)
            print("✓ 翻译警告已添加")
            
            # Step 4: 完整性检查
            print("\nStep 4: 文档完整性检查...")
            completeness = self.check_latex_completeness(merged_content)

            if completeness['issues']:
                print("发现的问题:")
                for issue in completeness['issues']:
                    print(f"  - {issue}")
                
                if completeness['critical_issues']:
                    print("\n严重问题:")
                    for issue in completeness['critical_issues']:
                        print(f"  ⚠️ {issue}")
                
                if completeness['fixable_issues']:
                    print("\n可修复问题:")
                    for issue in completeness['fixable_issues']:
                        print(f"  ℹ️ {issue}")
            else:
                print("✓ 文档结构完整")

            # 生成统计报告
            print(f"\n合并统计:")
            print(f"- 成功合并: {self.merge_stats['merged_segments']} 段")
            print(f"- 合并失败: {self.merge_stats['failed_segments']} 段")
            print(f"- 格式修复: {self.merge_stats['fixed_issues']} 处")
            print(f"- 总问题数: {len(completeness['issues'])}")
            print(f"- 严重问题: {len(completeness['critical_issues'])}")

            # 计算成功率
            success_rate = (self.merge_stats['merged_segments'] / self.merge_stats['total_segments']) * 100
            print(f"- 成功率: {success_rate:.1f}%")

            # 更宽松的成功标准：只有严重问题才判定为失败
            has_critical_issues = len(completeness['critical_issues']) > 0
            overall_success = (success_rate >= 80) and (not has_critical_issues)

            if overall_success:
                if completeness['fixable_issues']:
                    message = f"合并成功（有{len(completeness['fixable_issues'])}个可修复问题）。成功率: {success_rate:.1f}%"
                    print(f"✓ {message}")
                else:
                    message = f"合并成功！成功率: {success_rate:.1f}%，文档结构完整。"
                    print(f"✓ {message}")
            else:
                if has_critical_issues:
                    message = f"合并失败：发现{len(completeness['critical_issues'])}个严重问题。成功率: {success_rate:.1f}%"
                    print(f"✗ {message}")
                else:
                    message = f"合并完成但成功率较低。成功率: {success_rate:.1f}%"
                    print(f"⚠ {message}")

            print("=" * 60)
            print("翻译结果合并完成")
            print("=" * 60)

            return overall_success, merged_content, message
            
        except Exception as e:
            error_msg = f"合并过程出错: {e}"
            logger.error(error_msg)
            print(f"✗ {error_msg}")
            return False, "", error_msg
        
    def _merge_with_structure_preservation(self, original_full_content: str, 
                                 translated_segments: List[str], 
                                 original_segments: List[str] = None) -> str:
        """
        基于原文结构的智能合并
        
        输入：
        - original_full_content: 完整原文，如 "\\documentclass{article}\\begin{document}..."
        - translated_segments: 翻译段落列表
        - original_segments: 原始段落列表
        
        输出：
        - merged_content: 合并后的完整文档内容
        
        这个函数保持原文的LaTeX结构，只替换需要翻译的部分
        """
        try:
            from step3_content_splitter import LaTeXContentSplitter
            import re
            
            # 使用相同的切分逻辑来定位翻译段落在原文中的位置
            splitter = LaTeXContentSplitter()
            
            # 重新进行结构保护切分，获取完整的节点信息
            segments_from_original, structure_info = splitter.split_latex_with_full_protection(original_full_content)
            
            logger.info(f"原文切分出 {len(segments_from_original)} 个段落")
            logger.info(f"翻译段落数: {len(translated_segments)}")
            logger.info(f"结构信息包含 {len(structure_info)} 个部分")
            
            # 使用结构信息进行智能合并
            if len(structure_info) > 0:
                merged_content = ""
                translate_index = 0
                
                for item in structure_info:
                    if item['type'] == 'preserve':
                        # 保护区域，直接添加原文
                        merged_content += item['content']
                        self.merge_stats['merged_segments'] += 1
                    else:
                        # 翻译区域，使用翻译内容
                        if translate_index < len(translated_segments):
                            merged_content += translated_segments[translate_index]
                            translate_index += 1
                            self.merge_stats['merged_segments'] += 1
                        else:
                            # 如果翻译段落不够，使用原文
                            merged_content += item['content']
                            self.merge_stats['failed_segments'] += 1
                            logger.warning(f"翻译段落不足，使用原文: {item['content'][:50]}...")
                
                logger.info(f"完成结构化合并，合并了 {self.merge_stats['merged_segments']} 个段落")
                return merged_content
            else:
                logger.warning(f"未获得结构信息，回退到基础合并")
                return self._basic_merge(translated_segments, original_segments)
                
        except Exception as e:
            logger.error(f"结构化合并失败: {e}")
            return self._basic_merge(translated_segments, original_segments)


    def _basic_merge(self, translated_segments: List[str], 
                    original_segments: List[str] = None) -> str:
        """
        基础段落合并（原有逻辑）
        
        输入：
        - translated_segments: 翻译后的段落列表
        - original_segments: 原始段落列表
        
        输出：
        - merged_content: 合并后的内容
        
        这个函数执行简单的段落拼接合并
        """
        merged_content = ""
        
        for i, segment in enumerate(translated_segments):
            if segment.strip():  # 跳过空段落
                # 检查段落是否包含错误信息
                if "[Local Message]" in segment and "警告" in segment:
                    # 这是一个错误段落，尝试使用原始内容
                    if original_segments and i < len(original_segments):
                        merged_content += original_segments[i]
                        self.merge_stats['failed_segments'] += 1
                        logger.warning(f"段落 {i} 翻译失败，使用原文")
                    else:
                        merged_content += segment  # 仍然包含但标记失败
                        self.merge_stats['failed_segments'] += 1
                else:
                    merged_content += segment
                    self.merge_stats['merged_segments'] += 1
                
                # 确保段落之间有适当的分隔
                if not segment.endswith('\n'):
                    merged_content += '\n'
        
        return merged_content

    
    def save_merged_content(self, content: str, output_path: str) -> bool:
        """
        保存合并后的内容到文件
        
        输入：
        - content: 合并后的LaTeX内容，完整的LaTeX文档字符串
        - output_path: 输出文件路径，如 "./output/merged_translated.tex"
        
        输出：
        - success: 是否保存成功（布尔值）
        
        这个函数将合并后的内容保存到指定文件
        """
        try:
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(content)
            
            file_size = output_file.stat().st_size
            logger.info(f"合并内容已保存到: {output_file} ({file_size} 字节)")
            return True
            
        except Exception as e:
            logger.error(f"保存文件时出错: {e}")
            return False

def merge_translation_result(translated_segments: List[str], 
                           original_segments: List[str] = None,
                           output_path: str = None,
                           llm_model: str = "gpt-4o-mini",
                           temperature: float = 0.3) -> Tuple[bool, str]:
    """
    便捷函数：合并翻译结果
    
    输入：
    - translated_segments: 翻译后的段落列表，如 ["\\section{介绍}", "机器学习..."]
    - original_segments: 原始段落列表（可选），用于失败时回滚
    - output_path: 输出文件路径（可选），如 "./output/translated.tex"
    - llm_model: LLM模型名称，如 "gpt-4o-mini"
    - temperature: 温度参数，如 0.3
    
    输出：
    - success: 是否成功（布尔值）
    - result: 成功时返回合并内容，失败时返回错误信息（字符串）
    
    这个函数提供最简单的调用方式，一步完成翻译结果的合并
    """
    try:
        merger = LaTeXResultMerger()
        success, merged_content, message = merger.merge_translated_segments(
            translated_segments=translated_segments,
            original_segments=original_segments,
            llm_model=llm_model,
            temperature=temperature
        )
        
        if success and output_path:
            if merger.save_merged_content(merged_content, output_path):
                return True, f"合并成功并保存到: {output_path}\n{message}"
            else:
                return False, f"合并成功但保存失败: {message}"
        elif success:
            return True, merged_content
        else:
            return False, message
            
    except Exception as e:
        error_msg = f"合并过程出错: {e}"
        logger.error(error_msg)
        return False, error_msg

# 测试和示例代码
def main():
    """
    测试函数，演示合并器的使用方法
    """
    print("=" * 70)
    print("LaTeX翻译结果合并器测试")
    print("=" * 70)
    
        # 测试数据 - 模拟翻译后的段落
    test_translated_segments = [
        r"\documentclass{article}",
        r"\usepackage[utf8]{inputenc}",
        r"\usepackage{amsmath}",
        r"\title{机器学习中的深度神经网络}",
        r"\author{GPT Academic 项目}",
        r"\date{\today}",
        r"\begin{document}",
        r"\maketitle",
        r"\begin{abstract}",
        r"本文介绍了深度学习在机器学习中的应用。我们提出了一种新的神经网络架构，能够有效地处理复杂的数据模式。",
        r"\end{abstract}",
        r"\section{介绍}",
        r"机器学习已经革命化了人工智能领域，使计算机能够从数据中学习而无需显式编程。",
        r"神经网络，受人脑启发，由通过加权连接处理信息的互连节点组成。",
        r"训练过程涉及调整这些权重以最小化预测输出和实际输出之间的差异。",
        r"\subsection{深度学习}",
        r"深度学习模型，以多个隐藏层为特征，在包括计算机视觉和自然语言处理在内的各个领域取得了显著成功。",
        r"\begin{equation}",
        r"f(x) = \sigma(\sum_{i=1}^{n} w_i x_i + b)",
        r"\end{equation}",
        r"其中 $\sigma$ 是激活函数，$w_i$ 是权重，$b$ 是偏置项。",
        r"\section{方法}",
        r"我们提出的方法基于注意力机制(attention mechanism)，能够动态地关注输入序列的不同部分。",
        r"\subsection{实验设置}",
        r"实验在包含10万个样本的数据集上进行，使用标准的训练-验证-测试划分。",
        r"\section{结果}",
        r"实验结果表明，我们的方法在准确率上比基线方法提高了15%。",
        r"\section{结论}",
        r"本文提出的深度学习方法为机器学习领域提供了新的见解和工具。",
        r"\end{document}"
    ]
    
    # 测试原始段落（用于回滚测试）
    test_original_segments = [
        r"\documentclass{article}",
        r"\usepackage[utf8]{inputenc}",
        r"\usepackage{amsmath}",
        r"\title{Deep Neural Networks in Machine Learning}",
        r"\author{GPT Academic Project}",
        r"\date{\today}",
        r"\begin{document}",
        r"\maketitle",
        r"\begin{abstract}",
        r"This paper introduces the application of deep learning in machine learning. We propose a new neural network architecture that can effectively handle complex data patterns.",
        r"\end{abstract}",
        r"\section{Introduction}",
        r"Machine learning has revolutionized the field of artificial intelligence, enabling computers to learn from data without being explicitly programmed.",
        r"Neural networks, inspired by the human brain, consist of interconnected nodes that process information through weighted connections.",
        r"The training process involves adjusting these weights to minimize the difference between predicted and actual outputs.",
        r"\subsection{Deep Learning}",
        r"Deep learning models, characterized by multiple hidden layers, have achieved remarkable success in various domains including computer vision and natural language processing.",
        r"\begin{equation}",
        r"f(x) = \sigma(\sum_{i=1}^{n} w_i x_i + b)",
        r"\end{equation}",
        r"where $\sigma$ is the activation function, $w_i$ are the weights, and $b$ is the bias term.",
        r"\section{Method}",
        r"Our proposed method is based on attention mechanism, which can dynamically focus on different parts of the input sequence.",
        r"\subsection{Experimental Setup}",
        r"Experiments were conducted on a dataset containing 100,000 samples, using standard train-validation-test splits.",
        r"\section{Results}",
        r"Experimental results show that our method achieves 15% improvement in accuracy compared to baseline methods.",
        r"\section{Conclusion}",
        r"The proposed deep learning method provides new insights and tools for the machine learning field.",
        r"\end{document}"
    ]
    
    print("测试数据准备完成:")
    print(f"- 翻译段落数: {len(test_translated_segments)}")
    print(f"- 原始段落数: {len(test_original_segments)}")
    
    # 创建合并器
    merger = LaTeXResultMerger()
    
    # 测试1: 基础合并功能
    print("\n" + "=" * 50)
    print("测试1: 基础翻译结果合并")
    print("=" * 50)
    
    success, merged_content, message = merger.merge_translated_segments(
        translated_segments=test_translated_segments,
        llm_model="gpt-4o-mini",
        temperature=0.3
    )
    
    if success:
        print("✅ 基础合并测试通过")
        print(f"合并结果长度: {len(merged_content)} 字符")
        print(f"消息: {message}")
        
        # 保存测试结果
        test_output_file = "test_merged_basic.tex"
        if merger.save_merged_content(merged_content, test_output_file):
            print(f"✓ 测试结果已保存到: {test_output_file}")
        
        # 显示文档开头
        print("\n文档开头预览:")
        lines = merged_content.splitlines()
        for i, line in enumerate(lines[:10]):
            print(f"  {i+1:2d}: {line}")
        if len(lines) > 10:
            print(f"  ... (还有 {len(lines)-10} 行)")
            
    else:
        print("❌ 基础合并测试失败")
        print(f"错误: {message}")
    
    # 测试2: 格式修复功能
    print("\n" + "=" * 50)
    print("测试2: LaTeX格式修复")
    print("=" * 50)
    
    # 创建包含格式问题的测试内容
    problematic_content = r"""
\documentclass{article}
\begin{document}
\title{测试文档}
这里有一些格式问题%未转义的百分号
\section {空格问题}
\textbf{粗体文本，这里有中文逗号}
下划线问题_未转义
\end{document}
"""
    
    print("原始内容（包含格式问题）:")
    print(problematic_content)
    
    fixed_content, fix_count = merger.fix_latex_format_issues(problematic_content)
    
    print(f"\n✓ 格式修复完成，修复了 {fix_count} 个问题")
    print("修复后内容:")
    print(fixed_content)
    
    # 测试3: 完整性检查
    print("\n" + "=" * 50)
    print("测试3: 文档完整性检查")
    print("=" * 50)
    
    # 测试完整文档
    print("检查完整文档...")
    completeness = merger.check_latex_completeness(merged_content)
    
    print("完整性检查结果:")
    print(f"- documentclass: {'✓' if completeness['has_documentclass'] else '✗'}")
    print(f"- begin document: {'✓' if completeness['has_begin_document'] else '✗'}")
    print(f"- end document: {'✓' if completeness['has_end_document'] else '✗'}")
    print(f"- 花括号平衡: {'✓' if completeness['brace_balanced'] else '✗'}")
    print(f"- begin/end平衡: {'✓' if completeness['begin_end_balanced'] else '✗'}")
    
    if completeness['issues']:
        print("发现的问题:")
        for issue in completeness['issues']:
            print(f"  - {issue}")
    else:
        print("✓ 文档结构完整")
    
    # 测试不完整文档
    print("\n检查不完整文档...")
    incomplete_content = r"\documentclass{article}\begin{document}\section{Test"
    incomplete_check = merger.check_latex_completeness(incomplete_content)
    
    print(f"不完整文档问题数: {len(incomplete_check['issues'])}")
    for issue in incomplete_check['issues']:
        print(f"  - {issue}")
    
    # 测试4: 回滚机制
    print("\n" + "=" * 50)
    print("测试4: 翻译失败回滚机制")
    print("=" * 50)
    
    # 创建包含失败段落的测试数据
    failed_segments = test_translated_segments.copy()
    failed_segments[10] = "[Local Message] 警告，翻译失败，这是一个错误段落"
    failed_segments[15] = "[Local Message] 警告，API调用失败"
    
    print("模拟翻译失败情况...")
    success, merged_with_fallback, message = merger.merge_translated_segments(
        translated_segments=failed_segments,
        original_segments=test_original_segments,
        llm_model="gpt-4o-mini",
        temperature=0.3
    )
    
    if success:
        print("✓ 回滚机制测试通过")
        print(f"消息: {message}")
        
        # 保存回滚测试结果
        fallback_output_file = "test_merged_with_fallback.tex"
        if merger.save_merged_content(merged_with_fallback, fallback_output_file):
            print(f"✓ 回滚测试结果已保存到: {fallback_output_file}")
    else:
        print("❌ 回滚机制测试失败")
        print(f"错误: {message}")
    
    # 测试5: 便捷函数
    print("\n" + "=" * 50)
    print("测试5: 便捷函数接口")
    print("=" * 50)
    
    success, result = merge_translation_result(
        translated_segments=test_translated_segments[:10],  # 只测试前10个段落
        output_path="test_convenience_output.tex",
        llm_model="gpt-4o-mini",
        temperature=0.2
    )
    
    if success:
        print("✅ 便捷函数测试通过")
        print(f"结果: {result}")
    else:
        print("❌ 便捷函数测试失败")
        print(f"错误: {result}")
    
    # 测试6: 警告信息添加
    print("\n" + "=" * 50)
    print("测试6: 翻译警告添加")
    print("=" * 50)
    
    # 测试不同的摘要格式
    test_cases = [
        r"\begin{abstract}这是一个测试摘要。\end{abstract}",
        r"\abstract{这是另一个测试摘要。}",
        r"\maketitle\n\section{Introduction}没有摘要的文档。",
        r"\begin{document}\section{Test}最简单的文档。"
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n测试用例 {i}:")
        print(f"原文: {test_case[:50]}...")
        
        with_warning = merger.add_translation_warning(test_case, "gpt-4o-mini", 0.3)
        
        if "警告：该PDF由GPT-Academic" in with_warning:
            print("✓ 警告添加成功")
        else:
            print("✗ 警告添加失败")
    
    print(f"\n{'='*70}")
    print("所有测试完成")
    
    # 统计测试结果
    print("\n测试文件生成:")
    output_files = [
        "test_merged_basic.tex",
        "test_merged_with_fallback.tex", 
        "test_convenience_output.tex"
    ]
    
    for file_path in output_files:
        if Path(file_path).exists():
            size = Path(file_path).stat().st_size
            print(f"✓ {file_path} ({size} 字节)")
        else:
            print(f"✗ {file_path} (未生成)")
    
    print(f"{'='*70}")

if __name__ == "__main__":
    main()