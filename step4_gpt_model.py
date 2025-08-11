#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GPT模型调用器 - 专用于LaTeX翻译

主要功能：
1. 封装OpenAI GPT API调用逻辑
2. 处理翻译请求和响应
3. 支持流式和非流式调用
4. 错误处理和重试机制
5. Token计算和限制

输入：翻译提示词和配置参数
输出：GPT翻译结果

作者：基于GPT Academic项目改进
"""

import json
import time
import requests
import logging
from typing import Dict, Tuple, Optional, Any
import re

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class GPTModelCaller:
    """
    GPT模型调用器类
    
    主要功能：
    1. 管理API配置和认证
    2. 构建和发送请求
    3. 处理响应和错误
    4. 支持重试机制
    """
    
    def __init__(self, 
                 api_key: str = "",
                 base_url: str = "",
                 model: str = "gpt-4o-mini",
                 timeout: int = 60,
                 max_retries: int = 3):
        """
        初始化GPT调用器
        
        输入：
        - api_key: OpenAI API密钥，如 "sk-xxx..."
        - base_url: API基础URL，如 "https://api.openai.com" 或代理地址
        - model: 模型名称，如 "gpt-4o-mini", "gpt-3.5-turbo"
        - timeout: 请求超时时间（秒），默认60秒
        - max_retries: 最大重试次数，默认3次
        
        输出：无
        
        这个函数初始化GPT调用器，设置API配置和网络参数
        """
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        
        # 构建完整的API端点
        self.endpoint = f"{self.base_url}/v1/chat/completions"
        
        # 设置请求头
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        # 统计信息
        self.stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'total_tokens_used': 0
        }
        
        logger.info(f"GPT模型调用器初始化完成")
        logger.info(f"模型: {self.model}")
        logger.info(f"端点: {self.endpoint}")
        logger.info(f"超时时间: {self.timeout}秒")
        
    def count_tokens(self, text: str) -> int:
        """
        简单的token计数
        
        输入：
        - text: 文本内容，如 "Hello, how are you?"
        
        输出：
        - token_count: 估算的token数量（整数）
        
        这个函数使用简单的方法估算文本的token数量
        """
        try:
            # 简单估算：英文约4个字符=1个token，中文约1.5个字符=1个token
            # 这是一个粗略估算，实际应该使用tiktoken库
            
            # 统计中英文字符
            chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
            english_chars = len(text) - chinese_chars
            
            # 估算token数量
            estimated_tokens = int(english_chars / 4 + chinese_chars / 1.5)
            
            return max(1, estimated_tokens)  # 至少1个token
            
        except Exception as e:
            logger.warning(f"Token计数失败: {e}")
            # 备用方案：按空格分割
            return len(text.split())
    
    def build_chat_messages(self, user_prompt: str, system_prompt: str = "") -> list:
        """
        构建聊天消息格式
        
        输入：
        - user_prompt: 用户提示词，如 "请翻译以下内容..."
        - system_prompt: 系统提示词，如 "你是一个专业的翻译员"
        
        输出：
        - messages: OpenAI Chat格式的消息列表
          [
              {"role": "system", "content": "系统提示"},
              {"role": "user", "content": "用户提示"}
          ]
        
        这个函数将提示词转换为OpenAI Chat API要求的消息格式
        """
        messages = []
        
        # 添加系统提示词（如果有）
        if system_prompt.strip():
            messages.append({
                "role": "system",
                "content": system_prompt.strip()
            })
        
        # 添加用户提示词
        messages.append({
            "role": "user", 
            "content": user_prompt.strip()
        })
        
        return messages
    
    def call_gpt_sync(self, 
                      user_prompt: str, 
                      system_prompt: str = "You are a professional academic translator.",
                      temperature: float = 0.3,
                      max_tokens: int = 4000) -> Tuple[bool, str, str]:
        """
        同步调用GPT（非流式）
        
        输入：
        - user_prompt: 用户提示词，包含要翻译的内容
        - system_prompt: 系统提示词，默认为专业翻译员设定
        - temperature: 温度参数，控制输出随机性，默认0.3
        - max_tokens: 最大输出token数，默认4000
        
        输出：返回结果元组
        - success: 是否成功（布尔值）
        - result: GPT回复内容（字符串）
        - error: 错误信息（字符串，成功时为空）
        
        这个函数发送请求到GPT并等待完整响应返回
        """
        try:
            self.stats['total_requests'] += 1
            logger.info(f"开始GPT调用，模型: {self.model}")
            
            # 构建消息
            messages = self.build_chat_messages(user_prompt, system_prompt)
            
            # 构建请求payload
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": False  # 非流式
            }
            
            # 计算输入token数量
            input_text = system_prompt + user_prompt
            input_tokens = self.count_tokens(input_text)
            logger.info(f"输入token数量: {input_tokens}")
            
            # 发送请求（支持重试）
            for attempt in range(self.max_retries + 1):
                try:
                    logger.info(f"发送API请求 (尝试 {attempt + 1}/{self.max_retries + 1})")
                    
                    response = requests.post(
                        self.endpoint,
                        headers=self.headers,
                        json=payload,
                        timeout=self.timeout
                    )
                    
                    # 检查HTTP状态码
                    if response.status_code == 200:
                        break
                    elif response.status_code == 429:
                        # 速率限制，等待后重试
                        wait_time = (attempt + 1) * 5
                        logger.warning(f"遇到速率限制，等待 {wait_time} 秒后重试...")
                        time.sleep(wait_time)
                    else:
                        logger.error(f"API请求失败，状态码: {response.status_code}")
                        logger.error(f"响应内容: {response.text}")
                        
                except requests.exceptions.Timeout:
                    logger.warning(f"请求超时 (尝试 {attempt + 1})")
                    if attempt == self.max_retries:
                        raise
                    time.sleep(2)
                except requests.exceptions.ConnectionError:
                    logger.warning(f"连接错误 (尝试 {attempt + 1})")
                    if attempt == self.max_retries:
                        raise
                    time.sleep(3)
            else:
                # 所有重试都失败了
                error_msg = f"API请求失败，状态码: {response.status_code}"
                self.stats['failed_requests'] += 1
                return False, "", error_msg
            
            # 解析响应
            try:
                result_data = response.json()
                
                # 检查是否有错误
                if 'error' in result_data:
                    error_msg = result_data['error'].get('message', '未知API错误')
                    logger.error(f"API返回错误: {error_msg}")
                    self.stats['failed_requests'] += 1
                    return False, "", error_msg
                
                # 提取回复内容
                if 'choices' in result_data and len(result_data['choices']) > 0:
                    content = result_data['choices'][0]['message']['content']
                    
                    # 更新统计信息
                    if 'usage' in result_data:
                        total_tokens = result_data['usage'].get('total_tokens', 0)
                        self.stats['total_tokens_used'] += total_tokens
                        logger.info(f"Token使用: {total_tokens} (累计: {self.stats['total_tokens_used']})")
                    
                    self.stats['successful_requests'] += 1
                    logger.info(f"GPT调用成功，回复长度: {len(content)} 字符")
                    return True, content, ""
                else:
                    error_msg = "API响应格式异常，未找到choices字段"
                    logger.error(error_msg)
                    self.stats['failed_requests'] += 1
                    return False, "", error_msg
                    
            except json.JSONDecodeError as e:
                error_msg = f"JSON解析失败: {e}"
                logger.error(error_msg)
                self.stats['failed_requests'] += 1
                return False, "", error_msg
                
        except Exception as e:
            error_msg = f"GPT调用异常: {e}"
            logger.error(error_msg)
            self.stats['failed_requests'] += 1
            return False, "", error_msg
    
    def call_gpt_stream(self, 
                       user_prompt: str, 
                       system_prompt: str = "You are a professional academic translator.",
                       temperature: float = 0.3,
                       max_tokens: int = 4000) -> Tuple[bool, str, str]:
        """
        流式调用GPT
        
        输入参数同call_gpt_sync
        
        输出：返回结果元组
        - success: 是否成功（布尔值）
        - result: 完整的GPT回复内容（字符串）
        - error: 错误信息（字符串，成功时为空）
        
        这个函数使用流式方式调用GPT，可以获得逐步生成的回复
        """
        try:
            self.stats['total_requests'] += 1
            logger.info(f"开始GPT流式调用，模型: {self.model}")
            
            # 构建消息
            messages = self.build_chat_messages(user_prompt, system_prompt)
            
            # 构建请求payload
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": True  # 流式
            }
            
            # 发送流式请求
            response = requests.post(
                self.endpoint,
                headers=self.headers,
                json=payload,
                timeout=self.timeout,
                stream=True
            )
            
            if response.status_code != 200:
                error_msg = f"流式API请求失败，状态码: {response.status_code}"
                logger.error(error_msg)
                self.stats['failed_requests'] += 1
                return False, "", error_msg
            
            # 处理流式响应
            full_content = ""
            for line in response.iter_lines():
                if line:
                    line_text = line.decode('utf-8')
                    
                    # 跳过非数据行
                    if not line_text.startswith('data: '):
                        continue
                    
                    # 检查结束标志
                    if line_text == 'data: [DONE]':
                        break
                    
                    # 解析JSON数据
                    try:
                        json_data = json.loads(line_text[6:])  # 去掉 'data: ' 前缀
                        
                        if 'choices' in json_data and len(json_data['choices']) > 0:
                            delta = json_data['choices'][0].get('delta', {})
                            if 'content' in delta:
                                content_chunk = delta['content']
                                full_content += content_chunk
                                print(content_chunk, end='', flush=True)  # 实时显示
                        
                    except json.JSONDecodeError:
                        continue  # 跳过无法解析的行
            
            print()  # 流式输出结束后换行
            
            if full_content:
                self.stats['successful_requests'] += 1
                logger.info(f"GPT流式调用成功，回复长度: {len(full_content)} 字符")
                return True, full_content, ""
            else:
                error_msg = "流式调用未获得任何内容"
                logger.error(error_msg)
                self.stats['failed_requests'] += 1
                return False, "", error_msg
                
        except Exception as e:
            error_msg = f"GPT流式调用异常: {e}"
            logger.error(error_msg)
            self.stats['failed_requests'] += 1
            return False, "", error_msg
    
    def translate_text(self, 
                      text: str, 
                      target_language: str = "简体中文",
                      source_language: str = "英文",
                      domain: str = "学术论文",
                      stream: bool = False) -> Tuple[bool, str, str]:
        """
        专用翻译方法
        
        输入：
        - text: 要翻译的文本内容，如 "Machine learning is..."
        - target_language: 目标语言，如 "简体中文"
        - source_language: 源语言，如 "英文"
        - domain: 领域，如 "学术论文", "技术文档"
        - stream: 是否使用流式输出，默认False
        
        输出：翻译结果元组
        - success: 是否成功（布尔值）
        - translation: 翻译后的文本（字符串）
        - error: 错误信息（字符串，成功时为空）
        
        这个函数专门用于文本翻译，内置了优化的翻译提示词
        """
        # 构建翻译系统提示词
        system_prompt = f"""你是一位专业的{domain}翻译专家，精通{source_language}和{target_language}。
