"""
Hardware-backed key storage using macOS Keychain.

Provides secure storage for gate validation keys using the macOS
Keychain instead of file-based storage.
"""

from __future__ import annotations

import subprocess
from typing import Optional


class GateKeyStorage:
    """Manages gate keys in macOS Keychain."""

    SERVICE_NAME: str = "carby-studio-gate-validation"
    ACCOUNT_NAME: str = "validation-key"

    @classmethod
    def store_key(cls, key: str) -> bool:
        """
        Store a key in macOS Keychain.

        Args:
            key: The key to store securely

        Returns:
            True if successful, False otherwise
        """
        try:
            # First, delete any existing entry to avoid duplicates
            cls._delete_existing()

            # Add the new key to keychain
            cmd: list[str] = [
                "security",
                "add-generic-password",
                "-s", cls.SERVICE_NAME,
                "-a", cls.ACCOUNT_NAME,
                "-w", key,
                "-U",  # Update if exists (shouldn't happen after delete)
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )

            return result.returncode == 0

        except subprocess.CalledProcessError as e:
            print(f"Keychain store error: {e.stderr}")
            return False
        except FileNotFoundError:
            print("security CLI not found. Are you on macOS?")
            return False

    @classmethod
    def retrieve_key(cls) -> Optional[str]:
        """
        Retrieve a key from macOS Keychain.

        Returns:
            The stored key, or None if not found
        """
        try:
            cmd: list[str] = [
                "security",
                "find-generic-password",
                "-s", cls.SERVICE_NAME,
                "-a", cls.ACCOUNT_NAME,
                "-w",  # Output password only
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )

            if result.returncode == 0:
                return result.stdout.strip()

            return None

        except subprocess.CalledProcessError:
            # Key not found or other error
            return None
        except FileNotFoundError:
            print("security CLI not found. Are you on macOS?")
            return None

    @classmethod
    def delete_key(cls) -> bool:
        """
        Delete the stored key from macOS Keychain.

        Returns:
            True if successful or key didn't exist, False on error
        """
        return cls._delete_existing()

    @classmethod
    def key_exists(cls) -> bool:
        """
        Check if a key exists in the Keychain.

        Returns:
            True if key exists, False otherwise
        """
        return cls.retrieve_key() is not None

    @classmethod
    def _delete_existing(cls) -> bool:
        """Delete existing keychain entry if it exists."""
        try:
            cmd: list[str] = [
                "security",
                "delete-generic-password",
                "-s", cls.SERVICE_NAME,
                "-a", cls.ACCOUNT_NAME,
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True
            )

            # Return code 0 means deleted, 44 means not found (both OK)
            return result.returncode in (0, 44)

        except FileNotFoundError:
            print("security CLI not found. Are you on macOS?")
            return False


def store_key(key: str) -> bool:
    """Convenience function to store a key."""
    return GateKeyStorage.store_key(key)


def retrieve_key() -> Optional[str]:
    """Convenience function to retrieve a key."""
    return GateKeyStorage.retrieve_key()
