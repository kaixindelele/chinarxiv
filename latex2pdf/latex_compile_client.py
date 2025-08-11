#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LaTeX编译客户端 - 支持依赖文件传递（修复中文字体问题）

主要功能：
1. 与LaTeX编译服务器通信
2. 发送编译请求并接收结果
3. 支持同步和异步编译模式
4. 支持依赖文件传递和处理
5. 提供健康检查和错误处理
6. 修复中文字体配置问题

输入：LaTeX文档内容和依赖文件
输出：编译后的PDF文件或错误信息

作者：基于GPT Academic项目改进
"""

import requests
import json
import time
import base64
import logging
from typing import Dict, Optional, Any, Union
from pathlib import Path

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class LaTeXCompileClient:
    """
    LaTeX编译客户端类
    
    主要功能：
    1. 管理与编译服务器的连接
    2. 发送编译请求
    3. 处理编译结果
    4. 支持依赖文件传递
    """
    
    def __init__(self, server_url: str = "http://localhost:9851", timeout: int = 300):
        """
        初始化LaTeX编译客户端
        
        输入：
        - server_url: 编译服务器地址，如 "http://localhost:9851"
        - timeout: 请求超时时间（秒），默认300秒
        
        输出：无
        
        这个函数初始化编译客户端，设置服务器连接参数
        """
        self.server_url = server_url.rstrip('/')
        self.timeout = timeout
        
        # API端点
        self.health_endpoint = f"{self.server_url}/health"
        self.compile_sync_endpoint = f"{self.server_url}/compile/sync"
        self.compile_async_endpoint = f"{self.server_url}/compile/async"
        self.status_endpoint = f"{self.server_url}/status"
        
        logger.info(f"LaTeX编译客户端初始化完成")
        logger.info(f"服务器地址: {self.server_url}")
        logger.info(f"超时时间: {self.timeout}秒")
    
    def check_server_health(self) -> bool:
        """
        检查服务器健康状态
        
        输入：无
        输出：服务器是否健康（布尔值）
        
        这个函数检查LaTeX编译服务器是否正常运行
        """
        try:
            print(f"正在检查服务器健康状态: {self.health_endpoint}")
            response = requests.get(self.health_endpoint, timeout=10)
            
            if response.status_code == 200:
                health_data = response.json()
                print(f"✓ 服务器健康检查通过")
                print(f"服务器状态: {health_data}")
                return True
            else:
                print(f"✗ 服务器健康检查失败，状态码: {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            print(f"✗ 服务器健康检查异常: {e}")
            return False
        except Exception as e:
            print(f"✗ 检查服务器健康状态时出错: {e}")
            return False
    
    def _encode_dependencies(self, dependencies: Dict[str, bytes]) -> Dict[str, str]:
        """
        将依赖文件编码为base64格式
        
        输入：
        - dependencies: 依赖文件字典，如 {"file.cls": b"文件内容", "image.pdf": b"图片内容"}
        
        输出：
        - encoded_deps: base64编码后的依赖文件字典，如 {"file.cls": "base64编码字符串"}
        
        这个函数将二进制文件内容编码为base64字符串，便于JSON传输
        """
        try:
            encoded_deps = {}
            for filename, content in dependencies.items():
                if isinstance(content, bytes):
                    encoded_deps[filename] = base64.b64encode(content).decode('utf-8')
                elif isinstance(content, str):
                    # 如果是字符串，先编码为bytes再转base64
                    encoded_deps[filename] = base64.b64encode(content.encode('utf-8')).decode('utf-8')
                else:
                    logger.warning(f"跳过不支持的依赖文件类型: {filename} ({type(content)})")
                    continue
            
            logger.info(f"成功编码 {len(encoded_deps)} 个依赖文件")
            return encoded_deps
            
        except Exception as e:
            logger.error(f"编码依赖文件时出错: {e}")
            return {}
    
    def compile_latex_sync(self, 
                          tex_content: str, 
                          output_name: str = "output",
                          dependencies: Dict[str, bytes] = None) -> Dict[str, Any]:
        """
        同步编译LaTeX文档（支持依赖文件）
        
        输入：
        - tex_content: LaTeX文档内容，如 "\\documentclass{article}\\begin{document}Hello\\end{document}"
        - output_name: 输出文件名，如 "my_document"
        - dependencies: 依赖文件字典，如 {"bmcart.cls": b"类文件内容", "image.pdf": b"图片内容"}
        
        输出：
        - result: 编译结果字典
          {
              'success': bool,           # 是否成功
              'pdf_content': bytes,      # PDF文件内容（成功时）
              'log': str,               # 编译日志
              'error': str              # 错误信息（失败时）
          }
        
        这个函数发送同步编译请求，等待编译完成后返回结果
        """
        try:
            print(f"发送编译请求，输出文件名: {output_name}")
            print(f"LaTeX内容长度: {len(tex_content)} 字符")
            
            # 准备请求数据
            request_data = {
                "tex_content": tex_content,
                "output_name": output_name
            }
            
            # 处理依赖文件
            if dependencies:
                print(f"包含 {len(dependencies)} 个依赖文件")
                encoded_deps = self._encode_dependencies(dependencies)
                request_data["dependencies"] = encoded_deps
                
                # 显示依赖文件信息
                for filename in dependencies.keys():
                    file_size = len(dependencies[filename])
                    print(f"  依赖文件: {filename} ({file_size} 字节)")
            
            # 发送请求
            response = requests.post(
                self.compile_sync_endpoint,
                json=request_data,
                timeout=self.timeout
            )
            
            # 处理响应
            if response.status_code == 200:
                result = response.json()
                
                if result.get('success'):
                    # 编译成功，解码PDF内容
                    pdf_base64 = result.get('pdf_content', '')
                    if pdf_base64:
                        pdf_content = base64.b64decode(pdf_base64)
                        result['pdf_content'] = pdf_content
                        print(f"编译成功，PDF大小: {len(pdf_content)} 字节")
                    else:
                        print("编译成功但未获得PDF内容")
                        result['success'] = False
                        result['error'] = "编译成功但未获得PDF内容"
                else:
                    # 编译失败
                    error_msg = result.get('error', '未知错误')
                    print(f"编译失败: {error_msg}")
                
                return result
                
            else:
                # HTTP请求失败
                error_msg = f"编译请求失败，状态码: {response.status_code}"
                try:
                    error_detail = response.json().get('detail', response.text)
                    error_msg += f"\n错误详情: {error_detail}"
                except:
                    error_msg += f"\n响应内容: {response.text}"
                
                print(f"编译失败，状态码: {response.status_code}")
                print(f"错误信息: {error_detail if 'error_detail' in locals() else response.text}")
                
                return {
                    'success': False,
                    'error': error_msg,
                    'log': ''
                }
                
        except requests.exceptions.Timeout:
            error_msg = f"编译请求超时（{self.timeout}秒）"
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg,
                'log': ''
            }
            
        except requests.exceptions.RequestException as e:
            error_msg = f"编译请求异常: {e}"
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg,
                'log': ''
            }
            
        except Exception as e:
            error_msg = f"编译过程出现异常: {e}"
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg,
                'log': ''
            }
    
    def compile_latex_async(self, 
                           tex_content: str, 
                           output_name: str = "output",
                           dependencies: Dict[str, bytes] = None) -> Dict[str, Any]:
        """
        异步编译LaTeX文档（支持依赖文件）
        
        输入：
        - tex_content: LaTeX文档内容
        - output_name: 输出文件名
        - dependencies: 依赖文件字典
        
        输出：
        - result: 编译任务信息字典
          {
              'success': bool,           # 是否成功提交
              'task_id': str,           # 任务ID（成功时）
              'error': str              # 错误信息（失败时）
          }
        
        这个函数提交异步编译任务，返回任务ID用于后续查询
        """
        try:
            print(f"提交异步编译任务，输出文件名: {output_name}")
            print(f"LaTeX内容长度: {len(tex_content)} 字符")
            
            # 准备请求数据
            request_data = {
                "tex_content": tex_content,
                "output_name": output_name
            }
            
            # 处理依赖文件
            if dependencies:
                print(f"包含 {len(dependencies)} 个依赖文件")
                encoded_deps = self._encode_dependencies(dependencies)
                request_data["dependencies"] = encoded_deps
            
            # 发送请求
            response = requests.post(
                self.compile_async_endpoint,
                json=request_data,
                timeout=30  # 异步提交超时时间较短
            )
            
            # 处理响应
            if response.status_code == 200:
                result = response.json()
                task_id = result.get('task_id')
                print(f"异步编译任务提交成功，任务ID: {task_id}")
                return result
            else:
                error_msg = f"异步编译请求失败，状态码: {response.status_code}"
                try:
                    error_detail = response.json().get('detail', response.text)
                    error_msg += f"\n错误详情: {error_detail}"
                except:
                    error_msg += f"\n响应内容: {response.text}"
                
                print(f"异步编译任务提交失败: {error_msg}")
                return {
                    'success': False,
                    'error': error_msg
                }
                
        except Exception as e:
            error_msg = f"异步编译请求异常: {e}"
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg
            }
    
    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        查询异步编译任务状态
        
        输入：
        - task_id: 任务ID，如 "task_12345"
        
        输出：
        - status: 任务状态字典
          {
              'task_id': str,           # 任务ID
              'status': str,            # 任务状态：pending/running/completed/failed
              'progress': float,        # 进度百分比
              'result': dict           # 编译结果（完成时）
          }
        
        这个函数查询异步编译任务的当前状态和结果
        """
        try:
            response = requests.get(
                f"{self.status_endpoint}/{task_id}",
                timeout=10
            )
            
            if response.status_code == 200:
                status = response.json()
                
                # 如果任务完成且有PDF内容，解码PDF
                if (status.get('status') == 'completed' and 
                    status.get('result', {}).get('success') and 
                    status.get('result', {}).get('pdf_content')):
                    
                    pdf_base64 = status['result']['pdf_content']
                    pdf_content = base64.b64decode(pdf_base64)
                    status['result']['pdf_content'] = pdf_content
                
                return status
            else:
                return {
                    'task_id': task_id,
                    'status': 'error',
                    'error': f"查询失败，状态码: {response.status_code}"
                }
                
        except Exception as e:
            logger.error(f"查询任务状态时出错: {e}")
            return {
                'task_id': task_id,
                'status': 'error',
                'error': str(e)
            }

