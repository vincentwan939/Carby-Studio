#!/usr/bin/env python3
"""
Bitwarden Data Access Object for Carby Studio

Provides CRUD operations for credentials stored in Bitwarden Organization.
"""

import os
import re
import json
import subprocess
import logging
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum

# Import session manager
from session_manager import SessionManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CredentialType(Enum):
    """Supported credential types."""
    NAS = "nas"
    ICLOUD = "icloud"
    GOOGLE_API = "google-api"
    DATABASE = "database"
    API_KEY = "api-key"


@dataclass
class Credential:
    """Represents a credential (without sensitive values in logs)."""
    project: str
    cred_type: str
    name: str
    fields: Dict[str, str] = field(default_factory=dict)
    item_id: Optional[str] = None
    collection_id: Optional[str] = None
    
    def __repr__(self) -> str:
        """Safe repr that doesn't expose secrets."""
        return f"Credential(project='{self.project}', type='{self.cred_type}', name='{self.name}', item_id='{self.item_id or 'new'}')"
    
    def __str__(self) -> str:
        """Safe string representation."""
        return self.__repr__()
    
    @property
    def full_name(self) -> str:
        """Bitwarden item name: carby-studio/{project}/{type}.{name}"""
        return f"carby-studio/{self.project}/{self.cred_type}.{self.name}"
    
    @classmethod
    def from_full_name(cls, full_name: str, fields: Dict[str, str] = None) -> Optional["Credential"]:
        """Parse a Bitwarden item name into a Credential.
        
        Format: carby-studio/{project}/{type}.{name}
        """
        pattern = r"^carby-studio/([^/]+)/([^\.]+)\.(.+)$"
        match = re.match(pattern, full_name)
        if not match:
            return None
        
        project, cred_type, name = match.groups()
        return cls(
            project=project,
            cred_type=cred_type,
            name=name,
            fields=fields or {}
        )


