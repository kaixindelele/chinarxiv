#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LaTeX翻译管理器

主要功能：
1. 管理多个文本段落的翻译任务
2. 调用LLM进行批量翻译
3. 处理专业术语一致性
4. 支持多线程并发翻译
5. 错误处理和重试机制
6. 集成翻译缓存功能

输入：切分后的LaTeX文本段落列表
输出：翻译后的段落列表

作者：基于GPT Academic项目改进
"""

import json
import time
import logging
import threading
import re
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

# 导入GPT模型调用器
from step4_gpt_model import GPTModelCaller
from step7_trans_cache import TranslationCache
from config import API_KEY, BASE_URL, LLM_MODEL

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TranslationManager:
    """
    LaTeX翻译管理器类
    
    主要功能：
    1. 管理翻译任务
    2. 调用LLM服务
    3. 处理术语一致性
    4. 支持多线程翻译
    """
    
    def __init__(self, 
             api_key: str = "",
             base_url: str = "",
             llm_model: str = "",
             max_workers: int = 3,
             terms_file: str = "all_terms.json",
             cache_dir: str = "./arxiv_cache"):
        """
        初始化翻译管理器
        
        输入：
        - api_key: OpenAI API密钥，如 "sk-xxx..."
        - base_url: API基础URL，如 "https://apis.xxxx.ai"
        - llm_model: 使用的LLM模型名称，如 "gpt-4o-mini"
        - max_workers: 最大并发线程数，默认3
        - terms_file: 术语词典文件路径，如 "all_terms.json"
        - cache_dir: 翻译缓存目录，如 "./arxiv_cache"
        
        输出：无
        
        这个函数初始化翻译管理器，设置模型和并发参数
        """
        self.api_key = api_key
        self.base_url = base_url
        self.llm_model = llm_model
        self.max_workers = max_workers
        self.cache_dir = cache_dir
        
        # 处理术语文件路径
        if not Path(terms_file).is_absolute():
            current_dir = Path(__file__).parent
            root_dir = current_dir.parent
            self.terms_file = root_dir / terms_file
        else:
            self.terms_file = Path(terms_file)
        
        # 初始化GPT调用器
        self.gpt_caller = GPTModelCaller(
            api_key=self.api_key,
            base_url=self.base_url,
            model=self.llm_model
        )

        # 初始化翻译缓存管理器
        self.cache_manager = TranslationCache(cache_dir=self.cache_dir)
        
        # 加载术语词典
        self.default_terms = self._load_terms_dict()
        
        # 翻译统计信息
        self.translation_stats = {
            'total_segments': 0,
            'completed_segments': 0,
            'failed_segments': 0,
            'cached_segments': 0,
            'start_time': None,
            'end_time': None
        }
        
        logger.info(f"翻译管理器初始化完成")
        logger.info(f"LLM模型: {self.llm_model}")
        logger.info(f"API地址: {self.base_url}")
        logger.info(f"最大并发数: {self.max_workers}")
        logger.info(f"术语词典: {len(self.default_terms)} 条")
        logger.info(f"缓存目录: {self.cache_dir}")

    
    def _load_terms_dict(self) -> Dict[str, str]:
        """
        加载术语词典
        
        输入：无
        输出：术语词典字典，如 {"agent": "智能体", "model": "模型"}
        
        这个函数从JSON文件加载专业术语翻译对照表
        """
        try:
            if self.terms_file.exists():
                with open(self.terms_file, 'r', encoding='utf-8') as f:
                    terms = json.load(f)
                logger.info(f"成功加载术语词典: {len(terms)} 条术语")
                return terms
            else:
                logger.warning(f"术语词典文件不存在: {self.terms_file}")
                # 返回一些基础术语
                return {
                    "agent": "智能体", 
                    "model": "模型",
                    "algorithm": "算法",
                    "neural network": "神经网络",
                    "machine learning": "机器学习",
                    "deep learning": "深度学习",
                    "artificial intelligence": "人工智能",
                    "dataset": "数据集",
                    "training": "训练",
                    "inference": "推理",
                    "transformer": "变换器",
                    "attention": "注意力",
                    "embedding": "嵌入",
                    "fine-tuning": "微调"
                }
        except Exception as e:
            logger.error(f"加载术语词典失败: {e}")
            return {}
    
    def _extract_relevant_terms(self, text: str, user_terms: Dict[str, str] = None) -> Dict[str, str]:
        """
        提取文本中相关的术语
        
        输入：
        - text: 要翻译的文本内容，如 "The agent uses machine learning..."
        - user_terms: 用户自定义术语，如 {"agent": "代理"}
        
        输出：
        - relevant_terms: 相关术语字典，如 {"agent": "智能体", "machine learning": "机器学习"}
        
        这个函数从文本中识别出需要统一翻译的专业术语
        """
        try:
            # 合并默认术语和用户术语
            all_terms = self.default_terms.copy()
            if user_terms:
                all_terms.update(user_terms)
            
            relevant_terms = {}
            text_lower = text.lower()
            
            # 查找文本中出现的术语
            for english_term, chinese_term in all_terms.items():
                if english_term.lower() in text_lower:
                    relevant_terms[english_term] = chinese_term
            
            logger.debug(f"提取到 {len(relevant_terms)} 个相关术语")
            return relevant_terms
            
        except Exception as e:
            logger.error(f"提取术语时出错: {e}")
            return {}
    
    def _generate_translation_prompt(self, text: str, user_requirements: str = "", user_terms: Dict[str, str] = None) -> Tuple[str, str]:
        """
        生成翻译提示词（改进版，基于原版gpt_academic）
        
        输入：
        - text: 要翻译的LaTeX文本片段，如 "\\section{Introduction} Machine learning..."
        - user_requirements: 用户自定义要求，如 "保持学术性"
        - user_terms: 用户术语字典，如 {"agent": "代理"}
        
        输出：
        - system_prompt: 系统提示词（字符串）
        - user_prompt: 用户提示词（字符串）
        
        这个函数基于GPT Academic项目的switch_prompt逻辑生成翻译指令
        """
        try:
            # 提取相关术语
            relevant_terms = self._extract_relevant_terms(text, user_terms)
            terms_str = str(relevant_terms) if relevant_terms else "{}"
            
            # 构建系统提示词 - 基于原版gpt_academic
            system_prompt = "You are a professional academic translator with Latex format."
            
            # 构建用户提示词 - 完全基于原版gpt_academic的逻辑
            if user_requirements:
                user_prompt = f"""Please translate the LaTeX format fragment of an English academic paper into authentic Simplified Chinese according to the following instructions.