# 便捷函数
def compile_latex_to_pdf(tex_content: str, 
                        output_name: str = "output",
                        dependencies: Dict[str, bytes] = None,
                        server_url: str = "http://localhost:9851"):
    """
    便捷函数：编译LaTeX为PDF（支持依赖文件）
    
    输入：
    - tex_content: LaTeX文档内容，如 "\\documentclass{article}..."
    - output_name: 输出文件名，如 "my_document"
    - dependencies: 依赖文件字典，如 {"file.cls": b"内容"}
    - server_url: 服务器地址，如 "http://localhost:9851"
    
    输出：
    - success: 是否成功（布尔值）
    - result: 成功时返回PDF内容（bytes），失败时返回错误信息（字符串）
    
    这个函数提供最简单的调用方式，一步完成LaTeX到PDF的编译
    """
    try:
        client = LaTeXCompileClient(server_url)
        
        # 检查服务器状态
        if not client.check_server_health():
            return False, "LaTeX编译服务器不可用"
        
        # 执行编译
        result = client.compile_latex_sync(tex_content, output_name, dependencies)
        
        if result.get('success'):
            return True, result.get('pdf_content')
        else:
            error_msg = result.get('error', '编译失败')
            compile_log = result.get('log', '')
            if compile_log:
                error_msg += f"\n编译日志:\n{compile_log}"
            return False, error_msg
            
    except Exception as e:
        return False, f"编译过程出错: {e}"

