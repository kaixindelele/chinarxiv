"""
BabelDoc API 客户端示例
展示如何调用 babeldoc_server.py 提供的 API
"""

import requests
import json
import sys
from pathlib import Path
try:
    import tomli as tomllib  # Python < 3.11
except ImportError:
    import tomllib  # Python >= 3.11


def load_config(config_path: str = None) -> dict:
    """
    加载 TOML 配置文件
    
    Args:
        config_path: 配置文件路径，如果为 None 则使用默认路径
        
    Returns:
        配置字典，如果文件不存在或解析失败则返回空字典
    """
    if config_path is None:
        # 默认配置文件路径：babeldoc/babeldoc_config.toml
        config_path = Path(__file__).parent / "babeldoc_config.toml"
    else:
        config_path = Path(config_path)
    
    if not config_path.exists():
        print(f"[警告] 配置文件不存在: {config_path}")
        return {}
    
    try:
        with open(config_path, 'rb') as f:
            config = tomllib.load(f)
        
        # 返回 babeldoc 部分的配置
        return config.get('babeldoc', {})
    except Exception as e:
        print(f"[警告] 加载配置文件失败: {e}")
        return {}


def merge_config_with_params(config: dict, **kwargs) -> dict:
    """
    合并配置文件和函数参数
    
    优先级：函数参数 > 配置文件
    
    Args:
        config: 从配置文件加载的配置字典
        **kwargs: 函数参数
        
    Returns:
        合并后的参数字典
    """
    # 配置文件中的键名映射到 API 参数名
    key_mapping = {
        'lang-in': 'lang_in',
        'lang-out': 'lang_out',
        'openai-model': 'openai_model',
        'openai-base-url': 'openai_base_url',
        'openai-api-key': 'openai_api_key',
        'glossary-files': 'glossary_files',
        'max-pages-per-part': 'max_pages_per_part',
        'no-dual': 'no_dual',
        'no-mono': 'no_mono',
    }
    
    # 从配置文件中提取参数
    params = {}
    for config_key, api_key in key_mapping.items():
        if config_key in config:
            params[api_key] = config[config_key]
    
    # 直接映射的参数
    direct_keys = ['qps', 'output']
    for key in direct_keys:
        if key in config:
            if key == 'output':
                params['output_dir'] = config[key]
            else:
                params[key] = config[key]
    
    # 函数参数覆盖配置文件
    params.update({k: v for k, v in kwargs.items() if v is not None})
    
    return params


def translate_stream(pdf_path: str, output_dir: str = None, config_path: str = None, **kwargs):
    """
    使用流式 API 翻译 PDF（推荐使用）
    
    Args:
        pdf_path: PDF 文件路径
        output_dir: 输出目录（可选，如果不指定则使用配置文件中的设置）
        config_path: 配置文件路径（可选，默认使用 babeldoc/babeldoc_config.toml）
        **kwargs: 其他参数，会覆盖配置文件中的设置
    """
    url = "http://localhost:8321/translate/stream"
    
    # 加载配置文件
    config = load_config(config_path)
    
    # 合并配置和参数
    params = merge_config_with_params(
        config,
        pdf_path=pdf_path,
        output_dir=output_dir,
        **kwargs
    )
    
    # 确保 pdf_path 存在
    if 'pdf_path' not in params:
        params['pdf_path'] = pdf_path
    
    payload = params
    
    print(f"开始翻译: {pdf_path}")
    print(f"输出目录: {payload.get('output_dir', 'babeldoc_output')}")
    if config:
        print(f"[配置] 已加载配置文件")
    print("-" * 80)
    
    try:
        # 发送 POST 请求，使用 stream=True 接收流式响应
        response = requests.post(url, json=payload, stream=True, timeout=3600)
        
        if response.status_code != 200:
            print(f"错误: HTTP {response.status_code}")
            print(response.text)
            return None
        
        pdf_paths = []
        
        # 逐行读取 SSE 响应
        for line in response.iter_lines():
            if not line:
                continue
                
            line_str = line.decode('utf-8')
            
            # SSE 格式: "data: {...}"
            if line_str.startswith("data: "):
                data_str = line_str[6:]  # 去掉 "data: " 前缀
                
                try:
                    data = json.loads(data_str)
                    msg_type = data.get("type", "unknown")
                    
                    if msg_type == "log":
                        # 普通日志
                        print(data.get("message", ""))
                    
                    elif msg_type == "info":
                        # 信息消息
                        print(f"[INFO] {data.get('message', '')}")
                        if "command" in data:
                            print(f"[CMD] {data['command']}")
                    
                    elif msg_type == "success":
                        # 成功消息
                        print("\n" + "=" * 80)
                        print(f"✓ {data.get('message', '成功')}")
                        pdf_paths = data.get("pdf_paths", [])
                        if pdf_paths:
                            print("\n生成的 PDF 文件:")
                            for path in pdf_paths:
                                print(f"  - {path}")
                        print("=" * 80)
                    
                    elif msg_type == "error":
                        # 错误消息
                        print(f"\n✗ 错误: {data.get('message', '未知错误')}")
                    
                    elif msg_type == "done":
                        # 完成标记
                        print("\n传输完成")
                        
                except json.JSONDecodeError:
                    print(f"无法解析 JSON: {data_str}")
        
        return pdf_paths
        
    except requests.exceptions.RequestException as e:
        print(f"请求错误: {e}")
        return None