=== Here are some translation requirements: 
- In the translation, please refer to the following terminology dict: {terms_str}. 
- For special or rare professional terms, please add parentheses after the translation to indicate the original English term. 
- Please translate according to the specific requirements given by {user_requirements}. 
- Maintain the accuracy of the output LaTeX format and ensure that LaTeX commands (such as \\section, \\cite, \\begin, \\item, etc.) are not modified. 
- Do not translate the content within formulas and tables, and maintain the correctness of the LaTeX format. 
=== 
The following is the LaTeX text fragment that needs to be translated: 

```
{text}
```
===
Your output needed to be enclosed with triple backticks, as following:
```latex
translated content
```
"""
            else:
                user_prompt = f"""Please translate the LaTeX format fragment of an English academic paper into authentic Simplified Chinese according to the following instructions.
=== Here are some translation requirements: 
- In the translation, please refer to the following terminology dict: {terms_str}. 
- For special or rare professional terms, please add parentheses after the translation to indicate the original English term. 
- Maintain the accuracy of the output LaTeX format and ensure that LaTeX commands (such as \\section, \\cite, \\begin, \\item, etc.) are not modified. 
- Do not translate the content within formulas and tables, and maintain the correctness of the LaTeX format. 
=== 
The following is the LaTeX text fragment that needs to be translated: 