class BitwardenDAO:
    """Data Access Object for Bitwarden credentials."""
    
    # Organization and collection names
    ORG_NAME = "Carby-Studio"
    COLLECTION_NAME = "Carby-Studio"
    
    def __init__(self):
        self.session_manager = SessionManager()
        self._org_id: Optional[str] = None
        self._collection_id: Optional[str] = None
    
    def _ensure_unlocked(self) -> Tuple[bool, str]:
        """Ensure Bitwarden is unlocked."""
        return self.session_manager.ensure_unlocked()
    
    def _run_bw(self, args: List[str], needs_unlock: bool = True) -> Tuple[bool, str, str]:
        """Run Bitwarden CLI command.
        
        Args:
            args: Command arguments
            needs_unlock: Whether this command requires an unlocked vault
            
        Returns:
            Tuple of (success, stdout, stderr)
        """
        if needs_unlock:
            success, msg = self._ensure_unlocked()
            if not success:
                return False, "", f"Bitwarden not unlocked: {msg}"
        
        # SECURITY FIX (Issue #2): Use subprocess with explicit env only
        # Never set BW_SESSION in os.environ - only pass to subprocess
        env = os.environ.copy()
        session_env = self.session_manager.get_session_env()
        
        try:
            result = subprocess.run(
                ["bw"] + args,
                capture_output=True,
                text=True,
                env=env if not session_env else {**env, **session_env},
                timeout=60
            )
            return result.returncode == 0, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return False, "", "Command timed out"
        except FileNotFoundError:
            return False, "", "Bitwarden CLI (bw) not found"
        except Exception as e:
            return False, "", str(e)
    
    def _get_org_id(self) -> Optional[str]:
        """Get organization ID."""
        if self._org_id:
            return self._org_id
        
        success, stdout, stderr = self._run_bw(["list", "organizations", "--raw"])
        if not success:
            logger.error(f"Failed to list organizations: {stderr}")
            return None
        
        try:
            orgs = json.loads(stdout)
            for org in orgs:
                if org.get("name") == self.ORG_NAME:
                    self._org_id = org.get("id")
                    return self._org_id
        except json.JSONDecodeError:
            logger.error("Failed to parse organizations")
        
        return None
    
    def _get_collection_id(self) -> Optional[str]:
        """Get collection ID within the organization."""
        if self._collection_id:
            return self._collection_id
        
        org_id = self._get_org_id()
        if not org_id:
            return None
        
        success, stdout, stderr = self._run_bw(
            ["list", "collections", "--organizationid", org_id, "--raw"]
        )
        if not success:
            logger.error(f"Failed to list collections: {stderr}")
            return None
        
        try:
            collections = json.loads(stdout)
            for coll in collections:
                if coll.get("name") == self.COLLECTION_NAME:
                    self._collection_id = coll.get("id")
                    return self._collection_id
        except json.JSONDecodeError:
            logger.error("Failed to parse collections")
        
        return None
    
    def _build_item_template(self, credential: Credential) -> dict:
        """Build a Bitwarden item template for a credential."""
        # Build fields
        fields = []
        for key, value in credential.fields.items():
            fields.append({
                "name": key,
                "value": value,
                "type": 1  # Hidden field
            })
        
        # Determine item type based on credential type
        item_type = 2  # Secure Note (default)
        
        if credential.cred_type == "database":
            item_type = 3  # Card (we'll use notes for connection string)
        
        template = {
            "type": item_type,
            "name": credential.full_name,
            "notes": f"Carby Studio credential\nProject: {credential.project}\nType: {credential.cred_type}\nName: {credential.name}",
            "secureNote": {
                "type": 0
            },
            "fields": fields,
            "organizationId": self._get_org_id(),
            "collectionIds": [self._get_collection_id()] if self._get_collection_id() else []
        }
        
        # Add type-specific fields
        if credential.cred_type == "nas":
            template["login"] = {
                "username": credential.fields.get("username", ""),
                "password": credential.fields.get("password", "")
            }
            template["type"] = 1  # Login
        elif credential.cred_type == "icloud":
            template["login"] = {
                "username": credential.fields.get("apple_id", ""),
                "password": credential.fields.get("password", "")
            }
            template["type"] = 1  # Login
        elif credential.cred_type == "google-api":
            template["login"] = {
                "username": credential.fields.get("client_id", ""),
                "password": credential.fields.get("client_secret", "")
            }
            template["type"] = 1  # Login
        elif credential.cred_type == "database":
            # Build connection string for notes
            host = credential.fields.get("host", "")
            port = credential.fields.get("port", "")
            database = credential.fields.get("database", "")
            username = credential.fields.get("username", "")
            password = credential.fields.get("password", "")
            
            conn_str = f"host={host} port={port} dbname={database} user={username} password={password}"
            template["notes"] = f"{template['notes']}\n\nConnection:\n{conn_str}"
        elif credential.cred_type == "api-key":
            template["login"] = {
                "username": credential.fields.get("key_name", "API Key"),
                "password": credential.fields.get("key", "")
            }
            template["type"] = 1  # Login
        
        return template
    
    def create(self, credential: Credential) -> Tuple[bool, str]:
        """Create a new credential in Bitwarden.
        
        Args:
            credential: Credential to create
            
        Returns:
            Tuple of (success, item_id or error message)
        """
        logger.info(f"Creating credential: {credential.full_name}")
        
        # Build template
        template = self._build_item_template(credential)
        
        # Encode template
        import base64
        template_json = json.dumps(template)
        template_b64 = base64.b64encode(template_json.encode()).decode()
        
        # Create item
        success, stdout, stderr = self._run_bw(
            ["create", "item", "--organizationid", self._get_org_id(), template_b64]
        )
        
        if not success:
            logger.error(f"Failed to create item: {stderr}")
            return False, stderr
        
        try:
            result = json.loads(stdout)
            item_id = result.get("id")
            credential.item_id = item_id
            return True, item_id
        except json.JSONDecodeError:
            return False, "Failed to parse creation response"
    
    def get(self, project: str, cred_type: str, name: str) -> Tuple[bool, Optional[Credential]]:
        """Get a credential by project, type, and name.
        
        Returns:
            Tuple of (success, credential or None)
        """
        full_name = f"carby-studio/{project}/{cred_type}.{name}"
        return self.get_by_full_name(full_name)
    
    def get_by_full_name(self, full_name: str) -> Tuple[bool, Optional[Credential]]:
        """Get a credential by its full Bitwarden name.
        
        Returns:
            Tuple of (success, credential or None)
        """
        logger.debug(f"Getting credential: {full_name}")
        
        # Search for item
        success, stdout, stderr = self._run_bw(
            ["list", "items", "--search", full_name, "--raw"]
        )
        
        if not success:
            logger.error(f"Failed to search items: {stderr}")
            return False, None
        
        try:
            items = json.loads(stdout)
            # SECURITY FIX (Issue #8): Filter for exact name match
            # bw list --search does substring match, so we filter for exact match
            for item in items:
                if item.get("name") == full_name:
                    return self._parse_item(item)
        except json.JSONDecodeError:
            logger.error("Failed to parse items")
        
        return False, None
    
    def _parse_item(self, item: dict) -> Tuple[bool, Optional[Credential]]:
        """Parse a Bitwarden item into a Credential."""
        full_name = item.get("name", "")
        credential = Credential.from_full_name(full_name)
        
        if not credential:
            return False, None
        
        credential.item_id = item.get("id")
        credential.collection_id = item.get("collectionIds", [None])[0] if item.get("collectionIds") else None
        
        # Parse fields
        fields = {}
        
        # Type-specific parsing
        item_type = item.get("type")
        
        if item_type == 1:  # Login
            login = item.get("login", {})
            if credential.cred_type == "nas":
                fields["username"] = login.get("username", "")
                fields["password"] = login.get("password", "")
            elif credential.cred_type == "icloud":
                fields["apple_id"] = login.get("username", "")
                fields["password"] = login.get("password", "")
                # Check for app-specific password in custom fields
                for field in item.get("fields", []):
                    if field.get("name") == "app_specific_password":
                        fields["app_specific_password"] = field.get("value", "")
            elif credential.cred_type == "google-api":
                fields["client_id"] = login.get("username", "")
                fields["client_secret"] = login.get("password", "")
                for field in item.get("fields", []):
                    if field.get("name") == "refresh_token":
                        fields["refresh_token"] = field.get("value", "")
            elif credential.cred_type == "api-key":
                fields["key"] = login.get("password", "")
                for field in item.get("fields", []):
                    if field.get("name") == "endpoint":
                        fields["endpoint"] = field.get("value", "")
                    elif field.get("name") == "rate_limit":
                        fields["rate_limit"] = field.get("value", "")
        
        # Custom fields
        for field in item.get("fields", []):
            field_name = field.get("name", "")
            if field_name not in fields:
                fields[field_name] = field.get("value", "")
        
        credential.fields = fields
        return True, credential
    
    def update(self, credential: Credential) -> Tuple[bool, str]:
        """Update an existing credential.
        
        Args:
            credential: Credential with updated fields
            
        Returns:
            Tuple of (success, message)
        """
        if not credential.item_id:
            return False, "Credential has no item_id"
        
        logger.info(f"Updating credential: {credential.full_name}")
        
        # Get existing item
        success, stdout, stderr = self._run_bw(
            ["get", "item", credential.item_id, "--raw"]
        )
        
        if not success:
            return False, f"Failed to get existing item: {stderr}"
        
        try:
            existing = json.loads(stdout)
        except json.JSONDecodeError:
            return False, "Failed to parse existing item"
        
        # Update fields
        template = self._build_item_template(credential)
        template["id"] = credential.item_id
        template["createdDate"] = existing.get("createdDate")
        template["revisionDate"] = existing.get("revisionDate")
        
        # Encode template
        import base64
        template_json = json.dumps(template)
        template_b64 = base64.b64encode(template_json.encode()).decode()
        
        # Update item
        success, stdout, stderr = self._run_bw(
            ["edit", "item", credential.item_id, template_b64]
        )
        
        if not success:
            return False, stderr
        
        return True, "Updated successfully"
    
    def delete(self, project: str, cred_type: str, name: str) -> Tuple[bool, str]:
        """Delete a credential.
        
        Returns:
            Tuple of (success, message)
        """
        full_name = f"carby-studio/{project}/{cred_type}.{name}"
        logger.info(f"Deleting credential: {full_name}")
        
        # Find item
        success, credential = self.get(project, cred_type, name)
        if not success or not credential:
            return False, "Credential not found"
        
        if not credential.item_id:
            return False, "Credential has no item_id"
        
        # Delete item
        success, stdout, stderr = self._run_bw(
            ["delete", "item", credential.item_id]
        )
        
        if not success:
            return False, stderr
        
        return True, "Deleted successfully"
    
    def list_by_project(self, project: str) -> Tuple[bool, List[Credential]]:
        """List all credentials for a project.
        
        Returns:
            Tuple of (success, list of credentials)
        """
        logger.info(f"Listing credentials for project: {project}")
        
        prefix = f"carby-studio/{project}/"
        success, stdout, stderr = self._run_bw(
            ["list", "items", "--search", prefix, "--raw"]
        )
        
        if not success:
            logger.error(f"Failed to list items: {stderr}")
            return False, []
        
        credentials = []
        try:
            items = json.loads(stdout)
            for item in items:
                name = item.get("name", "")
                if name.startswith(prefix):
                    success, credential = self._parse_item(item)
                    if success and credential:
                        credentials.append(credential)
        except json.JSONDecodeError:
            logger.error("Failed to parse items")
        
        return True, credentials
    
    def list_all(self) -> Tuple[bool, List[Credential]]:
        """List all Carby Studio credentials.
        
        Returns:
            Tuple of (success, list of credentials)
        """
        logger.info("Listing all Carby Studio credentials")
        
        prefix = "carby-studio/"
        success, stdout, stderr = self._run_bw(
            ["list", "items", "--search", prefix, "--raw"]
        )
        
        if not success:
            logger.error(f"Failed to list items: {stderr}")
            return False, []
        
        credentials = []
        try:
            items = json.loads(stdout)
            for item in items:
                name = item.get("name", "")
                if name.startswith(prefix):
                    success, credential = self._parse_item(item)
                    if success and credential:
                        credentials.append(credential)
        except json.JSONDecodeError:
            logger.error("Failed to parse items")
        
        return True, credentials
    
    def exists(self, project: str, cred_type: str, name: str) -> bool:
        """Check if a credential exists."""
        success, credential = self.get(project, cred_type, name)
        return success and credential is not None
    
    def verify(self, project: str, cred_type: str, name: str) -> Tuple[bool, str]:
        """Verify a credential is accessible and complete.
        
        Returns:
            Tuple of (success, message)
        """
        success, credential = self.get(project, cred_type, name)
        
        if not success or not credential:
            return False, "Credential not found"
        
        # Check required fields based on type
        required_fields = {
            "nas": ["username", "password"],
            "icloud": ["apple_id", "password"],
            "google-api": ["client_id", "client_secret"],
            "database": ["host", "username", "password"],
            "api-key": ["key"]
        }
        
        missing = []
        for field in required_fields.get(cred_type, []):
            if field not in credential.fields or not credential.fields[field]:
                missing.append(field)
        
        if missing:
            return False, f"Missing required fields: {', '.join(missing)}"
        
        return True, "Credential verified"