def translate_sync(pdf_path: str, output_dir: str = None, config_path: str = None, **kwargs):
    """
    使用同步 API 翻译 PDF（等待完成后返回）
    
    Args:
        pdf_path: PDF 文件路径
        output_dir: 输出目录（可选，如果不指定则使用配置文件中的设置）
        config_path: 配置文件路径（可选，默认使用 babeldoc/babeldoc_config.toml）
        **kwargs: 其他参数，会覆盖配置文件中的设置
    """
    url = "http://localhost:8321/translate"
    
    # 加载配置文件
    config = load_config(config_path)
    
    # 合并配置和参数
    params = merge_config_with_params(
        config,
        pdf_path=pdf_path,
        output_dir=output_dir,
        **kwargs
    )
    
    # 确保 pdf_path 存在
    if 'pdf_path' not in params:
        params['pdf_path'] = pdf_path
    
    payload = params
    
    print(f"开始翻译: {pdf_path}")
    print(f"输出目录: {payload.get('output_dir', 'babeldoc_output')}")
    if config:
        print(f"[配置] 已加载配置文件")
    print("等待翻译完成（这可能需要几分钟）...")
    print("-" * 80)
    
    try:
        response = requests.post(url, json=payload, timeout=3600)
        
        if response.status_code != 200:
            print(f"错误: HTTP {response.status_code}")
            print(response.text)
            return None
        
        result = response.json()
        
        print("\n" + "=" * 80)
        if result["success"]:
            print(f"✓ {result['message']}")
            
            if result.get("pdf_paths"):
                print("\n生成的 PDF 文件:")
                for path in result["pdf_paths"]:
                    print(f"  - {path}")
            
            if result.get("total_time"):
                print(f"\n总耗时: {result['total_time']:.2f} 秒")
        else:
            print(f"✗ {result['message']}")
            if result.get("error"):
                print(f"\n错误详情:\n{result['error']}")
        
        print("=" * 80)
        
        return result.get("pdf_paths", [])
        
    except requests.exceptions.RequestException as e:
        print(f"请求错误: {e}")
        return None


def check_server_health():
    """检查服务器状态"""
    url = "http://localhost:8321/health"
    
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✓ 服务器运行正常")
            print(f"  状态: {data.get('status')}")
            print(f"  时间: {data.get('timestamp')}")
            return True
        else:
            print(f"✗ 服务器响应异常: HTTP {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"✗ 无法连接到服务器: {e}")
        print("\n请确保服务器已启动:")
        print("  python babeldoc/babeldoc_server.py")
        return False


def main():
    """主函数"""
    print("BabelDoc API 客户端示例")
    print("=" * 80)
    
    # 检查服务器状态
    print("\n1. 检查服务器状态...")
    if not check_server_health():
        sys.exit(1)
    
    # 设置 PDF 路径（修改为你的实际路径）
    pdf_path = "babeldoc/2510-20817.pdf"
    output_dir = "/home/lyl/academic/chinarxiv/babeldoc_output"  # 使用绝对路径，覆盖配置文件
    no_dual = True  # 默认不生成双语PDF
    
    print("\n2. 选择翻译方式:")
    print("   a) 流式翻译（推荐，实时显示进度）")
    print("   b) 同步翻译（等待完成后返回）")
    
    choice = input("\n请选择 (a/b，默认 a): ").strip().lower()
    
    print("\n3. 开始翻译...")
    print("-" * 80)
    
    if choice == "b":
        # 同步翻译
        pdf_paths = translate_sync(pdf_path, output_dir=output_dir, no_dual=no_dual)
    else:
        # 流式翻译（默认）
        pdf_paths = translate_stream(pdf_path, output_dir=output_dir, no_dual=no_dual)
    
    if pdf_paths:
        print(f"\n✓ 翻译成功！生成了 {len(pdf_paths)} 个 PDF 文件。")
        # 打印出pdf_paths
        for path in pdf_paths:
            print(f"  - {path}")
    else:
        print("\n✗ 翻译失败或未生成文件。")


if __name__ == "__main__":
    main()

