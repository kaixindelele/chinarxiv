#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Arxiv论文下载器 (优化版)

主要功能：
1. 解析arxiv URL或ID
2. 多重试机制下载arxiv源码tar包
3. 解压到指定目录
4. 处理缓存和重复下载
5. 应对IP限制和网络不稳定

输入：arxiv URL或ID (如: "1812.10695" 或 "https://arxiv.org/abs/1812.10695")
输出：解压后的源码目录路径

作者：基于GPT Academic项目改进，增强版
"""

import os
import re
import time
import random
import requests
import tarfile
import shutil
import hashlib
from pathlib import Path
import logging
from typing import Optional, Tuple, List
from urllib.parse import urlparse
from fake_useragent import UserAgent

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ArxivDownloader:
    """
    Arxiv论文下载器类 (优化版)
    
    主要功能：
    1. 标准化arxiv ID和URL
    2. 多重试机制下载源码包
    3. 解压和目录管理
    4. 智能缓存机制
    5. 应对IP限制
    """
    
    def __init__(self, cache_dir: str = "./arxiv_cache", proxies: dict = None, 
                 timeout: int = 60, max_retries: int = 3):
        """
        初始化下载器
        
        输入：
        - cache_dir: 缓存目录路径，如 "./arxiv_cache"
        - proxies: 代理配置，如 {"http": "http://127.0.0.1:7890", "https": "http://127.0.0.1:7890"}
        - timeout: 下载超时时间（秒），默认60秒
        - max_retries: 最大重试次数，默认3次
        
        输出：无
        
        这个函数初始化下载器，设置缓存目录和网络配置
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.proxies = proxies or {}
        self.timeout = timeout
        self.max_retries = max_retries
        
        # 多个arxiv镜像源，用于应对IP限制
        self.arxiv_mirrors = [
            "https://arxiv.org/e-print/",
            "https://cn.arxiv.org/e-print/",  # 中国镜像
            "https://export.arxiv.org/e-print/",  # 备用源
        ]
        
        # 常用User-Agent池，避免被识别
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:89.0) Gecko/20100101 Firefox/89.0",
        ]
        
        logger.info(f"Arxiv下载器初始化完成 (优化版)")
        logger.info(f"缓存目录: {self.cache_dir}")
        logger.info(f"代理配置: {self.proxies}")
        logger.info(f"最大重试次数: {self.max_retries}")
        logger.info(f"可用镜像源: {len(self.arxiv_mirrors)}个")
        
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
            if arxiv_input.startswith('https://arxiv.org/pdf/') or arxiv_input.startswith('https://cn.arxiv.org/pdf/'):
                # https://arxiv.org/pdf/1812.10695v2.pdf -> 1812.10695
                pdf_name = arxiv_input.split('/')[-1]  # 1812.10695v2.pdf
                arxiv_id = pdf_name.split('v')[0].replace('.pdf', '')  # 1812.10695
                logger.info(f"从PDF链接解析出ID: {arxiv_id}")
                return True, arxiv_id, ""
            
            # 情况2: abs页面链接
            elif arxiv_input.startswith('https://arxiv.org/abs/') or arxiv_input.startswith('https://cn.arxiv.org/abs/'):
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
    
    def _get_random_headers(self) -> dict:
        """
        获取随机请求头，避免被识别为爬虫
        
        输出：
        - headers: 请求头字典
        """
        try:
            # 优先使用fake_useragent
            ua = UserAgent()
            user_agent = ua.random
        except:
            # 如果fake_useragent失败，从预设列表中随机选择
            user_agent = random.choice(self.user_agents)
        
        headers = {
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
        
        return headers
    
    def _add_random_delay(self, min_delay: float = 0.5, max_delay: float = 2.0):
        """
        添加随机延迟，避免请求过于频繁
        
        输入：
        - min_delay: 最小延迟时间（秒）
        - max_delay: 最大延迟时间（秒）
        """
        delay = random.uniform(min_delay, max_delay)
        logger.debug(f"随机延迟 {delay:.2f} 秒")
        time.sleep(delay)
    
    def _verify_file_integrity(self, file_path: str, expected_size: int = None) -> bool:
        """
        验证文件完整性
        
        输入：
        - file_path: 文件路径
        - expected_size: 期望的文件大小（字节）
        
        输出：
        - is_valid: 文件是否完整有效
        """
        try:
            if not os.path.exists(file_path):
                return False
            
            file_size = os.path.getsize(file_path)
            
            # 检查文件大小
            if file_size == 0:
                logger.warning(f"文件为空: {file_path}")
                return False
            
            if expected_size and abs(file_size - expected_size) > 1024:  # 允许1KB误差
                logger.warning(f"文件大小不匹配: 期望{expected_size}, 实际{file_size}")
                return False
            
            # 检查是否为有效的tar文件
            try:
                with tarfile.open(file_path, 'r') as tar:
                    # 尝试读取文件列表
                    members = tar.getnames()
                    if len(members) == 0:
                        logger.warning(f"tar文件为空: {file_path}")
                        return False
            except tarfile.ReadError:
                logger.warning(f"tar文件损坏: {file_path}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"验证文件完整性时出错: {e}")
            return False
    
    def download_arxiv_source(self, arxiv_id: str) -> Tuple[bool, str, str]:
        """
        下载arxiv源码包 (带重试机制)
        
        输入：
        - arxiv_id: 标准化的arxiv ID，如 "1812.10695"
        
        输出：下载结果元组
        - success: 是否下载成功（布尔值）
        - tar_path: tar文件路径（字符串）
        - error_msg: 错误信息（字符串）
        
        这个函数从arxiv服务器下载指定论文的源码tar包，支持多次重试和多镜像源
        """
        # 创建下载目录
        download_dir = self.cache_dir / arxiv_id / "e-print"
        download_dir.mkdir(parents=True, exist_ok=True)
        
        tar_path = download_dir / f"{arxiv_id}.tar"
        
        # 如果已经下载过且文件完整，直接返回
        if tar_path.exists():
            if self._verify_file_integrity(str(tar_path)):
                logger.info(f"tar文件已存在且完整: {tar_path}")
                return True, str(tar_path), ""
            else:
                logger.warning(f"删除损坏的tar文件: {tar_path}")
                tar_path.unlink()
        
        # 开始多重试下载
        last_error = ""
        
        for retry in range(self.max_retries):
            logger.info(f"开始下载 (尝试 {retry + 1}/{self.max_retries}): {arxiv_id}")
            
            # 在重试时添加延迟
            if retry > 0:
                retry_delay = 2 ** retry + random.uniform(0, 1)  # 指数退避 + 随机抖动
                logger.info(f"重试延迟 {retry_delay:.2f} 秒")
                time.sleep(retry_delay)
            
            # 尝试每个镜像源
            for mirror_idx, mirror_base in enumerate(self.arxiv_mirrors):
                try:
                    download_url = f"{mirror_base}{arxiv_id}"
                    headers = self._get_random_headers()
                    
                    logger.info(f"尝试镜像源 {mirror_idx + 1}: {download_url}")
                    logger.debug(f"使用 User-Agent: {headers['User-Agent'][:50]}...")
                    
                    # 添加随机延迟
                    if mirror_idx > 0 or retry > 0:
                        self._add_random_delay(0.5, 1.5)
                    
                    # 发送HEAD请求获取文件信息
                    head_response = requests.head(
                        download_url,
                        proxies=self.proxies,
                        timeout=10,
                        headers=headers
                    )
                    
                    if head_response.status_code != 200:
                        logger.warning(f"HEAD请求失败: {head_response.status_code}")
                        continue
                    
                    expected_size = int(head_response.headers.get('content-length', 0))
                    logger.info(f"文件大小: {expected_size} 字节")
                    
                    # 发送下载请求
                    response = requests.get(
                        download_url, 
                        proxies=self.proxies, 
                        timeout=self.timeout,
                        headers=headers,
                        stream=True
                    )
                    response.raise_for_status()
                    
                    # 保存文件 (优化chunk大小提升速度)
                    downloaded_size = 0
                    chunk_size = 32768  # 32KB chunks for better speed
                    last_progress_log = 0
                    
                    with open(tar_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=chunk_size):
                            if chunk:
                                f.write(chunk)
                                downloaded_size += len(chunk)
                                
                                # 每下载1MB显示一次进度
                                if downloaded_size - last_progress_log >= 1024 * 1024:
                                    if expected_size > 0:
                                        progress = (downloaded_size / expected_size) * 100
                                        logger.info(f"下载进度: {progress:.1f}% ({downloaded_size//1024}KB/{expected_size//1024}KB)")
                                    else:
                                        logger.info(f"已下载: {downloaded_size//1024}KB")
                                    last_progress_log = downloaded_size
                    
                    # 验证下载的文件
                    if self._verify_file_integrity(str(tar_path), expected_size):
                        logger.info(f"下载完成: {tar_path} ({downloaded_size} 字节)")
                        return True, str(tar_path), ""
                    else:
                        logger.error(f"下载的文件不完整，删除并重试")
                        tar_path.unlink()
                        continue
                        
                except requests.exceptions.Timeout as e:
                    last_error = f"下载超时: {e}"
                    logger.warning(f"镜像源 {mirror_idx + 1} 超时: {e}")
                    continue
                    
                except requests.exceptions.HTTPError as e:
                    last_error = f"HTTP错误: {e}"
                    if e.response.status_code == 403:
                        logger.warning(f"镜像源 {mirror_idx + 1} 被禁止访问(403)，可能IP被限制")
                    elif e.response.status_code == 429:
                        logger.warning(f"镜像源 {mirror_idx + 1} 请求过于频繁(429)")
                        time.sleep(5)  # 额外等待
                    else:
                        logger.warning(f"镜像源 {mirror_idx + 1} HTTP错误: {e}")
                    continue
                    
                except requests.exceptions.RequestException as e:
                    last_error = f"请求错误: {e}"
                    logger.warning(f"镜像源 {mirror_idx + 1} 请求失败: {e}")
                    continue
                    
                except Exception as e:
                    last_error = f"未知错误: {e}"
                    logger.error(f"镜像源 {mirror_idx + 1} 未知错误: {e}")
                    continue
            
            logger.warning(f"第 {retry + 1} 次尝试失败，所有镜像源都无法使用")
        
        # 所有重试都失败了
        error_msg = f"下载失败，已重试 {self.max_retries} 次: {last_error}"
        logger.error(error_msg)
        return False, "", error_msg
    
    def extract_tar_file(self, tar_path: str, arxiv_id: str) -> Tuple[bool, str, str]:
        """
        解压tar文件 (增强版)
        
        输入：
        - tar_path: tar文件路径，如 "/cache/1812.10695/e-print/1812.10695.tar"
        - arxiv_id: arxiv ID，如 "1812.10695"
        
        输出：解压结果元组
        - success: 是否解压成功（布尔值）
        - extract_path: 解压目录路径（字符串）
        - error_msg: 错误信息（字符串）
        
        这个函数将下载的tar包解压到指定目录，增加了更好的错误处理
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
            
            # 首先验证tar文件
            if not self._verify_file_integrity(tar_path):
                error_msg = f"tar文件损坏或不完整: {tar_path}"
                logger.error(error_msg)
                return False, "", error_msg
            
            # 解压tar文件 (增强安全性和错误处理)
            extracted_count = 0
            try:
                with tarfile.open(tar_path, 'r') as tar:
                    # 安全检查：防止路径遍历攻击和过大文件
                    def is_safe_member(member):
                        # 检查路径
                        if member.name.startswith('/') or '..' in member.name:
                            return False
                        # 检查文件大小 (限制单个文件最大100MB)
                        if member.size > 100 * 1024 * 1024:
                            logger.warning(f"跳过过大文件: {member.name} ({member.size} bytes)")
                            return False
                        return True
                    
                    safe_members = [m for m in tar.getmembers() if is_safe_member(m)]
                    
                    # 批量解压
                    for member in safe_members:
                        try:
                            tar.extract(member, path=extract_path)
                            extracted_count += 1
                        except Exception as e:
                            logger.warning(f"跳过解压文件 {member.name}: {e}")
                            continue
                    
            except tarfile.ReadError as e:
                error_msg = f"tar文件格式错误: {e}"
                logger.error(error_msg)
                return False, "", error_msg
            
            # 检查解压结果
            extracted_files = list(extract_path.glob("**/*"))
            tex_files = list(extract_path.glob("**/*.tex"))
            
            logger.info(f"解压完成: 成功解压 {extracted_count} 个文件")
            logger.info(f"发现文件: {len(extracted_files)} 个总文件")
            logger.info(f"发现tex文件: {len(tex_files)} 个")
            
            if len(tex_files) == 0:
                # 检查是否有其他类型的文档文件
                doc_files = list(extract_path.glob("**/*.pdf")) + \
                           list(extract_path.glob("**/*.ps")) + \
                           list(extract_path.glob("**/*.dvi"))
                
                if len(doc_files) > 0:
                    logger.warning(f"未找到tex文件，但找到 {len(doc_files)} 个文档文件")
                    # 对于只有PDF等文件的情况，也认为是成功的
                else:
                    error_msg = f"解压后未找到tex或文档文件: {extract_path}"
                    logger.error(error_msg)
                    return False, "", error_msg
            
            # 处理单层文件夹包装的情况
            extract_path = self._handle_folder_wrapper(extract_path)
            
            return True, str(extract_path), ""
            
        except Exception as e:
            error_msg = f"解压过程出错: {e}"
            logger.error(error_msg)
            return False, "", error_msg
    
    def _handle_folder_wrapper(self, extract_path: Path) -> Path:
        """
        处理单层文件夹包装的情况 (增强版)
        
        输入：
        - extract_path: 解压目录路径
        
        输出：
        - final_path: 最终的源码目录路径
        
        这个函数处理arxiv源码被包装在单个文件夹中的情况
        """
        try:
            items = list(extract_path.iterdir())
            # 过滤掉系统文件夹
            items = [item for item in items if item.name not in ['__MACOSX', '.DS_Store', 'Thumbs.db']]
            
            # 如果只有一个文件夹，且没有重要文件在根目录
            if len(items) == 1 and items[0].is_dir():
                root_important_files = list(extract_path.glob("*.tex")) + \
                                     list(extract_path.glob("*.pdf")) + \
                                     list(extract_path.glob("*.bib")) + \
                                     list(extract_path.glob("*.cls")) + \
                                     list(extract_path.glob("*.sty"))
                
                if len(root_important_files) == 0:
                    subfolder = items[0]
                    subfolder_important_files = list(subfolder.glob("**/*.tex")) + \
                                              list(subfolder.glob("**/*.pdf"))
                    
                    if len(subfolder_important_files) > 0:
                        logger.info(f"检测到文件夹包装，使用子文件夹: {subfolder}")
                        return subfolder
            
            return extract_path
            
        except Exception as e:
            logger.warning(f"处理文件夹包装时出错: {e}")
            return extract_path
    
    def download_and_extract(self, arxiv_input: str, use_cache: bool = True) -> Tuple[bool, str, str]:
        """
        完整的下载和解压流程 (增强版)
        
        输入：
        - arxiv_input: arxiv输入，如 "1812.10695" 或 "https://arxiv.org/abs/1812.10695"
        - use_cache: 是否使用缓存，默认True
        
        输出：处理结果元组
        - success: 是否成功（布尔值）
        - extract_path: 解压目录路径（字符串）
        - message: 结果消息（字符串）
        
        这个函数是主要的公共接口，完成从输入到解压的完整流程，支持重试和错误恢复
        """
        print("=" * 60)
        print("开始Arxiv论文下载和解压 (增强版)")
        print("=" * 60)
        
        start_time = time.time()
        
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
                elapsed_time = time.time() - start_time
                print(f"✓ 找到缓存，直接使用: {cache_path}")
                print(f"✓ 总耗时: {elapsed_time:.2f} 秒")
                return True, cache_path, f"使用缓存: {cache_path}"
            print("✓ 未找到缓存，需要下载")
        else:
            print("Step 2: 跳过缓存检查")
        
        # Step 3: 下载源码包 (带重试)
        print(f"Step 3: 下载源码包 (最多重试 {self.max_retries} 次)...")
        success, tar_path, error_msg = self.download_arxiv_source(arxiv_id)
        if not success:
            return False, "", f"下载失败: {error_msg}"
        
        download_time = time.time() - start_time
        print(f"✓ 下载成功: {tar_path}")
        print(f"✓ 下载耗时: {download_time:.2f} 秒")
        
                # Step 4: 解压文件
        print(f"Step 4: 解压文件...")
        success, extract_path, error_msg = self.extract_tar_file(tar_path, arxiv_id)
        if not success:
            return False, "", f"解压失败: {error_msg}"
        
        extract_time = time.time() - start_time
        print(f"✓ 解压成功: {extract_path}")
        print(f"✓ 解压耗时: {extract_time - download_time:.2f} 秒")
        
        # 统计结果
        tex_files = list(Path(extract_path).glob("**/*.tex"))
        pdf_files = list(Path(extract_path).glob("**/*.pdf"))
        bib_files = list(Path(extract_path).glob("**/*.bib"))
        all_files = list(Path(extract_path).glob("**/*"))
        
        print(f"✓ 文件统计:")
        print(f"  - 总文件数: {len(all_files)}")
        print(f"  - tex文件: {len(tex_files)}")
        print(f"  - pdf文件: {len(pdf_files)}")
        print(f"  - bib文件: {len(bib_files)}")
        
        total_time = time.time() - start_time
        print("=" * 60)
        print(f"Arxiv论文下载完成 (总耗时: {total_time:.2f} 秒)")
        print("=" * 60)
        
        return True, extract_path, f"下载解压成功: {extract_path}"
    
    def cleanup_cache(self, arxiv_id: str = None, older_than_days: int = 30):
        """
        清理缓存文件
        
        输入：
        - arxiv_id: 特定的arxiv ID，如果为None则清理所有缓存
        - older_than_days: 清理多少天前的缓存，默认30天
        
        这个函数用于管理缓存空间，删除过期或指定的缓存文件
        """
        try:
            if arxiv_id:
                # 清理特定论文的缓存
                cache_path = self.cache_dir / arxiv_id
                if cache_path.exists():
                    shutil.rmtree(cache_path)
                    logger.info(f"已清理缓存: {arxiv_id}")
                else:
                    logger.info(f"缓存不存在: {arxiv_id}")
            else:
                # 清理过期缓存
                import time
                cutoff_time = time.time() - (older_than_days * 24 * 3600)
                cleaned_count = 0
                
                for item in self.cache_dir.iterdir():
                    if item.is_dir() and item.stat().st_mtime < cutoff_time:
                        shutil.rmtree(item)
                        cleaned_count += 1
                        logger.info(f"已清理过期缓存: {item.name}")
                
                logger.info(f"清理完成，共清理 {cleaned_count} 个过期缓存")
                
        except Exception as e:
            logger.error(f"清理缓存时出错: {e}")
    
    def get_cache_info(self) -> dict:
        """
        获取缓存信息
        
        输出：
        - info: 缓存信息字典
        
        这个函数返回当前缓存的统计信息
        """
        try:
            info = {
                "cache_dir": str(self.cache_dir),
                "total_papers": 0,
                "total_size_mb": 0,
                "papers": []
            }
            
            if not self.cache_dir.exists():
                return info
            
            total_size = 0
            for item in self.cache_dir.iterdir():
                if item.is_dir():
                    paper_info = {
                        "arxiv_id": item.name,
                        "has_extract": (item / "extract").exists(),
                        "has_tar": (item / "e-print").exists(),
                        "size_mb": 0
                    }
                    
                    # 计算大小
                    for root, dirs, files in os.walk(item):
                        for file in files:
                            file_path = os.path.join(root, file)
                            paper_info["size_mb"] += os.path.getsize(file_path)
                    
                    paper_info["size_mb"] = paper_info["size_mb"] / (1024 * 1024)  # 转换为MB
                    total_size += paper_info["size_mb"]
                    
                    info["papers"].append(paper_info)
                    info["total_papers"] += 1
            
            info["total_size_mb"] = round(total_size, 2)
            
            return info
            
        except Exception as e:
            logger.error(f"获取缓存信息时出错: {e}")
            return {"error": str(e)}

def download_arxiv_paper(arxiv_input: str, cache_dir: str = "./arxiv_cache", 
                        proxies: dict = None, use_cache: bool = True, 
                        max_retries: int = 3) -> Tuple[bool, str]:
    """
    便捷函数：下载arxiv论文源码 (增强版)
    
    输入：
    - arxiv_input: arxiv输入，如 "1812.10695" 或完整URL
    - cache_dir: 缓存目录，默认 "./arxiv_cache"
    - proxies: 代理配置，如 {"http": "http://127.0.0.1:7890"}
    - use_cache: 是否使用缓存，默认True
    - max_retries: 最大重试次数，默认3次
    
    输出：
    - success: 是否成功（布尔值）
    - result: 成功时返回解压路径，失败时返回错误信息（字符串）
    
    这个函数提供最简单的调用方式，一步完成arxiv论文的下载和解压
    """
    downloader = ArxivDownloader(
        cache_dir=cache_dir, 
        proxies=proxies, 
        max_retries=max_retries
    )
    success, extract_path, message = downloader.download_and_extract(arxiv_input, use_cache)
    
    if success:
        return True, extract_path
    else:
        return False, message

def batch_download_arxiv_papers(arxiv_list: List[str], cache_dir: str = "./arxiv_cache",
                               proxies: dict = None, max_retries: int = 3,
                               delay_between_downloads: float = 2.0) -> dict:
    """
    批量下载arxiv论文
    
    输入：
    - arxiv_list: arxiv ID或URL列表
    - cache_dir: 缓存目录
    - proxies: 代理配置
    - max_retries: 最大重试次数
    - delay_between_downloads: 下载间隔时间（秒）
    
    输出：
    - results: 批量下载结果字典
    
    这个函数支持批量下载多篇论文，自动管理下载间隔
    """
    results = {
        "total": len(arxiv_list),
        "success": 0,
        "failed": 0,
        "details": []
    }
    
    downloader = ArxivDownloader(
        cache_dir=cache_dir,
        proxies=proxies,
        max_retries=max_retries
    )
    
    print(f"开始批量下载 {len(arxiv_list)} 篇论文...")
    print("=" * 60)
    
    for i, arxiv_input in enumerate(arxiv_list, 1):
        print(f"\n进度: {i}/{len(arxiv_list)} - {arxiv_input}")
        print("-" * 40)
        
        try:
            success, extract_path, message = downloader.download_and_extract(arxiv_input)
            
            result_detail = {
                "arxiv_input": arxiv_input,
                "success": success,
                "extract_path": extract_path if success else "",
                "message": message
            }
            
            results["details"].append(result_detail)
            
            if success:
                results["success"] += 1
                print(f"✅ 成功: {extract_path}")
            else:
                results["failed"] += 1
                print(f"❌ 失败: {message}")
                
        except KeyboardInterrupt:
            print("\n用户中断批量下载")
            break
        except Exception as e:
            results["failed"] += 1
            error_msg = f"批量下载异常: {e}"
            results["details"].append({
                "arxiv_input": arxiv_input,
                "success": False,
                "extract_path": "",
                "message": error_msg
            })
            print(f"❌ 异常: {error_msg}")
        
        # 添加下载间隔（最后一个不需要等待）
        if i < len(arxiv_list):
            print(f"等待 {delay_between_downloads} 秒...")
            time.sleep(delay_between_downloads)
    
    print("\n" + "=" * 60)
    print(f"批量下载完成:")
    print(f"  总数: {results['total']}")
    print(f"  成功: {results['success']}")
    print(f"  失败: {results['failed']}")
    print(f"  成功率: {results['success']/results['total']*100:.1f}%")
    print("=" * 60)
    
    return results

# 测试和示例代码
def main():
    """
    测试函数，演示增强版下载器的使用方法
    """
    print("=" * 70)
    print("Arxiv下载器测试 (增强版)")
    print("=" * 70)
    
    # 测试用例
    test_cases = [
        "1812.10695",  # 经典论文ID - BERT
        "https://arxiv.org/abs/2508.06309",  # Transformer论文
        # "https://arxiv.org/pdf/2303.02210",  # InstructGPT
        "2402.14207",  # 最新论文
    ]
    
    # 代理配置（如果需要）
    proxies = {
        # "http": "http://127.0.0.1:7890",
        # "https": "http://127.0.0.1:7890"
    }
    
    # 创建增强版下载器
    downloader = ArxivDownloader(
        cache_dir="./test_arxiv_cache",  # 测试时使用独立目录
        proxies=proxies,  # 如果不需要代理，设为None
        timeout=120,  # 增加超时时间
        max_retries=3  # 最大重试3次
    )
    
    # 测试单个下载
    print("\n" + "="*50)
    print("测试单个下载功能")
    print("="*50)
    
    test_input = test_cases[0]  # 测试第一个用例
    try:
        success, extract_path, message = downloader.download_and_extract(
            test_input, 
            use_cache=True
        )
        
        if success:
            print(f"✅ 单个下载测试通过")
            print(f"解压路径: {extract_path}")
            
            # 显示详细文件统计
            path_obj = Path(extract_path)
            tex_files = list(path_obj.glob("**/*.tex"))
            pdf_files = list(path_obj.glob("**/*.pdf"))
            bib_files = list(path_obj.glob("**/*.bib"))
            
            print(f"文件详情:")
            print(f"  - tex文件: {len(tex_files)}")
            print(f"  - pdf文件: {len(pdf_files)}")  
            print(f"  - bib文件: {len(bib_files)}")
            
            if tex_files:
                print(f"主要tex文件:")
                for tex_file in tex_files[:3]:
                    rel_path = tex_file.relative_to(path_obj)
                    size_kb = tex_file.stat().st_size // 1024
                    print(f"    - {rel_path} ({size_kb}KB)")
        else:
            print(f"❌ 单个下载测试失败: {message}")
            
    except Exception as e:
        print(f"❌ 单个下载测试异常: {e}")
    
    # 测试批量下载
    print(f"\n" + "="*50)
    print("测试批量下载功能")
    print("="*50)
    
    batch_test_cases = test_cases[:2]  # 只测试前2个，避免测试时间过长
    
    try:
        results = batch_download_arxiv_papers(
            arxiv_list=batch_test_cases,
            cache_dir="./test_arxiv_cache",  # 测试时使用独立目录
            proxies=proxies,
            max_retries=2,  # 测试时减少重试次数
            delay_between_downloads=1.0  # 测试时减少等待时间
        )
        
        print(f"\n批量下载结果:")
        for detail in results["details"]:
            status = "✅" if detail["success"] else "❌"
            print(f"{status} {detail['arxiv_input']}: {detail['message'][:50]}")
            
    except Exception as e:
        print(f"❌ 批量下载测试异常: {e}")
    
    # 测试缓存管理
    print(f"\n" + "="*50)
    print("测试缓存管理功能")
    print("="*50)
    
    try:
        cache_info = downloader.get_cache_info()
        print(f"缓存统计:")
        print(f"  - 缓存目录: {cache_info['cache_dir']}")
        print(f"  - 论文数量: {cache_info['total_papers']}")
        print(f"  - 总大小: {cache_info['total_size_mb']:.2f} MB")
        
        if cache_info['papers']:
            print(f"缓存详情:")
            for paper in cache_info['papers'][:3]:  # 只显示前3个
                status = "✓" if paper['has_extract'] else "✗"
                print(f"    {status} {paper['arxiv_id']}: {paper['size_mb']:.2f} MB")
                
    except Exception as e:
        print(f"❌ 缓存管理测试异常: {e}")
    
    print(f"\n" + "="*70)
    print("所有测试完成")
    print("="*70)

if __name__ == "__main__":
    main()