```
{text}
```
===
Your output needed to be enclosed with triple backticks, as following:
```latex
translated content
```
"""
            
            return system_prompt, user_prompt
            
        except Exception as e:
            logger.error(f"生成翻译提示词时出错: {e}")
            # 返回简单的备用提示词
            system_prompt = "你是专业的学术翻译员，请将英文LaTeX内容翻译成中文，保持格式不变。"
            user_prompt = f"请翻译以下内容：\n\n{text}"
            return system_prompt, user_prompt
    
    def _clean_translation_result(self, translation: str) -> str:
        """
        清理翻译结果（增强版，基于原版gpt_academic）
        
        输入：
        - translation: 原始翻译结果，如 "```latex\n翻译内容\n```"
        
        输出：
        - cleaned: 清理后的翻译内容（字符串）
        
        这个函数从LLM响应中提取出纯净的翻译内容，并进行格式修复
        """
        try:
            # 去除可能的代码块标记
            translation = translation.strip()
            
            # 移除 ```latex 和 ``` 标记
            if translation.startswith('```latex'):
                translation = translation[8:]  # 移除 ```latex
            elif translation.startswith('```'):
                translation = translation[3:]   # 移除 ```
            
            if translation.endswith('```'):
                translation = translation[:-3]  # 移除结尾的 ```
            
            # 去除首尾空白
            translation = translation.strip()
            
            # 移除可能的提示文字（这是关键修复）
            unwanted_prefixes = [
                "翻译后内容：",
                "翻译内容：",
                "译文：",
                "翻译结果：",
                "翻译后的内容：",
                "以下是翻译：",
                "翻译如下：",
                "Translated content:",
                "Translation:",
                "Here is the translation:",
            ]
            
            for prefix in unwanted_prefixes:
                if translation.startswith(prefix):
                    translation = translation[len(prefix):].strip()
                    break
            
            # 移除可能的换行符开头
            translation = translation.lstrip('\n').strip()
            
            return translation
            
        except Exception as e:
            logger.warning(f"清理翻译结果时出错: {e}")
            return translation.strip()
    
    def fix_content(self, final_tex: str, node_string: str) -> str:
        """
        修复常见的GPT翻译错误（基于原版gpt_academic）
        
        输入：
        - final_tex: GPT翻译后的内容
        - node_string: 原始节点内容
        
        输出：
        - fixed_content: 修复后的内容
        
        这个函数修复常见的LaTeX格式错误，提高翻译成功率
        """
        try:
            # 修复未转义的%符号
            final_tex = re.sub(r"(?<!\\)%", "\\%", final_tex)
            
            # 修复命令和花括号之间的空格
            final_tex = re.sub(r"\\([a-z]{2,10})\ \{", r"\\\1{", string=final_tex)
            final_tex = re.sub(r"\\\ ([a-z]{2,10})\{", r"\\\1{", string=final_tex)
            
            # 修复命令内部的中文标点
            def mod_inbraket(match):
                cmd = match.group(1)
                str_to_modify = match.group(2)
                str_to_modify = str_to_modify.replace("：", ":")  # 中文冒号→英文冒号
                str_to_modify = str_to_modify.replace("，", ",")  # 中文逗号→英文逗号
                return "\\" + cmd + "{" + str_to_modify + "}"
            
            final_tex = re.sub(r"\\([a-z]{2,10})\{([^\}]*?)\}", mod_inbraket, string=final_tex)
            
            # 检查是否有严重错误，如果有则回滚到原文
            if "Traceback" in final_tex and "[Local Message]" in final_tex:
                final_tex = node_string  # 出问题了，还原原文
                
            if node_string.count("\\begin") != final_tex.count("\\begin"):
                final_tex = node_string  # 出问题了，还原原文
                
            if node_string.count("\_") > 0 and node_string.count("\_") > final_tex.count("\_"):
                # 修复未转义的下划线
                final_tex = re.sub(r"(?<!\\)_", "\\_", final_tex)
            
            # 检查花括号平衡
            def compute_brace_level(string):
                brace_level = 0
                for c in string:
                    if c == "{":
                        brace_level += 1
                    elif c == "}":
                        brace_level -= 1
                return brace_level
            
            if compute_brace_level(final_tex) != compute_brace_level(node_string):
                # 花括号不平衡，尝试部分修复
                def join_most(tex_t, tex_o):
                    p_t = 0
                    p_o = 0
                    
                    def find_next(string, chars, begin):
                        p = begin
                        while p < len(string):
                            if string[p] in chars:
                                return p, string[p]
                            p += 1
                        return None, None
                    
                    while True:
                        res1, char = find_next(tex_o, ["{", "}"], p_o)
                        if res1 is None:
                            break
                        res2, char = find_next(tex_t, [char], p_t)
                        if res2 is None:
                            break
                        p_o = res1 + 1
                        p_t = res2 + 1
                    return tex_t[:p_t] + tex_o[p_o:]
                
                final_tex = join_most(final_tex, node_string)
            
            return final_tex
            
        except Exception as e:
            logger.warning(f"修复内容时出错: {e}")
            return final_tex
    
    def _call_llm_api(self, system_prompt: str, user_prompt: str, segment_index: int = 0) -> Tuple[bool, str, str]:
        """
        调用LLM API进行翻译
        
        输入：
        - system_prompt: 系统提示词字符串，如 "你是专业翻译员..."
        - user_prompt: 用户提示词字符串，包含要翻译的内容
        - segment_index: 段落索引号，用于日志标识
        
        输出：
        - success: 是否成功（布尔值）
        - result: 翻译结果（字符串）
        - error: 错误信息（字符串）
        
        这个函数调用实际的LLM服务进行文本翻译
        """
        try:
            logger.info(f"开始翻译段落 {segment_index}")
            
            # 调用GPT模型进行翻译
            success, translation, error = self.gpt_caller.call_gpt_sync(
                user_prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=0.3,  # 较低温度保证翻译稳定性
                max_tokens=4000
            )
            
            if success:
                logger.info(f"段落 {segment_index} 翻译成功，长度: {len(translation)} 字符")
                # 清理和修复翻译结果
                cleaned_translation = self._clean_translation_result(translation)
                return True, cleaned_translation, ""
            else:
                logger.error(f"段落 {segment_index} 翻译失败: {error}")
                return False, "", error
                
        except Exception as e:
            error_msg = f"LLM API调用异常: {e}"
            logger.error(f"段落 {segment_index} 翻译异常: {error_msg}")
            return False, "", error_msg
    
    def _translate_single_segment(self, segment_data: Tuple[int, str, str, Dict[str, str]]) -> Tuple[int, bool, str, str]:
        """
        翻译单个文本段落（线程工作函数）
        
        输入：
        - segment_data: 包含段落信息的元组 (索引, 原文, 用户要求, 用户术语)
          如 (0, "\\section{Introduction}...", "保持学术性", {"agent": "智能体"})
        
        输出：
        - result_tuple: 结果元组 (索引, 成功标志, 翻译结果, 错误信息)
          如 (0, True, "\\section{介绍}...", "")
        
        这个函数在多线程环境中翻译单个文本段落，支持缓存
        """
        index, text, user_requirements, user_terms = segment_data
        
        try:
            # 先检查缓存（需要arxiv_id，从用户术语中提取）
            arxiv_id = user_terms.get('__arxiv_id__', None)
            
            if arxiv_id and self.cache_manager:
                # 尝试从缓存获取翻译
                cached_translation = self.cache_manager.get_cached_translation(
                    arxiv_id, index, text
                )
                if cached_translation:
                    logger.info(f"段落 {index} 使用缓存翻译")
                    return index, True, cached_translation, ""
            
            # 生成翻译提示词
            system_prompt, user_prompt = self._generate_translation_prompt(
                text, user_requirements, user_terms
            )
            
            # 调用LLM API
            success, translation, error = self._call_llm_api(
                system_prompt, user_prompt, index
            )
            
            if success:
                # 使用fix_content进行后处理（这是关键修复）
                fixed_translation = self.fix_content(translation, text)
                
                # 保存到缓存
                if arxiv_id and self.cache_manager:
                    self.cache_manager.update_single_translation(
                        arxiv_id, index, text, fixed_translation
                    )
                    logger.info(f"段落 {index} 翻译完成并缓存")
                else:
                    logger.info(f"段落 {index} 翻译完成")
                return index, True, fixed_translation, ""
            else:
                logger.error(f"段落 {index} 翻译失败: {error}")
                return index, False, text, error  # 失败时返回原文
                
        except Exception as e:
            error_msg = f"翻译段落 {index} 时出现异常: {e}"
            logger.error(error_msg)
            return index, False, text, error_msg
    
    def translate_segments(self, 
                        segments: List[str], 
                        user_requirements: str = "", 
                        user_terms: Dict[str, str] = None,
                        progress_callback = None,
                        arxiv_id: str = None) -> Tuple[bool, List[str], List[str]]:
        """
        批量翻译文本段落
        
        输入：
        - segments: 文本段落列表，如 ["\\section{Introduction}...", "The method..."]
        - user_requirements: 用户自定义翻译要求，如 "保持学术性，专业术语要准确"
        - user_terms: 用户术语字典，如 {"agent": "代理", "model": "模型"}
        - progress_callback: 进度回调函数，接收 (当前进度, 总数) 参数
        - arxiv_id: arxiv论文ID，用于缓存
        
        输出：
        - success: 整体是否成功（布尔值）
        - translations: 翻译结果列表（字符串列表）
        - errors: 错误信息列表（字符串列表）
        
        这个函数是主要的翻译接口，支持多线程并发翻译
        """
        print("=" * 60)
        print("开始批量翻译LaTeX文档")
        print("=" * 60)
        
        try:
            # 初始化统计信息
            self.translation_stats['total_segments'] = len(segments)
            self.translation_stats['completed_segments'] = 0
            self.translation_stats['failed_segments'] = 0
            self.translation_stats['start_time'] = time.time()
            
            print(f"翻译任务信息:")
            print(f"- 总段落数: {len(segments)}")
            print(f"- 并发线程数: {self.max_workers}")
            print(f"- 使用模型: {self.llm_model}")
            print(f"- 用户术语: {len(user_terms) if user_terms else 0} 条")
            print(f"- API地址: {self.base_url}")
            
            # 准备翻译任务数据
            task_data = []
            # 为缓存功能，在user_terms中添加arxiv_id
            enhanced_user_terms = user_terms.copy() if user_terms else {}
            if arxiv_id:
                enhanced_user_terms['__arxiv_id__'] = arxiv_id
                logger.info(f"启用翻译缓存，arxiv_id: {arxiv_id}")
            
            for i, segment in enumerate(segments):
                task_data.append((i, segment, user_requirements, enhanced_user_terms))
            
            # 初始化结果容器
            translations = [""] * len(segments)
            errors = [""] * len(segments)
            
            print(f"\n开始多线程翻译...")
            
            # 执行多线程翻译
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # 提交所有任务
                future_to_index = {
                    executor.submit(self._translate_single_segment, data): data[0] 
                    for data in task_data
                }
                
                # 收集结果
                completed_count = 0
                for future in as_completed(future_to_index):
                    index, success, result, error = future.result()
                    
                    translations[index] = result
                    errors[index] = error
                    
                    if success:
                        self.translation_stats['completed_segments'] += 1
                        status = "✓"
                    else:
                        self.translation_stats['failed_segments'] += 1
                        status = "✗"
                    
                    completed_count += 1
                    
                    # 显示进度
                    progress = (completed_count / len(segments)) * 100
                    print(f"{status} 翻译进度: {completed_count}/{len(segments)} ({progress:.1f}%) - 段落 {index}")
                    
                    # 调用进度回调
                    if progress_callback:
                        progress_callback(completed_count, len(segments))
            
            # 更新统计信息
            self.translation_stats['end_time'] = time.time()
            duration = self.translation_stats['end_time'] - self.translation_stats['start_time']
            
            # 输出统计结果
            print(f"\n翻译完成统计:")
            print(f"- 成功翻译: {self.translation_stats['completed_segments']} 段")
            print(f"- 翻译失败: {self.translation_stats['failed_segments']} 段")
            print(f"- 总耗时: {duration:.2f} 秒")
            if duration > 0:
                print(f"- 平均速度: {len(segments)/duration:.2f} 段/秒")
            
            # 显示API调用统计
            gpt_stats = self.gpt_caller.get_stats()
            print(f"- API调用统计: {gpt_stats}")
            
                        # 判断整体是否成功
            overall_success = self.translation_stats['failed_segments'] == 0
            
            if overall_success:
                print("✓ 所有段落翻译成功")
            else:
                print(f"✗ {self.translation_stats['failed_segments']} 个段落翻译失败")
                
                # 显示失败的段落
                print("\n失败的段落:")
                for i, error in enumerate(errors):
                    if error:
                        print(f"  段落 {i}: {error}")
            
            print("=" * 60)
            print("批量翻译完成")
            print("=" * 60)
            
            return overall_success, translations, errors
            
        except Exception as e:
            error_msg = f"批量翻译过程出错: {e}"
            logger.error(error_msg)
            print(f"✗ {error_msg}")
            return False, [], [error_msg]

def translate_latex_segments(segments: List[str], 
                           api_key: str = "",
                           base_url: str = "",
                           llm_model: str = "gpt-4o-mini",
                           user_requirements: str = "",
                           user_terms: Dict[str, str] = None,
                           max_workers: int = 3) -> Tuple[bool, List[str]]:
    """
    便捷函数：翻译LaTeX文档段落
    
    输入：
    - segments: LaTeX段落列表，如 ["\\section{Introduction}...", "The proposed method..."]
    - api_key: OpenAI API密钥，如 "sk-xxx..."
    - base_url: API基础URL，如 "https://apis.xxxx.ai"
    - llm_model: LLM模型名称，如 "gpt-4o-mini"
    - user_requirements: 用户翻译要求，如 "保持学术性"
    - user_terms: 用户术语，如 {"agent": "智能体"}
    - max_workers: 并发数，默认3
    
    输出：
    - success: 是否成功（布尔值）
    - translations: 翻译结果列表（失败时返回错误信息）
    
    这个函数提供最简单的调用方式，一步完成LaTeX文档的批量翻译
    """
    try:
        # 创建翻译管理器
        manager = TranslationManager(
            api_key=api_key,
            base_url=base_url,
            llm_model=llm_model,
            max_workers=max_workers
        )
        
        # 执行翻译
        success, translations, errors = manager.translate_segments(
            segments=segments,
            user_requirements=user_requirements,
            user_terms=user_terms
        )
        
        if success:
            return True, translations
        else:
            # 返回包含错误信息的结果
            error_summary = f"翻译失败，错误信息: {[e for e in errors if e]}"
            return False, [error_summary]
            
    except Exception as e:
        error_msg = f"翻译过程出错: {e}"
        logger.error(error_msg)
        return False, [error_msg]

# 测试和示例代码
def main():
    """
    测试函数，演示翻译管理器的使用方法
    """
    print("=" * 70)
    print("LaTeX翻译管理器测试")
    print("=" * 70)
    
    # 测试数据 - LaTeX文档段落
    test_segments = [
        r"\section{Introduction}",
        r"Machine learning has revolutionized the field of artificial intelligence, enabling computers to learn from data without being explicitly programmed.",
        r"Neural networks, inspired by the human brain, consist of interconnected nodes that process information through weighted connections.",
        r"The training process involves adjusting these weights to minimize the difference between predicted and actual outputs.",
        r"\subsection{Deep Learning}",
        r"Deep learning models, characterized by multiple hidden layers, have achieved remarkable success in various domains including computer vision and natural language processing."
    ]
    
    # 测试用户自定义术语
    test_user_terms = {
        "machine learning": "机器学习",
        "artificial intelligence": "人工智能",
        "neural networks": "神经网络",
        "deep learning": "深度学习"
    }
    
    # 测试用户要求
    test_user_requirements = "翻译要保持学术性和专业性，确保术语翻译的一致性"
    
    print("测试数据:")
    print(f"- 段落数量: {len(test_segments)}")
    print(f"- 用户术语: {len(test_user_terms)} 条")
    print(f"- 特殊要求: {test_user_requirements}")
    
    # 创建翻译管理器
    manager = TranslationManager(
        api_key=API_KEY,
        base_url=BASE_URL,
        llm_model="gpt-4o-mini",
        max_workers=2  # 测试时使用较少并发
    )
    
    # 测试翻译功能
    print("\n" + "=" * 50)
    print("开始翻译测试")
    print("=" * 50)
    
    success, translations, errors = manager.translate_segments(
        segments=test_segments,
        user_requirements=test_user_requirements,
        user_terms=test_user_terms
    )
    
    if success:
        print("\n✅ 翻译测试通过")
        print("\n翻译结果示例:")
        for i, (original, translation) in enumerate(zip(test_segments, translations)):
            print(f"\n段落 {i+1}:")
            print(f"原文: {original[:100]}{'...' if len(original) > 100 else ''}")
            print(f"译文: {translation[:100]}{'...' if len(translation) > 100 else ''}")
            if i >= 2:  # 只显示前3个段落
                print(f"... (还有 {len(test_segments)-3} 个段落)")
                break
                
        # 保存翻译结果供检查
        try:
            output_file = Path("test_translation_output.txt")
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write("LaTeX翻译管理器测试结果\n")
                f.write("=" * 40 + "\n\n")
                for i, (original, translation) in enumerate(zip(test_segments, translations)):
                    f.write(f"段落 {i+1}:\n")
                    f.write(f"原文:\n{original}\n\n")
                    f.write(f"译文:\n{translation}\n\n")
                    f.write("-" * 40 + "\n\n")
            print(f"\n✓ 翻译结果已保存到: {output_file}")
        except Exception as e:
            print(f"保存翻译结果失败: {e}")
    else:
        print("\n❌ 翻译测试失败")
        print("错误信息:")
        for i, error in enumerate(errors):
            if error:
                print(f"  段落 {i}: {error}")
    
    # 测试便捷函数
    print("\n" + "=" * 50)
    print("测试便捷函数接口")
    print("=" * 50)
    
    success, result = translate_latex_segments(
        segments=test_segments[:3],  # 只测试前3个段落
        api_key=API_KEY,
        base_url=BASE_URL,
        llm_model=LLM_MODEL,
        user_requirements="简洁明了的翻译",
        user_terms={"machine learning": "机器学习"},
        max_workers=1
    )
    
    if success:
        print("✅ 便捷函数测试通过")
        print(f"翻译结果数量: {len(result)}")
        print("前2个翻译结果:")
        for i, translation in enumerate(result[:2]):
            print(f"  {i+1}: {translation[:80]}{'...' if len(translation) > 80 else ''}")
    else:
        print("❌ 便捷函数测试失败")
        print(f"错误: {result}")
    
    # 测试单段落翻译
    print("\n" + "=" * 50)
    print("测试单段落翻译")
    print("=" * 50)
    
    single_text = r"The transformer architecture has become the foundation of modern natural language processing models."
    system_prompt, user_prompt = manager._generate_translation_prompt(
        single_text, 
        "保持技术术语的准确性", 
        {"transformer": "变换器", "architecture": "架构"}
    )
    
    success, translation, error = manager._call_llm_api(system_prompt, user_prompt, 999)
    
    if success:
        print("✅ 单段落翻译测试通过")
        print(f"原文: {single_text}")
        print(f"译文: {translation}")
    else:
        print("❌ 单段落翻译测试失败")
        print(f"错误: {error}")
    
    print(f"\n{'='*70}")
    print("测试完成")
    print(f"{'='*70}")

if __name__ == "__main__":
    main()