请将以下{source_language}文本翻译成地道的{target_language}，要求：
1. 保持原文的学术性和专业性
2. 确保术语翻译的准确性和一致性
3. 保持原文的格式和结构
4. 如果遇到LaTeX命令，请保持不变
5. 对于专业术语，可以在首次出现时用括号标注原文"""
        
        # 构建用户提示词
        user_prompt = f"""请将以下{source_language}文本翻译成{target_language}：

{text}

请直接输出翻译结果，不需要额外说明。"""
        
        # 调用相应的GPT方法
        if stream:
            return self.call_gpt_stream(user_prompt, system_prompt)
        else:
            return self.call_gpt_sync(user_prompt, system_prompt)
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取调用统计信息
        
        输入：无
        输出：统计信息字典
        {
            'total_requests': 总请求数,
            'successful_requests': 成功请求数,
            'failed_requests': 失败请求数,
            'success_rate': 成功率,
            'total_tokens_used': 总token使用量
        }
        
        这个函数返回API调用的统计信息，便于监控使用情况
        """
        total = self.stats['total_requests']
        success_rate = (self.stats['successful_requests'] / total * 100) if total > 0 else 0
        
        return {
            'total_requests': total,
            'successful_requests': self.stats['successful_requests'],
            'failed_requests': self.stats['failed_requests'],
            'success_rate': f"{success_rate:.1f}%",
            'total_tokens_used': self.stats['total_tokens_used']
        }

