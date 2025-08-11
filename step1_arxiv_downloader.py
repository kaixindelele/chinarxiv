#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Arxiv论文下载器

主要功能：
1. 解析arxiv URL或ID
2. 下载arxiv源码tar包
3. 解压到指定目录
4. 处理缓存和重复下载

输入：arxiv URL或ID (如: "1812.10695" 或 "https://arxiv.org/abs/1812.10695")
输出：解压后的源码目录路径

作者：基于GPT Academic项目改进
"""

import os
import re
import time
import requests
import tarfile
import shutil
from pathlib import Path
import logging
from typing import Optional, Tuple
from urllib.parse import urlparse

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ArxivDownloader:
    """
    Arxiv论文下载器类
    
    主要功能：
    1. 标准化arxiv ID和URL
    2. 下载源码包
    3. 解压和目录管理
    4. 缓存机制
    """
    
    def __init__(self, cache_dir: str = "./arxiv_cache", proxies: dict = None, timeout: int = 60):
        """
        初始化下载器
        
        输入：
        - cache_dir: 缓存目录路径，如 "./arxiv_cache"
        - proxies: 代理配置，如 {"http": "http://127.0.0.1:7890", "https": "http://127.0.0.1:7890"}
        - timeout: 下载超时时间（秒），默认60秒
        
        输出：无
        
        这个函数初始化下载器，设置缓存目录和网络配置
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.proxies = proxies or {}
        self.timeout = timeout
        
        logger.info(f"Arxiv下载器初始化完成")
        logger.info(f"缓存目录: {self.cache_dir}")
        logger.info(f"代理配置: {self.proxies}")
        
    def parse_arxiv_input(self, arxiv_input: str) -> Tuple[bool, str, str]:
        """
        解析arxiv输入，提取标准ID
        
        输入：
        - arxiv_input: arxiv输入，可能是ID或URL
          示例: "1812.10695", "1812.10695v2", "https://arxiv.org/abs/1812.10695"
        
        输出：解析结果元组
        - success: 是否解析成功（布尔值）
        - arxiv_id: 标准化的arxiv ID（字符串），如 "1812.10695"
        - error_msg: 错误信息（字符串）
        
        这个函数将各种格式的arxiv输入标准化为统一的ID格式
        """
        try:
            arxiv_input = arxiv_input.strip()
            logger.info(f"解析arxiv输入: {arxiv_input}")
            
            # 情况1: 直接是PDF链接
            if arxiv_input.startswith('https://arxiv.org/pdf/'):
                # https://arxiv.org/pdf/1812.10695v2.pdf -> 1812.10695
                pdf_name = arxiv_input.split('/')[-1]  # 1812.10695v2.pdf
                arxiv_id = pdf_name.split('v')[0].replace('.pdf', '')  # 1812.10695
                logger.info(f"从PDF链接解析出ID: {arxiv_id}")
                return True, arxiv_id, ""
            
            # 情况2: abs页面链接
            elif arxiv_input.startswith('https://arxiv.org/abs/'):
                # https://arxiv.org/abs/1812.10695 -> 1812.10695
                arxiv_id = arxiv_input.split('/abs/')[-1]
                if 'v' in arxiv_id:
                    arxiv_id = arxiv_id.split('v')[0]  # 去掉版本号
                logger.info(f"从abs链接解析出ID: {arxiv_id}")
                return True, arxiv_id, ""
            
            # 情况3: 纯ID格式
            elif re.match(r'^\d{4}\.\d{4,5}(v\d+)?$', arxiv_input):
                # 1812.10695 或 1812.10695v2 -> 1812.10695
                arxiv_id = arxiv_input.split('v')[0]
                logger.info(f"解析纯ID: {arxiv_id}")
                return True, arxiv_id, ""
            
            # 情况4: 新格式ID (如 cs.AI/0301001)
            elif re.match(r'^[a-z-]+(\.[A-Z]{2})?/\d{7}(v\d+)?$', arxiv_input):
                arxiv_id = arxiv_input.split('v')[0]
                logger.info(f"解析新格式ID: {arxiv_id}")
                return True, arxiv_id, ""
            
            else:
                error_msg = f"无法识别的arxiv格式: {arxiv_input}"
                logger.error(error_msg)
                return False, "", error_msg
                
        except Exception as e:
            error_msg = f"解析arxiv输入时出错: {e}"
            logger.error(error_msg)
            return False, "", error_msg
    
    def check_cache(self, arxiv_id: str) -> Optional[str]:
        """
        检查缓存中是否已有该论文
        
        输入：
        - arxiv_id: 标准化的arxiv ID，如 "1812.10695"
        
        输出：
        - cache_path: 缓存目录路径（字符串）或None
        
        这个函数检查指定论文是否已经下载并解压到缓存中
        """
        cache_path = self.cache_dir / arxiv_id / "extract"
        
        if cache_path.exists() and cache_path.is_dir():
            # 检查是否有tex文件
            tex_files = list(cache_path.glob("**/*.tex"))
            if len(tex_files) > 0:
                logger.info(f"找到缓存: {cache_path}")
                logger.info(f"包含 {len(tex_files)} 个tex文件")
                return str(cache_path)
        
        logger.info(f"未找到缓存: {arxiv_id}")
        return None
    
    def download_arxiv_source(self, arxiv_id: str) -> Tuple[bool, str, str]:
        """
        下载arxiv源码包
        
        输入：
        - arxiv_id: 标准化的arxiv ID，如 "1812.10695"
        
        输出：下载结果元组
        - success: 是否下载成功（布尔值）
        - tar_path: tar文件路径（字符串）
        - error_msg: 错误信息（字符串）
        
        这个函数从arxiv服务器下载指定论文的源码tar包
        """
        try:
            # 创建下载目录
            download_dir = self.cache_dir / arxiv_id / "e-print"
            download_dir.mkdir(parents=True, exist_ok=True)
            
            tar_path = download_dir / f"{arxiv_id}.tar"
            
            # 如果已经下载过，直接返回
            if tar_path.exists() and tar_path.stat().st_size > 0:
                logger.info(f"tar文件已存在: {tar_path}")
                return True, str(tar_path), ""
            
            # 构建下载URL
            download_url = f"https://arxiv.org/e-print/{arxiv_id}"
            logger.info(f"开始下载: {download_url}")
            
            # 发送下载请求
            response = requests.get(
                download_url, 
                proxies=self.proxies, 
                timeout=self.timeout,
                stream=True
            )
            response.raise_for_status()
            
            # 保存文件
            total_size = int(response.headers.get('content-length', 0))
            downloaded_size = 0
            
            with open(tar_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        
                        # 显示下载进度
                        if total_size > 0:
                            progress = (downloaded_size / total_size) * 100
                            if downloaded_size % (1024 * 100) == 0:  # 每100KB显示一次
                                logger.info(f"下载进度: {progress:.1f}% ({downloaded_size}/{total_size} 字节)")
            
            logger.info(f"下载完成: {tar_path} ({downloaded_size} 字节)")
            return True, str(tar_path), ""
            
        except requests.exceptions.Timeout:
            error_msg = f"下载超时: {arxiv_id}"
            logger.error(error_msg)
            return False, "", error_msg
            
        except requests.exceptions.RequestException as e:
            error_msg = f"下载请求失败: {e}"
            logger.error(error_msg)
            return False, "", error_msg
            
        except Exception as e:
            error_msg = f"下载过程出错: {e}"
            logger.error(error_msg)
            return False, "", error_msg
    
    def extract_tar_file(self, tar_path: str, arxiv_id: str) -> Tuple[bool, str, str]:
        """
        解压tar文件
        
        输入：
        - tar_path: tar文件路径，如 "/cache/1812.10695/e-print/1812.10695.tar"
        - arxiv_id: arxiv ID，如 "1812.10695"
        
        输出：解压结果元组
        - success: 是否解压成功（布尔值）
        - extract_path: 解压目录路径（字符串）
        - error_msg: 错误信息（字符串）
        
        这个函数将下载的tar包解压到指定目录
        """
        try:
            extract_path = self.cache_dir / arxiv_id / "extract"
            
            # 如果已经解压过，检查是否完整
            if extract_path.exists():
                tex_files = list(extract_path.glob("**/*.tex"))
                if len(tex_files) > 0:
                    logger.info(f"解压目录已存在且包含tex文件: {extract_path}")
                    return True, str(extract_path), ""
                else:
                    # 删除不完整的解压目录
                    shutil.rmtree(extract_path)
                    logger.info(f"删除不完整的解压目录: {extract_path}")
            
            extract_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"开始解压: {tar_path} -> {extract_path}")
            
            # 解压tar文件
            with tarfile.open(tar_path, 'r') as tar:
                # 安全检查：防止路径遍历攻击
                def is_safe_path(path):
                    return not (path.startswith('/') or '..' in path)
                
                safe_members = [m for m in tar.getmembers() if is_safe_path(m.name)]
                tar.extractall(path=extract_path, members=safe_members)
            
            # 检查解压结果
            extracted_files = list(extract_path.glob("**/*"))
            tex_files = list(extract_path.glob("**/*.tex"))
            
            logger.info(f"解压完成: {len(extracted_files)} 个文件")
            logger.info(f"包含 {len(tex_files)} 个tex文件")
            
            if len(tex_files) == 0:
                error_msg = f"解压后未找到tex文件: {extract_path}"
                logger.error(error_msg)
                return False, "", error_msg
            
            # 处理单层文件夹包装的情况
            extract_path = self._handle_folder_wrapper(extract_path)
            
            return True, str(extract_path), ""
            
        except tarfile.ReadError as e:
            error_msg = f"tar文件格式错误: {e}"
            logger.error(error_msg)
            return False, "", error_msg
            
        except Exception as e:
            error_msg = f"解压过程出错: {e}"
            logger.error(error_msg)
            return False, "", error_msg
    
    def _handle_folder_wrapper(self, extract_path: Path) -> Path:
        """
        处理单层文件夹包装的情况
        
        输入：
        - extract_path: 解压目录路径
        
        输出：
        - final_path: 最终的源码目录路径
        
        这个函数处理arxiv源码被包装在单个文件夹中的情况
        """
        try:
            items = list(extract_path.iterdir())
            # 过滤掉macOS的__MACOSX文件夹
            items = [item for item in items if item.name != '__MACOSX']
            
            # 如果只有一个文件夹，且没有tex文件在根目录
            if len(items) == 1 and items[0].is_dir():
                root_tex_files = list(extract_path.glob("*.tex"))
                if len(root_tex_files) == 0:
                    subfolder = items[0]
                    subfolder_tex_files = list(subfolder.glob("**/*.tex"))
                    if len(subfolder_tex_files) > 0:
                        logger.info(f"检测到文件夹包装，使用子文件夹: {subfolder}")
                        return subfolder
            
            return extract_path
            
        except Exception as e:
            logger.warning(f"处理文件夹包装时出错: {e}")
            return extract_path
    
    def download_and_extract(self, arxiv_input: str, use_cache: bool = True) -> Tuple[bool, str, str]:
        """
        完整的下载和解压流程
        
        输入：
        - arxiv_input: arxiv输入，如 "1812.10695" 或 "https://arxiv.org/abs/1812.10695"
        - use_cache: 是否使用缓存，默认True
        
        输出：处理结果元组
        - success: 是否成功（布尔值）
        - extract_path: 解压目录路径（字符串）
        - message: 结果消息（字符串）
        
        这个函数是主要的公共接口，完成从输入到解压的完整流程
        """
        print("=" * 60)
        print("开始Arxiv论文下载和解压")
        print("=" * 60)
        
        # Step 1: 解析输入
        print(f"Step 1: 解析arxiv输入...")
        success, arxiv_id, error_msg = self.parse_arxiv_input(arxiv_input)
        if not success:
            return False, "", f"输入解析失败: {error_msg}"
        
        print(f"✓ 解析成功，arxiv ID: {arxiv_id}")
        
        # Step 2: 检查缓存
        if use_cache:
            print(f"Step 2: 检查缓存...")
            cache_path = self.check_cache(arxiv_id)
            if cache_path:
                print(f"✓ 找到缓存，直接使用: {cache_path}")
                return True, cache_path, f"使用缓存: {cache_path}"
            print("✓ 未找到缓存，需要下载")
        else:
            print("Step 2: 跳过缓存检查")
        
        # Step 3: 下载源码包
        print(f"Step 3: 下载源码包...")
        success, tar_path, error_msg = self.download_arxiv_source(arxiv_id)
        if not success:
            return False, "", f"下载失败: {error_msg}"
        
        print(f"✓ 下载成功: {tar_path}")
        
        # Step 4: 解压文件
        print(f"Step 4: 解压文件...")
        success, extract_path, error_msg = self.extract_tar_file(tar_path, arxiv_id)
        if not success:
            return False, "", f"解压失败: {error_msg}"
        
        print(f"✓ 解压成功: {extract_path}")
        
        # 统计结果
        tex_files = list(Path(extract_path).glob("**/*.tex"))
        print(f"✓ 发现 {len(tex_files)} 个tex文件")
        
        print("=" * 60)
        print("Arxiv论文下载完成")
        print("=" * 60)
        
        return True, extract_path, f"下载解压成功: {extract_path}"

