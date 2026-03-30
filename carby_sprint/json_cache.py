"""
Shared JSON Cache Module for Carby Studio.

Provides a centralized, thread-safe JSON caching mechanism to prevent
cross-module state inconsistencies between gate_state.py, transaction.py,
and other modules that access shared state files.

The cache uses file modification time (mtime) to detect changes and
automatically invalidate stale entries.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


# Thread-safe JSON cache shared across all modules
# Structure: {file_path: (mtime, parsed_data)}
_json_cache: Dict[str, Tuple[float, Any]] = {}
_cache_lock = threading.RLock()


def _get_cached_json(file_path: Path) -> Optional[Any]:
    """
    Get cached JSON data if file hasn't been modified.
    
    Args:
        file_path: Path to the JSON file
        
    Returns:
        Parsed JSON data if cache hit, None if cache miss or file modified
    """
    path_str = str(file_path)
    with _cache_lock:
        if path_str in _json_cache:
            cached_mtime, cached_data = _json_cache[path_str]
            try:
                current_mtime = file_path.stat().st_mtime
                if current_mtime == cached_mtime:
                    return cached_data
            except (OSError, FileNotFoundError):
                # File no longer exists, remove from cache
                del _json_cache[path_str]
                return None
        return None


def _set_cached_json(file_path: Path, data: Any) -> None:
    """
    Cache JSON data with file modification time.
    
    Args:
        file_path: Path to the JSON file
        data: Parsed JSON data to cache
    """
    path_str = str(file_path)
    with _cache_lock:
        try:
            mtime = file_path.stat().st_mtime
            _json_cache[path_str] = (mtime, data)
        except (OSError, FileNotFoundError):
            # File doesn't exist, don't cache
            pass


def _invalidate_json_cache(file_path: Path) -> None:
    """
    Invalidate cached JSON data for a file.
    Call this after writing to a JSON file.
    
    Args:
        file_path: Path to the JSON file
    """
    path_str = str(file_path)
    with _cache_lock:
        _json_cache.pop(path_str, None)


def load_json_cached(file_path: Path) -> Any:
    """
    Load JSON file with caching to avoid repeated parsing.
    
    Thread-safe: Uses file modification time checking to ensure
    cached data is fresh.
    
    Args:
        file_path: Path to the JSON file
        
    Returns:
        Parsed JSON data (empty dict if file doesn't exist)
    """
    # Check cache first
    cached = _get_cached_json(file_path)
    if cached is not None:
        return cached  # Return directly - caller should copy if needed
    
    # Load from disk
    if file_path.exists():
        try:
            data = json.loads(file_path.read_text())
            _set_cached_json(file_path, data)
            return data
        except (json.JSONDecodeError, IOError):
            return {}
    
    return {}


def save_json_invalidate_cache(file_path: Path, data: Dict[str, Any]) -> None:
    """
    Save JSON data and invalidate cache.
    
    This is a convenience function that saves JSON data to a file
    and immediately invalidates the cache entry to ensure consistency.
    
    Args:
        file_path: Path to save the JSON file
        data: Data to save
    """
    with open(file_path, "w") as f:
        json.dump(data, f, indent=2)
    _invalidate_json_cache(file_path)


def clear_cache() -> None:
    """
    Clear all cached data.
    
    This is useful for testing or when you want to ensure
    fresh data is loaded from disk.
    """
    with _cache_lock:
        _json_cache.clear()


def get_cache_stats() -> Dict[str, Any]:
    """
    Get statistics about the current cache state.
    
    Returns:
        Dictionary with cache statistics:
        - entry_count: Number of cached files
        - cached_paths: List of cached file paths
    """
    with _cache_lock:
        return {
            "entry_count": len(_json_cache),
            "cached_paths": list(_json_cache.keys())
        }