def start_latex_server():
    """
    启动LaTeX编译服务器（如果需要）
    
    输入：无
    输出：无
    
    这个函数尝试启动LaTeX编译服务器
    """
    try:
        import subprocess
        import os
        
        # 检查是否已经运行
        client = LaTeXCompileClient()
        if client.check_server_health():
            print("LaTeX编译服务器已经在运行")
            return
        
        # 尝试启动服务器
        current_dir = Path(__file__).parent
        server_script = current_dir / "latex_compile_server.py"
        
        if server_script.exists():
            print("正在启动LaTeX编译服务器...")
            subprocess.Popen([
                "python", str(server_script)
            ], cwd=str(current_dir))
            print("LaTeX编译服务器启动命令已发送")
        else:
            print(f"找不到服务器脚本: {server_script}")
            
    except Exception as e:
        print(f"启动LaTeX编译服务器时出错: {e}")

# 测试和示例代码
def main():
    """
    测试函数，演示LaTeX编译客户端的使用方法（修复中文字体问题）
    """
    print("=" * 70)
    print("LaTeX编译客户端测试（修复中文字体问题）")
    print("=" * 70)
    
    # 创建客户端
    client = LaTeXCompileClient()
    
    # 测试1: 健康检查
    print("\n" + "=" * 50)
    print("测试1: 服务器健康检查")
    print("=" * 50)
    
    if client.check_server_health():
        print("✅ 服务器健康检查通过")
    else:
        print("❌ 服务器健康检查失败，请确保服务器正在运行")
        return
    
    # 测试2: 简单英文文档编译（避免中文字体问题）
    print("\n" + "=" * 50)
    print("测试2: 简单英文文档编译")
    print("=" * 50)
    
    simple_tex = r"""
\documentclass{article}
\usepackage[utf8]{inputenc}

\title{Test Document}
\author{LaTeX Compile Client}
\date{\today}

\begin{document}
\maketitle

\section{Introduction}
This is a test document to verify the LaTeX compilation client functionality.

\section{Mathematical Formula}
Here is a mathematical formula:
\begin{equation}
E = mc^2
\end{equation}

\section{Conclusion}
Compilation test completed successfully.

\end{document}
"""
    
    result = client.compile_latex_sync(simple_tex, "simple_test")
    
    if result.get('success'):
        print("✅ 简单英文文档编译成功")
        pdf_content = result.get('pdf_content')
        if pdf_content:
            output_file = Path("test_simple_output.pdf")
            with open(output_file, 'wb') as f:
                f.write(pdf_content)
            print(f"✓ PDF已保存: {output_file} ({len(pdf_content)} 字节)")
    else:
        print("❌ 简单英文文档编译失败")
        print(f"错误: {result.get('error')}")
        if result.get('log'):
            print(f"日志: {result.get('log')}")
    
    # 测试3: 中文文档编译（使用CJK包）
    print("\n" + "=" * 50)
    print("测试3: 中文文档编译（使用CJK包）")
    print("=" * 50)
    
    chinese_tex = r"""
\documentclass{article}
\usepackage[utf8]{inputenc}
\usepackage{CJK}

\title{Chinese Test Document}
\author{LaTeX Compile Client}
\date{\today}

\begin{document}
\begin{CJK}{UTF8}{gbsn}

\maketitle

\section{介绍}
这是一个中文测试文档，用于验证LaTeX编译客户端的中文支持功能。

\section{数学公式}
这里是一个数学公式：
\begin{equation}
E = mc^2
\end{equation}

\section{结论}
中文编译测试完成。

\end{CJK}
\end{document}
"""
    
    result = client.compile_latex_sync(chinese_tex, "chinese_test")
    
    if result.get('success'):
        print("✅ 中文文档编译成功")
        pdf_content = result.get('pdf_content')
        if pdf_content:
            output_file = Path("test_chinese_output.pdf")
            with open(output_file, 'wb') as f:
                f.write(pdf_content)
            print(f"✓ PDF已保存: {output_file} ({len(pdf_content)} 字节)")
    else:
        print("❌ 中文文档编译失败")
        print(f"错误: {result.get('error')}")
        if result.get('log'):
            print(f"日志: {result.get('log')}")
    
    # 测试4: 带依赖文件的编译
    print("\n" + "=" * 50)
    print("测试4: 带依赖文件的编译")
    print("=" * 50)
    
    # 创建一个简单的自定义类文件（不涉及中文）
    custom_cls = r"""
\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{testclass}[2025/01/01 Test Class]
\LoadClass{article}
\RequirePackage[utf8]{inputenc}

% Custom command
\newcommand{\testcommand}[1]{\textbf{#1}}
"""
    
    # 使用自定义类的文档（英文）
    complex_tex = r"""
\documentclass{testclass}

\title{Test Document with Custom Class}
\author{LaTeX Compile Client}
\date{\today}

\begin{document}
\maketitle

\section{Test Custom Command}
Here we use the custom command: \testcommand{This is bold text}

\section{Conclusion}
Dependency file compilation test completed.

\end{document}
"""
    
    # 准备依赖文件
    dependencies = {
        "testclass.cls": custom_cls.encode('utf-8')
    }
    
    result = client.compile_latex_sync(complex_tex, "complex_test", dependencies)
    
    if result.get('success'):
        print("✅ 带依赖文件的编译成功")
        pdf_content = result.get('pdf_content')
        if pdf_content:
            output_file = Path("test_complex_output.pdf")
            with open(output_file, 'wb') as f:
                f.write(pdf_content)
            print(f"✓ PDF已保存: {output_file} ({len(pdf_content)} 字节)")
    else:
        print("❌ 带依赖文件的编译失败")
        print(f"错误: {result.get('error')}")
        if result.get('log'):
            print(f"日志: {result.get('log')}")
    
    # 测试5: 便捷函数
    print("\n" + "=" * 50)
    print("测试5: 便捷函数接口")
    print("=" * 50)
    
    success, result = compile_latex_to_pdf(simple_tex, "convenience_test")
    
    if success:
        print("✅ 便捷函数测试成功")
        output_file = Path("test_convenience_output.pdf")
        with open(output_file, 'wb') as f:
            f.write(result)
        print(f"✓ PDF已保存: {output_file} ({len(result)} 字节)")
    else:
        print("❌ 便捷函数测试失败")
        print(f"错误: {result}")
    
    print(f"\n{'='*70}")
    print("LaTeX编译客户端测试完成")
    print("说明：如需中文支持，请使用CJK包而不是ctex包")
    print(f"{'='*70}")

if __name__ == "__main__":
    main()