def main():
    """CLI for testing Bitwarden DAO."""
    import sys
    
    dao = BitwardenDAO()
    
    if len(sys.argv) < 2:
        print("Usage: bitwarden_dao.py <command> [args]")
        print("Commands:")
        print("  list [project]           - List credentials")
        print("  get <project> <type> <name>  - Get credential")
        print("  create <project> <type> <name> [field=value...]  - Create credential")
        print("  delete <project> <type> <name>  - Delete credential")
        print("  verify <project> <type> <name>  - Verify credential")
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "list":
        if len(sys.argv) > 2:
            project = sys.argv[2]
            success, credentials = dao.list_by_project(project)
        else:
            success, credentials = dao.list_all()
        
        if success:
            print(f"Found {len(credentials)} credentials:")
            for cred in credentials:
                print(f"  - {cred.full_name}")
        else:
            print("Failed to list credentials")
    
    elif cmd == "get":
        if len(sys.argv) < 5:
            print("Usage: get <project> <type> <name>")
            sys.exit(1)
        
        project, cred_type, name = sys.argv[2:5]
        success, credential = dao.get(project, cred_type, name)
        
        if success and credential:
            print(f"Credential: {credential.full_name}")
            print(f"Fields: {list(credential.fields.keys())}")
        else:
            print("Credential not found")
    
    elif cmd == "create":
        if len(sys.argv) < 5:
            print("Usage: create <project> <type> <name> [field=value...]")
            sys.exit(1)
        
        project, cred_type, name = sys.argv[2:5]
        fields = {}
        
        for arg in sys.argv[5:]:
            if "=" in arg:
                key, value = arg.split("=", 1)
                fields[key] = value
        
        credential = Credential(
            project=project,
            cred_type=cred_type,
            name=name,
            fields=fields
        )
        
        success, result = dao.create(credential)
        print(f"{'✓' if success else '✗'} {result}")
    
    elif cmd == "delete":
        if len(sys.argv) < 5:
            print("Usage: delete <project> <type> <name>")
            sys.exit(1)
        
        project, cred_type, name = sys.argv[2:5]
        success, msg = dao.delete(project, cred_type, name)
        print(f"{'✓' if success else '✗'} {msg}")
    
    elif cmd == "verify":
        if len(sys.argv) < 5:
            print("Usage: verify <project> <type> <name>")
            sys.exit(1)
        
        project, cred_type, name = sys.argv[2:5]
        success, msg = dao.verify(project, cred_type, name)
        print(f"{'✓' if success else '✗'} {msg}")
    
    else:
        print(f"Unknown command: {cmd}")


if __name__ == "__main__":
    main()
