#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LaTeX翻译缓存管理器

主要功能：
1. 管理翻译缓存的存储和读取
2. 按arxiv_id组织缓存文件
3. 支持段落级别的缓存更新
4. 提供缓存命中率统计
5. 自动处理缓存文件的创建和维护

输入：arxiv_id, 段落索引, 原文, 翻译内容
输出：缓存的翻译内容或更新状态

作者：基于GPT Academic项目改进
"""

import json
import os
import time
import hashlib
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TranslationCache:
    """
    翻译缓存管理器类
    
    主要功能：
    1. 管理arxiv论文的翻译缓存
    2. 支持段落级别的缓存存储和检索
    3. 提供缓存统计和维护功能
    4. 确保缓存数据的完整性和一致性
    """
    
    def __init__(self, cache_dir: str = "./arxiv_cache"):
        """
        初始化翻译缓存管理器
        
        输入：
        - cache_dir: 缓存根目录路径，如 "./arxiv_cache"
        
        输出：无
        
        这个函数初始化缓存管理器，设置缓存目录和统计信息
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        
        # 缓存统计信息
        self.cache_stats = {
            'total_requests': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'cache_updates': 0,
            'last_access_time': None
        }
        
        logger.info(f"翻译缓存管理器初始化完成")
        logger.info(f"缓存目录: {self.cache_dir}")
    
    def _get_cache_file_path(self, arxiv_id: str) -> Path:
        """
        获取指定arxiv论文的缓存文件路径
        
        输入：
        - arxiv_id: arxiv论文ID，如 "2402.14207"
        
        输出：
        - cache_file_path: 缓存文件路径，如 "./arxiv_cache/2402.14207/translation/2402.14207_trans_cache.json"
        
        这个函数根据arxiv_id构建标准的缓存文件路径
        """
        translation_dir = self.cache_dir / arxiv_id / "translation"
        translation_dir.mkdir(parents=True, exist_ok=True)
        return translation_dir / f"{arxiv_id}_trans_cache.json"
    
    def _calculate_text_hash(self, text: str) -> str:
        """
        计算文本的哈希值，用于验证缓存一致性
        
        输入：
        - text: 文本内容，如 "Machine learning is a subset of artificial intelligence..."
        
        输出：
        - hash_value: 文本的MD5哈希值，如 "a1b2c3d4e5f6..."
        
        这个函数生成文本的哈希值，用于检测原文是否发生变化
        """
        return hashlib.md5(text.encode('utf-8')).hexdigest()
    
    def _load_cache_file(self, cache_file_path: Path) -> Dict[str, Any]:
        """
        加载缓存文件内容
        
        输入：
        - cache_file_path: 缓存文件路径，如 Path("./arxiv_cache/2402.14207/translation/2402.14207_trans_cache.json")
        
        输出：
        - cache_data: 缓存数据字典，包含论文ID、时间戳和段落列表
        
        这个函数从磁盘加载缓存文件，处理文件不存在或格式错误的情况
        """
        try:
            if cache_file_path.exists():
                with open(cache_file_path, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                logger.info(f"成功加载缓存: {cache_file_path}")
                logger.info(f"缓存包含 {len(cache_data.get('segments', []))} 个段落")
                return cache_data
            else:
                logger.info(f"缓存文件不存在，将创建新缓存: {cache_file_path}")
                return self._create_empty_cache_structure()
                
        except json.JSONDecodeError as e:
            logger.error(f"缓存文件格式错误: {e}")
            return self._create_empty_cache_structure()
        except Exception as e:
            logger.error(f"加载缓存文件时出错: {e}")
            return self._create_empty_cache_structure()
    
    def _create_empty_cache_structure(self) -> Dict[str, Any]:
        """
        创建空的缓存数据结构
        
        输入：无
        输出：空的缓存数据字典
        
        这个函数创建标准的缓存数据结构模板
        """
        return {
            "arxiv_id": "",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "segments": []
        }
    
    def _save_cache_file(self, cache_file_path: Path, cache_data: Dict[str, Any]) -> bool:
        """
        保存缓存文件到磁盘
        
        输入：
        - cache_file_path: 缓存文件路径
        - cache_data: 要保存的缓存数据
        
        输出：
        - success: 是否保存成功（布尔值）
        
        这个函数将缓存数据写入磁盘文件
        """
        try:
            # 更新时间戳
            cache_data["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            with open(cache_file_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            
            logger.debug(f"缓存文件保存成功: {cache_file_path}")
            return True
            
        except Exception as e:
            logger.error(f"保存缓存文件时出错: {e}")
            return False
    
    def get_cached_translation(self, arxiv_id: str, index: int, original_text: str) -> Optional[str]:
        """
        获取指定段落的缓存翻译
        
        输入：
        - arxiv_id: arxiv论文ID，如 "2402.14207"
        - index: 段落索引，如 5
        - original_text: 原始文本内容，如 "Machine learning has revolutionized..."
        
        输出：
        - translation: 缓存的翻译内容（字符串）或None（如果未找到）
        
        这个函数查找指定段落的缓存翻译，验证原文一致性后返回翻译结果
        """
        try:
            self.cache_stats['total_requests'] += 1
            self.cache_stats['last_access_time'] = time.time()
            
            cache_file_path = self._get_cache_file_path(arxiv_id)
            cache_data = self._load_cache_file(cache_file_path)
            
            # 查找指定索引的段落
            for segment in cache_data.get("segments", []):
                if segment.get("index") == index:
                    # 验证原文哈希值
                    original_hash = self._calculate_text_hash(original_text)
                    cached_hash = segment.get("hash", "")
                    
                    if original_hash == cached_hash:
                        # 缓存命中
                        self.cache_stats['cache_hits'] += 1
                        translation = segment.get("translation", "")
                        logger.debug(f"缓存命中: arxiv_id={arxiv_id}, index={index}")
                        return translation
                    else:
                        # 原文已变化，缓存失效
                        logger.warning(f"原文已变化，缓存失效: arxiv_id={arxiv_id}, index={index}")
                        break
            
            # 缓存未命中
            self.cache_stats['cache_misses'] += 1
            logger.debug(f"缓存未命中: arxiv_id={arxiv_id}, index={index}")
            return None
            
        except Exception as e:
            logger.error(f"获取缓存翻译时出错: {e}")
            self.cache_stats['cache_misses'] += 1
            return None
    
    def update_single_translation(self, arxiv_id: str, index: int, 
                                original_text: str, translation: str) -> bool:
        """
        更新单个段落的翻译缓存
        
        输入：
        - arxiv_id: arxiv论文ID，如 "2402.14207"
        - index: 段落索引，如 5
        - original_text: 原始文本，如 "Machine learning has revolutionized..."
        - translation: 翻译文本，如 "机器学习已经彻底改变了..."
        
        输出：
        - success: 是否更新成功（布尔值）
        
        这个函数更新指定段落的翻译缓存，如果段落已存在则覆盖
        """
        try:
            cache_file_path = self._get_cache_file_path(arxiv_id)
            cache_data = self._load_cache_file(cache_file_path)
            
            # 设置arxiv_id
            if not cache_data.get("arxiv_id"):
                cache_data["arxiv_id"] = arxiv_id
            
            # 创建新的段落记录
            new_segment = {
                "index": index,
                "original": original_text,
                "translation": translation,
                "hash": self._calculate_text_hash(original_text)
            }
            
            # 查找是否已存在该索引的段落
            segments = cache_data.get("segments", [])
            updated = False
            
            for i, segment in enumerate(segments):
                if segment.get("index") == index:
                    # 更新现有段落
                    segments[i] = new_segment
                    updated = True
                    break
            
            if not updated:
                # 添加新段落
                segments.append(new_segment)
                cache_data["segments"] = segments
            
            # 按索引排序
            cache_data["segments"].sort(key=lambda x: x.get("index", 0))
            
            # 保存到文件
            success = self._save_cache_file(cache_file_path, cache_data)
            
            if success:
                self.cache_stats['cache_updates'] += 1
                logger.info(f"成功更新缓存段落: arxiv_id={arxiv_id}, index={index}")
            
            return success
            
        except Exception as e:
            logger.error(f"更新缓存翻译时出错: {e}")
            return False
    
    def batch_update_translations(self, arxiv_id: str, 
                                translations: List[Tuple[int, str, str]]) -> bool:
        """
        批量更新多个段落的翻译缓存
        
        输入：
        - arxiv_id: arxiv论文ID，如 "2402.14207"
        - translations: 翻译数据列表，格式为 [(index, original_text, translation), ...]
          如 [(0, "Abstract", "摘要"), (1, "Introduction", "介绍")]
        
        输出：
        - success: 是否全部更新成功（布尔值）
        
        这个函数批量更新多个段落的翻译缓存，提高效率
        """
        try:
            cache_file_path = self._get_cache_file_path(arxiv_id)
            cache_data = self._load_cache_file(cache_file_path)
            
            # 设置arxiv_id
            if not cache_data.get("arxiv_id"):
                cache_data["arxiv_id"] = arxiv_id
            
            segments = cache_data.get("segments", [])
            updated_count = 0
            
            for index, original_text, translation in translations:
                # 创建新的段落记录
                new_segment = {
                    "index": index,
                    "original": original_text,
                    "translation": translation,
                    "hash": self._calculate_text_hash(original_text)
                }
                
                # 查找是否已存在该索引的段落
                updated = False
                for i, segment in enumerate(segments):
                    if segment.get("index") == index:
                        segments[i] = new_segment
                        updated = True
                        break
                
                if not updated:
                    segments.append(new_segment)
                
                updated_count += 1
            
            # 按索引排序
            cache_data["segments"] = sorted(segments, key=lambda x: x.get("index", 0))
            
            # 保存到文件
            success = self._save_cache_file(cache_file_path, cache_data)
            
            if success:
                self.cache_stats['cache_updates'] += updated_count
                logger.info(f"批量更新缓存成功: arxiv_id={arxiv_id}, 更新了 {updated_count} 个段落")
            
            return success
            
        except Exception as e:
            logger.error(f"批量更新缓存时出错: {e}")
            return False
    
    def get_cache_info(self, arxiv_id: str) -> Dict[str, Any]:
        """
        获取指定论文的缓存信息
        
        输入：
        - arxiv_id: arxiv论文ID，如 "2402.14207"
        
        输出：
        - cache_info: 缓存信息字典，包含段落数量、时间戳等
        
        这个函数返回指定论文的缓存统计信息
        """
        try:
            cache_file_path = self._get_cache_file_path(arxiv_id)
            cache_data = self._load_cache_file(cache_file_path)
            
            segments = cache_data.get("segments", [])
            
            return {
                "arxiv_id": cache_data.get("arxiv_id", arxiv_id),
                "timestamp": cache_data.get("timestamp", "未知"),
                "segment_count": len(segments),
                "cache_file_exists": cache_file_path.exists(),
                "cache_file_path": str(cache_file_path),
                "cache_file_size": cache_file_path.stat().st_size if cache_file_path.exists() else 0
            }
            
        except Exception as e:
            logger.error(f"获取缓存信息时出错: {e}")
            return {
                "arxiv_id": arxiv_id,
                "error": str(e)
            }
    
    def clear_cache(self, arxiv_id: str) -> bool:
        """
        清除指定论文的缓存
        
        输入：
        - arxiv_id: arxiv论文ID，如 "2402.14207"
        
        输出：
        - success: 是否清除成功（布尔值）
        
        这个函数删除指定论文的缓存文件
        """
        try:
            cache_file_path = self._get_cache_file_path(arxiv_id)
            
            if cache_file_path.exists():
                cache_file_path.unlink()
                logger.info(f"缓存已清除: {cache_file_path}")
                return True
            else:
                logger.info(f"缓存文件不存在，无需清除: {cache_file_path}")
                return True
                
        except Exception as e:
            logger.error(f"清除缓存时出错: {e}")
            return False
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        获取缓存管理器的统计信息
        
        输入：无
        输出：统计信息字典
        
        这个函数返回缓存系统的使用统计
        """
        stats = self.cache_stats.copy()
        
        if stats['total_requests'] > 0:
            stats['cache_hit_rate'] = f"{(stats['cache_hits'] / stats['total_requests'] * 100):.1f}%"
        else:
            stats['cache_hit_rate'] = "0.0%"
        
        if stats['last_access_time']:
            stats['last_access_time_str'] = time.strftime(
                "%Y-%m-%d %H:%M:%S", 
                time.localtime(stats['last_access_time'])
            )
        
        return stats
    
    def list_cached_papers(self) -> List[str]:
        """
        列出所有已缓存的论文ID
        
        输入：无
        输出：arxiv_id列表，如 ["2402.14207", "1812.10695"]
        
        这个函数扫描缓存目录，返回所有已缓存的论文ID
        """
        try:
            cached_papers = []
            
            for paper_dir in self.cache_dir.iterdir():
                if paper_dir.is_dir():
                    translation_dir = paper_dir / "translation"
                    if translation_dir.exists():
                        cache_files = list(translation_dir.glob("*_trans_cache.json"))
                        if cache_files:
                            cached_papers.append(paper_dir.name)
            
            logger.info(f"发现 {len(cached_papers)} 个已缓存的论文")
            return sorted(cached_papers)
            
        except Exception as e:
            logger.error(f"列出缓存论文时出错: {e}")
            return []

# 便捷函数
def get_cached_translation(arxiv_id: str, index: int, original_text: str, 
                          cache_dir: str = "./arxiv_cache") -> Optional[str]:
    """
    便捷函数：获取缓存的翻译
    
    输入：
    - arxiv_id: arxiv论文ID
    - index: 段落索引
    - original_text: 原始文本
    - cache_dir: 缓存目录
    
    输出：
    - translation: 缓存的翻译内容或None
    
    这个函数提供最简单的缓存查询接口
    """
    cache_manager = TranslationCache(cache_dir)
    return cache_manager.get_cached_translation(arxiv_id, index, original_text)

def update_translation_cache(arxiv_id: str, index: int, 
                           original_text: str, translation: str,
                           cache_dir: str = "./arxiv_cache") -> bool:
    """
    便捷函数：更新翻译缓存
    
    输入：
    - arxiv_id: arxiv论文ID
    - index: 段落索引
    - original_text: 原始文本
    - translation: 翻译文本
    - cache_dir: 缓存目录
    
    输出：
    - success: 是否更新成功
    
    这个函数提供最简单的缓存更新接口
    """
    cache_manager = TranslationCache(cache_dir)
    return cache_manager.update_single_translation(arxiv_id, index, original_text, translation)

# 测试和示例代码
def main():
    """
    测试函数，演示翻译缓存管理器的使用方法
    """
    print("=" * 70)
    print("翻译缓存管理器测试")
    print("=" * 70)
    
    # 创建缓存管理器
    cache_manager = TranslationCache(cache_dir="./test_cache")
    
    # 测试数据
    test_arxiv_id = "2402.14207"
    test_segments = [
        (0, "Machine learning has revolutionized artificial intelligence.", "机器学习已经彻底改变了人工智能。"),
        (1, "Neural networks are computational models inspired by the brain.", "神经网络是受大脑启发的计算模型。"),
        (2, "Deep learning models achieve remarkable performance.", "深度学习模型取得了卓越的性能。")
    ]
    
    print(f"测试数据:")
    print(f"- arxiv_id: {test_arxiv_id}")
    print(f"- 段落数量: {len(test_segments)}")
    
    # 测试1: 批量更新缓存
    print(f"\n{'='*50}")
    print("测试1: 批量更新缓存")
    print("=" * 50)
    
    success = cache_manager.batch_update_translations(test_arxiv_id, test_segments)
    if success:
        print("✅ 批量更新缓存成功")
    else:
        print("❌ 批量更新缓存失败")
    
    # 测试2: 获取缓存翻译
    print(f"\n{'='*50}")
    print("测试2: 获取缓存翻译")
    print("=" * 50)
    
    for index, original, expected_translation in test_segments:
        cached_translation = cache_manager.get_cached_translation(
            test_arxiv_id, index, original
        )
        
        if cached_translation:
            print(f"✅ 段落 {index} 缓存命中")
            print(f"   原文: {original[:50]}...")
            print(f"   译文: {cached_translation[:50]}...")
            
            # 验证翻译内容
            if cached_translation == expected_translation:
                print(f"   ✓ 翻译内容正确")
            else:
                print(f"   ✗ 翻译内容不匹配")
        else:
            print(f"❌ 段落 {index} 缓存未命中")
    
    # 测试3: 单个更新
    print(f"\n{'='*50}")
    print("测试3: 单个段落更新")
    print("=" * 50)
    
    new_segment = (3, "Transformers have become the dominant architecture.", "Transformer已成为主导架构。")
    index, original, translation = new_segment
    
    success = cache_manager.update_single_translation(test_arxiv_id, index, original, translation)
    if success:
        print("✅ 单个段落更新成功")
        
        # 验证更新
        cached = cache_manager.get_cached_translation(test_arxiv_id, index, original)
        if cached == translation:
            print("✓ 更新内容验证成功")
        else:
            print("✗ 更新内容验证失败")
    else:
        print("❌ 单个段落更新失败")
    
    # 测试4: 缓存信息
    print(f"\n{'='*50}")
    print("测试4: 缓存信息查询")
    print("=" * 50)
    
    cache_info = cache_manager.get_cache_info(test_arxiv_id)
    print("缓存信息:")
    for key, value in cache_info.items():
        print(f"  {key}: {value}")
    
    # 测试5: 统计信息
    print(f"\n{'='*50}")
    print("测试5: 缓存统计信息")
    print("=" * 50)
    
    stats = cache_manager.get_cache_stats()
    print("统计信息:")
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    # 测试6: 列出缓存论文
    print(f"\n{'='*50}")
    print("测试6: 列出缓存论文")
    print("=" * 50)
    
    cached_papers = cache_manager.list_cached_papers()
    print(f"已缓存的论文: {cached_papers}")
    
    # 测试7: 便捷函数
    print(f"\n{'='*50}")
    print("测试7: 便捷函数接口")
    print("=" * 50)
    
    # 测试便捷查询函数
    cached = get_cached_translation(test_arxiv_id, 0, test_segments[0][1], "./test_cache")
    if cached:
        print("✅ 便捷查询函数测试通过")
        print(f"   译文: {cached[:50]}...")
    else:
        print("❌ 便捷查询函数测试失败")
    
    # 测试便捷更新函数
    success = update_translation_cache(
        test_arxiv_id, 4, "Test convenience function.", "测试便捷函数。", "./test_cache"
    )
    if success:
        print("✅ 便捷更新函数测试通过")
    else:
        print("❌ 便捷更新函数测试失败")
    
    print(f"\n{'='*70}")
    print("翻译缓存管理器测试完成")
    
    # 显示最终统计
    final_stats = cache_manager.get_cache_stats()
    print(f"\n最终统计:")
    print(f"- 总请求数: {final_stats['total_requests']}")
    print(f"- 缓存命中: {final_stats['cache_hits']}")
    print(f"- 缓存未命中: {final_stats['cache_misses']}")
    print(f"- 缓存命中率: {final_stats['cache_hit_rate']}")
    print(f"- 缓存更新: {final_stats['cache_updates']}")
    
    print(f"{'='*70}")

if __name__ == "__main__":
    main()
