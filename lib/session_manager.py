#!/usr/bin/env python3
"""
Bitwarden Session Manager for Carby Studio

Manages BW_SESSION token in macOS Keychain with auto-refresh capability.
"""

import os
import re
import time
import json
import subprocess
import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path

# Configure logging - never log secrets
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class SessionInfo:
    """Session metadata (no secrets stored here)."""
    unlocked_at: Optional[str] = None
    expires_at: Optional[str] = None
    last_sync: Optional[str] = None
    user_email: Optional[str] = None
    status: str = "locked"  # locked, unlocked, expired


class SessionManager:
    """Manages Bitwarden CLI session with Keychain integration."""
    
    # Keychain service and account for BW_SESSION
    KEYCHAIN_SERVICE = "com.carby-studio.bitwarden"
    KEYCHAIN_ACCOUNT = "bw-session"
    
    # Session expires after 30 minutes, refresh at 25 minutes
    SESSION_DURATION_MINUTES = 30
    REFRESH_THRESHOLD_MINUTES = 25
    
    # Cache file for session metadata (not the token itself)
    CACHE_DIR = Path.home() / ".openclaw" / "cache"
    CACHE_FILE = CACHE_DIR / "bw_session_meta.json"
    
    def __init__(self):
        self._ensure_cache_dir()
        self._session_info: Optional[SessionInfo] = None
        
    def _ensure_cache_dir(self):
        """Ensure cache directory exists."""
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        
    def _load_cache(self) -> SessionInfo:
        """Load session metadata from cache."""
        if self.CACHE_FILE.exists():
            try:
                with open(self.CACHE_FILE, 'r') as f:
                    data = json.load(f)
                return SessionInfo(**data)
            except (json.JSONDecodeError, TypeError) as e:
                logger.debug(f"Failed to load session cache: {e}")
        return SessionInfo()
    
    def _save_cache(self, info: SessionInfo):
        """Save session metadata to cache."""
        try:
            with open(self.CACHE_FILE, 'w') as f:
                json.dump(asdict(info), f, indent=2)
        except Exception as e:
            logger.debug(f"Failed to save session cache: {e}")
    
    def _get_keychain_session(self) -> Optional[str]:
        """Retrieve BW_SESSION from macOS Keychain."""
        try:
            result = subprocess.run(
                [
                    "security", "find-generic-password",
                    "-s", self.KEYCHAIN_SERVICE,
                    "-a", self.KEYCHAIN_ACCOUNT,
                    "-w"  # Output password only
                ],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                session = result.stdout.strip()
                if session and session != "password:":
                    return session
        except subprocess.TimeoutExpired:
            logger.warning("Keychain access timed out")
        except Exception as e:
            logger.debug(f"Failed to retrieve session from keychain: {e}")
        return None
    
    def _set_keychain_session(self, session: str) -> bool:
        """Store BW_SESSION in macOS Keychain."""
        try:
            # First delete any existing entry
            subprocess.run(
                [
                    "security", "delete-generic-password",
                    "-s", self.KEYCHAIN_SERVICE,
                    "-a", self.KEYCHAIN_ACCOUNT
                ],
                capture_output=True,
                timeout=5
            )
            
            # Add new entry
            result = subprocess.run(
                [
                    "security", "add-generic-password",
                    "-s", self.KEYCHAIN_SERVICE,
                    "-a", self.KEYCHAIN_ACCOUNT,
                    "-w", session,
                    "-U"  # Update if exists
                ],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            logger.warning("Keychain store timed out")
        except Exception as e:
            logger.debug(f"Failed to store session in keychain: {e}")
        return False
    
    def _delete_keychain_session(self) -> bool:
        """Remove BW_SESSION from macOS Keychain."""
        try:
            result = subprocess.run(
                [
                    "security", "delete-generic-password",
                    "-s", self.KEYCHAIN_SERVICE,
                    "-a", self.KEYCHAIN_ACCOUNT
                ],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception as e:
            logger.debug(f"Failed to delete session from keychain: {e}")
        return False
    
    def _run_bw_command(self, args: list, use_session: bool = True) -> Tuple[bool, str, str]:
        """Run a Bitwarden CLI command.
        
        Args:
            args: Command arguments (after 'bw')
            use_session: Whether to include BW_SESSION env var
            
        Returns:
            Tuple of (success, stdout, stderr)
        """
        env = os.environ.copy()
        
        if use_session:
            session = self._get_keychain_session()
            if session:
                env['BW_SESSION'] = session
        
        try:
            result = subprocess.run(
                ["bw"] + args,
                capture_output=True,
                text=True,
                env=env,
                timeout=60
            )
            return result.returncode == 0, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return False, "", "Command timed out"
        except FileNotFoundError:
            return False, "", "Bitwarden CLI (bw) not found. Please install: brew install bitwarden-cli"
        except Exception as e:
            return False, "", str(e)
    
    def check_status(self) -> SessionInfo:
        """Check current Bitwarden session status."""
        info = SessionInfo()
        
        success, stdout, stderr = self._run_bw_command(["status"], use_session=False)
        
        if not success:
            info.status = "error"
            return info
        
        try:
            status_data = json.loads(stdout)
            info.status = status_data.get("status", "locked")
            info.user_email = status_data.get("userEmail")
        except json.JSONDecodeError:
            info.status = "error"
        
        return info
    
    def is_unlocked(self) -> bool:
        """Check if session is currently unlocked."""
        info = self.check_status()
        return info.status == "unlocked"
    
    def needs_refresh(self) -> bool:
        """Check if session needs refresh (approaching expiration)."""
        info = self._load_cache()
        
        if info.status != "unlocked" or not info.unlocked_at:
            return True
        
        try:
            unlocked = datetime.fromisoformat(info.unlocked_at)
            elapsed = datetime.now() - unlocked
            return elapsed > timedelta(minutes=self.REFRESH_THRESHOLD_MINUTES)
        except (ValueError, TypeError):
            return True
    
    def unlock(self, password: Optional[str] = None) -> Tuple[bool, str]:
        """Unlock Bitwarden and store session.
        
        Args:
            password: Master password (if None, will try to use existing session)
            
        Returns:
            Tuple of (success, message)
        """
        # First check if already unlocked
        if self.is_unlocked():
            return True, "Already unlocked"
        
        # Try existing session from keychain
        existing_session = self._get_keychain_session()
        if existing_session:
            # Test if session is still valid
            success, stdout, stderr = self._run_bw_command(["status"])
            if success:
                try:
                    status = json.loads(stdout)
                    if status.get("status") == "unlocked":
                        # Update cache
                        info = SessionInfo(
                            unlocked_at=datetime.now().isoformat(),
                            expires_at=(datetime.now() + timedelta(minutes=self.SESSION_DURATION_MINUTES)).isoformat(),
                            status="unlocked",
                            user_email=status.get("userEmail")
                        )
                        self._save_cache(info)
                        return True, "Session restored from keychain"
                except json.JSONDecodeError:
                    pass
        
        # Need to unlock with password
        if not password:
            return False, "Password required to unlock Bitwarden"
        
        # SECURITY FIX (Issue #1): Use stdin instead of command line for password
        # This prevents password exposure in process list (ps)
        try:
            result = subprocess.run(
                ["bw", "unlock", "--raw"],
                input=password,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode != 0:
                return False, f"Unlock failed: {result.stderr}"
            
            session = result.stdout.strip()
        except subprocess.TimeoutExpired:
            return False, "Unlock command timed out"
        except FileNotFoundError:
            return False, "Bitwarden CLI (bw) not found"
        except Exception as e:
            return False, f"Unlock failed: {str(e)}"
        
        if not session:
            return False, "No session token received"
        
        # Store in keychain
        if not self._set_keychain_session(session):
            logger.warning("Failed to store session in keychain")
        
        # Update cache
        info = SessionInfo(
            unlocked_at=datetime.now().isoformat(),
            expires_at=(datetime.now() + timedelta(minutes=self.SESSION_DURATION_MINUTES)).isoformat(),
            status="unlocked"
        )
        self._save_cache(info)
        
        return True, "Unlocked successfully"
    
    def lock(self) -> bool:
        """Lock Bitwarden and clear stored session."""
        self._run_bw_command(["lock"], use_session=False)
        self._delete_keychain_session()
        
        info = SessionInfo(status="locked")
        self._save_cache(info)
        
        return True
    
    def refresh(self) -> Tuple[bool, str]:
        """Refresh session before expiration.
        
        FIX (Issue #5): Correct timing, proper error handling, fallback to re-auth
        
        Returns:
            Tuple of (success, message)
        """
        # Check if we have a session
        session = self._get_keychain_session()
        if not session:
            return False, "No session to refresh"
        
        # First check current status - if already locked, can't refresh
        if not self.is_unlocked():
            return False, "Session expired, re-authentication required"
        
        # Sync to extend session
        success, stdout, stderr = self._run_bw_command(["sync"])
        if not success:
            # Sync failed - session may be invalid
            logger.warning(f"Sync failed during refresh: {stderr}")
            # Try to check status again
            if not self.is_unlocked():
                return False, "Session expired, re-authentication required"
            # Even if sync failed, we might still be unlocked
            logger.info("Sync failed but session still valid")
        
        # Update cache with new timestamps
        info = self._load_cache()
        info.unlocked_at = datetime.now().isoformat()
        info.expires_at = (datetime.now() + timedelta(minutes=self.SESSION_DURATION_MINUTES)).isoformat()
        info.last_sync = datetime.now().isoformat()
        info.status = "unlocked"
        self._save_cache(info)
        
        return True, "Session refreshed"
    
    def ensure_unlocked(self, password: Optional[str] = None) -> Tuple[bool, str]:
        """Ensure session is unlocked, prompting if necessary.
        
        This is the main entry point - call this before any Bitwarden operation.
        
        FIX (Issue #5): Proper error handling and fallback to re-auth
        
        Returns:
            Tuple of (success, message)
        """
        # Check current status
        if self.is_unlocked():
            # Check if needs refresh
            if self.needs_refresh():
                success, msg = self.refresh()
                if success:
                    return True, "Session refreshed"
                # Refresh failed, try to unlock with existing session
                logger.info(f"Session refresh failed: {msg}")
                # If we have a session but refresh failed, try full unlock
                if self._get_keychain_session():
                    logger.info("Attempting re-authentication with stored session")
                    # Clear and try to unlock
                    self._delete_keychain_session()
            else:
                return True, "Session active"
        
        # Try to unlock
        return self.unlock(password)
    
    def get_session_env(self) -> dict:
        """Get environment dict with BW_SESSION set.
        
        SECURITY FIX (Issue #2): Returns session env dict for subprocess only
        Never sets BW_SESSION in os.environ directly
        
        Returns:
            Dict suitable for subprocess env, NOT os.environ.update()
        """
        session = self._get_keychain_session()
        if session:
            return {'BW_SESSION': session}
        return {}
    
    def logout(self) -> bool:
        """Log out of Bitwarden completely."""
        self._run_bw_command(["logout"], use_session=False)
        self._delete_keychain_session()
        
        # Clear cache
        if self.CACHE_FILE.exists():
            self.CACHE_FILE.unlink()
        
        return True
    
    def get_status_summary(self) -> dict:
        """Get human-readable status summary."""
        info = self._load_cache()
        
        summary = {
            "status": info.status,
            "user": info.user_email or "unknown",
            "keychain_stored": self._get_keychain_session() is not None,
        }
        
        if info.unlocked_at:
            try:
                unlocked = datetime.fromisoformat(info.unlocked_at)
                elapsed = datetime.now() - unlocked
                summary["session_age_minutes"] = int(elapsed.total_seconds() / 60)
                summary["refresh_needed"] = self.needs_refresh()
            except (ValueError, TypeError):
                pass
        
        return summary


def main():
    """CLI for testing session manager."""
    import sys
    
    manager = SessionManager()
    
    if len(sys.argv) < 2:
        print("Usage: session_manager.py <command> [args]")
        print("Commands: status, unlock, lock, refresh, logout")
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "status":
        status = manager.check_status()
        print(f"Status: {status.status}")
        print(f"User: {status.user_email or 'N/A'}")
        
        summary = manager.get_status_summary()
        print(f"\nKeychain stored: {summary['keychain_stored']}")
        if 'session_age_minutes' in summary:
            print(f"Session age: {summary['session_age_minutes']} minutes")
            print(f"Refresh needed: {summary['refresh_needed']}")
    
    elif cmd == "unlock":
        password = sys.argv[2] if len(sys.argv) > 2 else None
        if not password:
            import getpass
            password = getpass.getpass("Bitwarden master password: ")
        success, msg = manager.unlock(password)
        print(f"{'✓' if success else '✗'} {msg}")
    
    elif cmd == "lock":
        manager.lock()
        print("✓ Locked")
    
    elif cmd == "refresh":
        success, msg = manager.refresh()
        print(f"{'✓' if success else '✗'} {msg}")
    
    elif cmd == "logout":
        manager.logout()
        print("✓ Logged out")
    
    else:
        print(f"Unknown command: {cmd}")


if __name__ == "__main__":
    main()