def create_gpt_caller(api_key: str = "",
                     base_url: str = "",
                     model: str = "gpt-4o-mini") -> GPTModelCaller:
    """
    便捷函数：创建GPT调用器
    
    输入：
    - api_key: API密钥
    - base_url: API基础URL
    - model: 模型名称
    
    输出：
    - gpt_caller: GPT调用器实例
    
    这个函数提供最简单的方式创建GPT调用器
    """
    return GPTModelCaller(api_key=api_key, base_url=base_url, model=model)

def translate_latex_segment(text: str, 
                           api_key: str = "",
                           base_url: str = "") -> Tuple[bool, str]:
    """
    便捷函数：翻译单个LaTeX文本段落
    
    输入：
    - text: LaTeX文本段落，如 "\\section{Introduction} Machine learning..."
    - api_key: API密钥
    - base_url: API基础URL
    
    输出：
    - success: 是否成功（布尔值）
    - result: 翻译结果或错误信息（字符串）
    
    这个函数提供最简单的调用方式，一步完成LaTeX段落翻译
    """
    try:
        caller = create_gpt_caller(api_key, base_url)
        success, translation, error = caller.translate_text(text, domain="LaTeX学术论文")
        
        if success:
            return True, translation
        else:
            return False, f"翻译失败: {error}"
            
    except Exception as e:
        return False, f"调用异常: {e}"

