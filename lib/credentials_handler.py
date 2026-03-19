#!/usr/bin/env python3
"""
Credentials Handler for Carby Studio

Unified interface for credential management using Bitwarden.
"""

import os
import sys
import yaml
import json
import logging
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass, asdict

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent))
from bitwarden_dao import BitwardenDAO, Credential, CredentialType
from session_manager import SessionManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class CredentialStatus:
    """Status of a credential."""
    project: str
    cred_type: str
    name: str
    exists: bool
    verified: bool
    source: str  # 'bitwarden', 'gpg', 'none'
    message: str = ""


class CredentialsHandler:
    """Handles credential operations for Carby Studio projects."""
    
    SECRETS_DIR = Path.home() / ".openclaw" / "secrets" / "projects"
    
    def __init__(self):
        self.bw_dao = BitwardenDAO()
        self.session_manager = SessionManager()
    
    def _get_project_metadata(self, project: str) -> Optional[Dict]:
        """Read project metadata file."""
        metadata_file = self.SECRETS_DIR / project / "metadata.yaml"
        if not metadata_file.exists():
            return None
        
        try:
            with open(metadata_file, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Failed to read metadata: {e}")
            return None
    
    def _save_project_metadata(self, project: str, metadata: Dict):
        """Save project metadata file."""
        metadata_file = self.SECRETS_DIR / project / "metadata.yaml"
        metadata_file.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(metadata_file, 'w') as f:
                yaml.dump(metadata, f, default_flow_style=False)
        except Exception as e:
            logger.error(f"Failed to save metadata: {e}")
    
    def _get_storage_type(self, project: str) -> str:
        """Determine credential storage type for a project."""
        metadata = self._get_project_metadata(project)
        if metadata and metadata.get('storage') == 'bitwarden':
            return 'bitwarden'
        
        # Check for GPG file
        gpg_file = self.SECRETS_DIR / project / "secrets.db.gpg"
        if gpg_file.exists():
            return 'gpg'
        
        return 'none'
    
    def list_credentials(self, project: str) -> List[CredentialStatus]:
        """List all credentials for a project."""
        storage = self._get_storage_type(project)
        statuses = []
        
        if storage == 'bitwarden':
            # Get from Bitwarden
            success, credentials = self.bw_dao.list_by_project(project)
            if success:
                for cred in credentials:
                    # Check verification
                    verified, _ = self.bw_dao.verify(project, cred.cred_type, cred.name)
                    statuses.append(CredentialStatus(
                        project=project,
                        cred_type=cred.cred_type,
                        name=cred.name,
                        exists=True,
                        verified=verified,
                        source='bitwarden'
                    ))
        
        elif storage == 'gpg':
            # Get from metadata
            metadata = self._get_project_metadata(project)
            if metadata and 'credentials' in metadata:
                for key, info in metadata['credentials'].items():
                    parts = key.split('.', 1)
                    if len(parts) == 2:
                        cred_type, name = parts
                        statuses.append(CredentialStatus(
                            project=project,
                            cred_type=cred_type,
                            name=name,
                            exists=True,
                            verified=info.get('verified') is not None,
                            source='gpg'
                        ))
        
        return statuses
    
    def get_credential(self, project: str, cred_type: str, name: str) -> Tuple[bool, Optional[Dict]]:
        """Get a credential's fields."""
        storage = self._get_storage_type(project)
        
        if storage == 'bitwarden':
            success, credential = self.bw_dao.get(project, cred_type, name)
            if success and credential:
                return True, credential.fields
        
        elif storage == 'gpg':
            # Decrypt and read from GPG
            # This would require the GPG module
            logger.warning("GPG credential retrieval not yet implemented")
            return False, None
        
        return False, None
    
    def add_credential(self, project: str, cred_type: str, name: str, 
                       fields: Dict[str, str], interactive: bool = False) -> Tuple[bool, str]:
        """Add a new credential.
        
        Args:
            project: Project name
            cred_type: Credential type (nas, icloud, etc.)
            name: Credential identifier
            fields: Credential fields
            interactive: Whether to prompt for missing fields
            
        Returns:
            Tuple of (success, message)
        """
        storage = self._get_storage_type(project)
        
        # ENFORCEMENT: Bitwarden only for new credentials
        if storage == 'gpg':
            return False, (
                f"Project '{project}' uses deprecated GPG storage. "
                f"Run: carby-studio credentials migrate {project}"
            )
        
        # Default to Bitwarden for new projects
        if storage == 'none':
            storage = 'bitwarden'
        
        if storage == 'bitwarden':
            # Ensure unlocked
            success, msg = self.session_manager.ensure_unlocked()
            if not success:
                return False, f"Bitwarden not unlocked: {msg}"
            
            # Create credential
            credential = Credential(
                project=project,
                cred_type=cred_type,
                name=name,
                fields=fields
            )
            
            success, result = self.bw_dao.create(credential)
            if success:
                # Update metadata
                metadata = self._get_project_metadata(project) or {}
                if 'credentials' not in metadata:
                    metadata['credentials'] = {}
                
                metadata['credentials'][f"{cred_type}.{name}"] = {
                    'type': cred_type,
                    'name': name,
                    'added': __import__('datetime').datetime.now().isoformat(),
                    'storage': 'bitwarden'
                }
                metadata['storage'] = 'bitwarden'
                self._save_project_metadata(project, metadata)
                
                return True, f"Created in Bitwarden: {result}"
            else:
                return False, f"Failed to create: {result}"
        
        else:
            return False, f"Storage type '{storage}' not supported for adding credentials"
    
    def verify_credential(self, project: str, cred_type: str, name: str) -> Tuple[bool, str]:
        """Verify a credential is accessible and complete."""
        storage = self._get_storage_type(project)
        
        if storage == 'bitwarden':
            success, msg = self.bw_dao.verify(project, cred_type, name)
            if success:
                # Update metadata
                metadata = self._get_project_metadata(project)
                if metadata and 'credentials' in metadata:
                    key = f"{cred_type}.{name}"
                    if key in metadata['credentials']:
                        metadata['credentials'][key]['verified'] = __import__('datetime').datetime.now().isoformat()
                        self._save_project_metadata(project, metadata)
            return success, msg
        
        return False, f"Storage type '{storage}' does not support verification"