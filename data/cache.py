"""数据缓存模块"""
import pickle
import hashlib
from pathlib import Path
from typing import Optional, Any


class DataCache:
    """本地数据缓存管理"""
    
    def __init__(self, cache_dir: str = None):
        self.cache_dir = Path(cache_dir or './data_storage/cache')
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.enabled = True
    
    def _get_cache_key(self, prefix: str, **kwargs) -> str:
        """生成缓存键"""
        param_str = '_'.join([f"{k}={v}" for k, v in sorted(kwargs.items())])
        hash_key = hashlib.md5(param_str.encode()).hexdigest()[:12]
        return f"{prefix}_{hash_key}"
    
    def _get_cache_path(self, cache_key: str) -> Path:
        """获取缓存文件路径"""
        return self.cache_dir / f"{cache_key}.pkl"
    
    def get(self, prefix: str, **kwargs) -> Optional[Any]:
        """获取缓存数据"""
        if not self.enabled:
            return None
        
        cache_key = self._get_cache_key(prefix, **kwargs)
        cache_path = self._get_cache_path(cache_key)
        
        if not cache_path.exists():
            return None
        
        try:
            with open(cache_path, 'rb') as f:
                return pickle.load(f)
        except Exception:
            return None
    
    def set(self, data: Any, prefix: str, **kwargs):
        """设置缓存数据"""
        if not self.enabled:
            return
        
        cache_key = self._get_cache_key(prefix, **kwargs)
        cache_path = self._get_cache_path(cache_key)
        
        try:
            with open(cache_path, 'wb') as f:
                pickle.dump(data, f)
        except Exception:
            pass