# 测试和示例代码
def main():
    """
    测试函数，演示GPT调用器的使用方法
    """
    print("=" * 70)
    print("GPT模型调用器测试")
    print("=" * 70)
    from config import API_KEY, BASE_URL, LLM_MODEL
    # 测试配置
    TEST_API_KEY = API_KEY
    TEST_BASE_URL = BASE_URL
    TEST_MODEL = LLM_MODEL
    
    # 测试文本 - LaTeX格式的英文学术内容
    test_texts = [
        "Machine learning has revolutionized the field of artificial intelligence.",
        
        r"\section{Introduction} Neural networks are computational models inspired by the human brain.",
        
        r"The training process involves adjusting weights to minimize the loss function $L(\theta) = \frac{1}{n}\sum_{i=1}^n \ell(f(x_i; \theta), y_i)$.",
        
        r"\subsection{Deep Learning} Deep learning models have achieved remarkable success in computer vision and natural language processing tasks."
    ]
    
    # 创建GPT调用器
    print("创建GPT调用器...")
    caller = GPTModelCaller(
        api_key=TEST_API_KEY,
        base_url=TEST_BASE_URL,
        model=TEST_MODEL,
        timeout=30,
        max_retries=2
    )
    
    # 测试1: 基础同步调用
    print("\n" + "=" * 50)
    print("测试1: 基础同步调用")
    print("=" * 50)
    
    test_text = test_texts[0]
    print(f"原文: {test_text}")
    
    success, result, error = caller.call_gpt_sync(
        user_prompt=f"请将以下英文翻译成中文：{test_text}",
        system_prompt="你是专业的学术翻译员",
        temperature=0.3
    )
    
    if success:
        print(f"✓ 同步调用成功")
        print(f"译文: {result}")
    else:
        print(f"✗ 同步调用失败: {error}")
    
    # 测试2: 专用翻译方法
    print("\n" + "=" * 50)
    print("测试2: 专用翻译方法")
    print("=" * 50)
    
    for i, test_text in enumerate(test_texts[1:3], 1):  # 测试2个样本
        print(f"\n样本 {i}:")
        print(f"原文: {test_text}")
        
        success, translation, error = caller.translate_text(
            text=test_text,
            target_language="简体中文",
            domain="LaTeX学术论文"
        )
        
        if success:
            print(f"✓ 翻译成功")
            print(f"译文: {translation}")
        else:
            print(f"✗ 翻译失败: {error}")
        
        print("-" * 40)
    
    # 测试3: 流式调用（可选）
    print("\n" + "=" * 50)
    print("测试3: 流式调用")
    print("=" * 50)
    
    test_text = test_texts[-1]
    print(f"原文: {test_text}")
    print("流式输出:")
    
    success, result, error = caller.call_gpt_stream(
        user_prompt=f"请将以下英文翻译成中文：{test_text}",
        system_prompt="你是专业的学术翻译员"
    )
    
    if success:
        print(f"\n✓ 流式调用成功")
        print(f"完整译文: {result}")
    else:
        print(f"\n✗ 流式调用失败: {error}")
    
    # 测试4: 便捷函数
    print("\n" + "=" * 50)
    print("测试4: 便捷函数")
    print("=" * 50)
    
    success, result = translate_latex_segment(
        text="Deep learning models consist of multiple layers of neurons.",
        api_key=TEST_API_KEY,
        base_url=TEST_BASE_URL
    )
    
    if success:
        print(f"✓ 便捷函数调用成功")
        print(f"译文: {result}")
    else:
        print(f"✗ 便捷函数调用失败: {result}")
    
    # 显示统计信息
    print("\n" + "=" * 50)
    print("调用统计信息")
    print("=" * 50)
    
    stats = caller.get_stats()
    for key, value in stats.items():
        print(f"{key}: {value}")
    
    print(f"\n{'='*70}")
    print("测试完成")
    print(f"{'='*70}")

if __name__ == "__main__":
    main()