def download_arxiv_paper(arxiv_input: str, cache_dir: str = "./arxiv_cache", 
                        proxies: dict = None, use_cache: bool = True) -> Tuple[bool, str]:
    """
    便捷函数：下载arxiv论文源码
    
    输入：
    - arxiv_input: arxiv输入，如 "1812.10695" 或完整URL
    - cache_dir: 缓存目录，默认 "./arxiv_cache"
    - proxies: 代理配置，如 {"http": "http://127.0.0.1:7890"}
    - use_cache: 是否使用缓存，默认True
    
    输出：
    - success: 是否成功（布尔值）
    - result: 成功时返回解压路径，失败时返回错误信息（字符串）
    
    这个函数提供最简单的调用方式，一步完成arxiv论文的下载和解压
    """
    downloader = ArxivDownloader(cache_dir=cache_dir, proxies=proxies)
    success, extract_path, message = downloader.download_and_extract(arxiv_input, use_cache)
    
    if success:
        return True, extract_path
    else:
        return False, message

# 测试和示例代码
def main():
    """
    测试函数，演示下载器的使用方法
    """
    print("=" * 70)
    print("Arxiv下载器测试")
    print("=" * 70)
    
    # 测试用例
    test_cases = [
        "1812.10695",  # 经典论文ID
        "https://arxiv.org/abs/1812.10695",  # abs链接
        "https://arxiv.org/pdf/1812.10695.pdf",  # pdf链接
        "2402.14207",  # 另一个论文ID
    ]
    
    # 代理配置（如果需要）
    proxies = {
        "http": "http://127.0.0.1:7890",
        "https": "http://127.0.0.1:7890"
    }
    
    # 创建下载器
    downloader = ArxivDownloader(
        cache_dir="./test_arxiv_cache",
        proxies=None,  # 如果不需要代理，设为None
        timeout=60
    )
    
    # 测试每个用例
    for i, test_input in enumerate(test_cases, 1):
        print(f"\n{'='*50}")
        print(f"测试 {i}/{len(test_cases)}: {test_input}")
        print(f"{'='*50}")
        
        try:
            success, extract_path, message = downloader.download_and_extract(
                test_input, 
                use_cache=True
            )
            
            if success:
                print(f"✅ 测试通过")
                print(f"解压路径: {extract_path}")
                
                # 显示文件统计
                path_obj = Path(extract_path)
                tex_files = list(path_obj.glob("**/*.tex"))
                all_files = list(path_obj.glob("**/*"))
                
                print(f"文件统计:")
                print(f"  - 总文件数: {len(all_files)}")
                print(f"  - tex文件数: {len(tex_files)}")
                
                if len(tex_files) > 0:
                    print(f"主要tex文件:")
                    for tex_file in tex_files[:3]:  # 只显示前3个
                        relative_path = tex_file.relative_to(path_obj)
                        print(f"    - {relative_path}")
                    if len(tex_files) > 3:
                        print(f"    - ... 还有 {len(tex_files)-3} 个文件")
            else:
                print(f"❌ 测试失败: {message}")
                
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
