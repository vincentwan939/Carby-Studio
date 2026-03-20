"""
Path Validation Utilities for Carby Sprint Framework.

Provides functions to validate sprint IDs and generate safe work item IDs
to prevent path traversal attacks and ensure consistent naming.
"""

import re
import uuid
from typing import Optional


def validate_sprint_id(sprint_id: str) -> bool:
    """
    Validate a sprint ID to prevent path traversal and ensure safe characters.
    
    Args:
        sprint_id: Sprint identifier to validate
        
    Returns:
        True if valid, raises ValueError if invalid
    """
    if not sprint_id:
        raise ValueError("Sprint ID cannot be empty")
    
    # Check for path traversal attempts
    if '..' in sprint_id or '/' in sprint_id or '\\' in sprint_id:
        raise ValueError(f"Invalid sprint ID '{sprint_id}': Contains path traversal characters (.., /, \\)")
    
    # Check for valid characters (alphanumeric, underscore, hyphen)
    if not re.match(r'^[a-zA-Z0-9_-]+$', sprint_id):
        raise ValueError(f"Invalid sprint ID '{sprint_id}': Contains invalid characters. "
                         f"Only alphanumeric, underscore (_), and hyphen (-) are allowed.")
    
    # Additional checks
    if len(sprint_id) > 100:
        raise ValueError(f"Invalid sprint ID '{sprint_id}': Too long (max 100 chars)")
    
    if len(sprint_id) < 1:
        raise ValueError(f"Invalid sprint ID '{sprint_id}': Too short (min 1 char)")
    
    return True


def validate_work_item_id(work_item_id: str) -> bool:
    """
    Validate a work item ID to prevent path traversal and ensure safe characters.
    
    Args:
        work_item_id: Work item identifier to validate
        
    Returns:
        True if valid, raises ValueError if invalid
    """
    if not work_item_id:
        raise ValueError("Work item ID cannot be empty")
    
    # Check for path traversal attempts
    if '..' in work_item_id or '/' in work_item_id or '\\' in work_item_id:
        raise ValueError(f"Invalid work item ID '{work_item_id}': Contains path traversal characters (.., /, \\)")
    
    # Check for valid characters (alphanumeric, underscore, hyphen)
    if not re.match(r'^[a-zA-Z0-9_-]+$', work_item_id):
        raise ValueError(f"Invalid work item ID '{work_item_id}': Contains invalid characters. "
                         f"Only alphanumeric, underscore (_), and hyphen (-) are allowed.")
    
    # Additional checks
    if len(work_item_id) > 100:
        raise ValueError(f"Invalid work item ID '{work_item_id}': Too long (max 100 chars)")
    
    if len(work_item_id) < 1:
        raise ValueError(f"Invalid work item ID '{work_item_id}': Too short (min 1 char)")
    
    return True


def generate_work_item_id(prefix: str = "wi") -> str:
    """
    Generate a unique work item ID with a random hex suffix.
    
    Args:
        prefix: Prefix for the work item ID (default: "wi")
        
    Returns:
        Generated work item ID in format: {prefix}_{12_hex_chars}
    """
    # Generate 12-character hexadecimal string
    hex_part = uuid.uuid4().hex[:12]
    return f"{prefix}_{hex_part}"


def safe_join_path(base_path: str, *path_parts) -> str:
    """
    Safely join path parts, validating each part to prevent path traversal.
    
    Args:
        base_path: Base path
        path_parts: Additional path components to join
        
    Returns:
        Safe joined path
    """
    import os
    
    # Validate base path
    if '..' in base_path or base_path.startswith('/') or base_path.startswith('\\'):
        raise ValueError(f"Invalid base path '{base_path}': Contains path traversal characters")
    
    # Validate and join additional parts
    safe_parts = [base_path]
    for part in path_parts:
        # Check for path traversal attempts in each part
        if '..' in part or '/' in part or '\\' in part:
            raise ValueError(f"Path part '{part}' contains path traversal characters (.., /, \\)")
        
        safe_parts.append(part)
    
    # Use os.path.join to properly join the parts
    result = os.path.join(*safe_parts)
    
    # Final validation: make sure the result doesn't go outside intended directory
    # Normalize the path and check for upward traversal
    normalized = os.path.normpath(result)
    if ".." in normalized.split(os.sep):
        raise ValueError(f"Path traversal detected in final path: {result}")
    
    return normalized


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename to remove dangerous characters.
    
    Args:
        filename: Filename to sanitize
        
    Returns:
        Sanitized filename
    """
    if not filename:
        raise ValueError("Filename cannot be empty")
    
    # Remove dangerous characters and sequences
    if '..' in filename or '/' in filename or '\\' in filename:
        raise ValueError(f"Invalid filename '{filename}': Contains path traversal characters")
    
    # Replace potentially problematic characters (but keep safe ones)
    # Only allow alphanumeric, dash, underscore, dot, space
    sanitized = re.sub(r'[^\w\-_. ]', '_', filename)
    
    # Limit length
    if len(sanitized) > 255:
        raise ValueError(f"Filename too long: {len(sanitized)} characters (max 255)")
    
    return sanitized