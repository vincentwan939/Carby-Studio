"""Design gate enforcement."""
import json
import os
from datetime import datetime
from typing import Dict, Any
from pathlib import Path

from .gate_token import DesignApprovalToken
from .exceptions import GateEnforcementError, GateBypassError, ExpiredTokenError


class DesignGateEnforcer:
    """
    Enforces design approval before Build phase.
    Integrates with Phase Lock to avoid double-approval friction.
    """
    
    TOKEN_FILE = ".carby-sprints/{sprint_id}/design-approval-token.json"
    SPEC_DIR = "docs/carby/specs"
    
    def __init__(self, sprint_id: str, output_dir: str = ".carby-sprints"):
        self.sprint_id = sprint_id
        self.output_dir = Path(output_dir)
        self.token_path = self.output_dir / sprint_id / "design-approval-token.json"
        self.spec_path = Path(self.SPEC_DIR) / f"{sprint_id}-design.md"
        
    def request_approval(self, design_summary: str) -> Dict[str, Any]:
        """
        Called by Design agent when design is complete.
        Creates approval request, outputs spec file.
        """
        # Ensure spec directory exists
        self.spec_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create approval request file
        request = {
            "sprint_id": self.sprint_id,
            "status": "awaiting_approval",
            "design_summary": design_summary,
            "spec_path": str(self.spec_path),
            "requested_at": datetime.utcnow().isoformat(),
            "approval_command": f"carby-sprint approve-design {self.sprint_id}"
        }
        
        request_path = self.output_dir / self.sprint_id / "design-approval-request.json"
        request_path.parent.mkdir(parents=True, exist_ok=True)
        with open(request_path, 'w') as f:
            json.dump(request, f, indent=2)
            
        return {
            "status": "awaiting_approval",
            "message": f"Design complete. Awaiting approval.",
            "spec_path": str(self.spec_path),
            "approval_command": request["approval_command"]
        }
        
    def approve(self, approver: str = "user") -> DesignApprovalToken:
        """
        Called by CLI when user approves design.
        Issues cryptographically signed token.
        """
        # Verify spec exists
        if not self.spec_path.exists():
            raise GateEnforcementError(
                f"Design spec not found: {self.spec_path}\n"
                f"Design agent must output spec before approval."
            )
            
        # Create and save token
        token = DesignApprovalToken(
            sprint_id=self.sprint_id,
            design_version=self._get_design_version(),
            approver=approver
        )
        
        self.token_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.token_path, 'w') as f:
            json.dump(token.to_dict(), f, indent=2)
        os.chmod(self.token_path, 0o600)  # Owner read/write only
            
        # Update approval request
        request_path = self.output_dir / self.sprint_id / "design-approval-request.json"
        if request_path.exists():
            with open(request_path) as f:
                request = json.load(f)
            request["status"] = "approved"
            request["approved_at"] = datetime.utcnow().isoformat()
            with open(request_path, 'w') as f:
                json.dump(request, f, indent=2)
                
        return token
        
    def check_approval(self) -> Dict[str, Any]:
        """
        Called by Build agent before starting.
        Returns token if approved, raises error if not.
        """
        if not self.token_path.exists():
            # Check if approval was requested
            request_path = self.output_dir / self.sprint_id / "design-approval-request.json"
            if request_path.exists():
                with open(request_path) as f:
                    request = json.load(f)
                raise GateBypassError(
                    f"⛔ BUILD BLOCKED: Design not approved.\n\n"
                    f"   Status: {request['status']}\n"
                    f"   Spec: {request['spec_path']}\n\n"
                    f"   To approve:\n"
                    f"   $ carby-sprint approve-design {self.sprint_id}\n\n"
                    f"   Or review spec first:\n"
                    f"   $ cat {request['spec_path']}"
                )
            else:
                raise GateBypassError(
                    f"⛔ BUILD BLOCKED: Design approval not requested.\n\n"
                    f"   Design agent must complete and request approval.\n"
                    f"   Expected spec: {self.spec_path}"
                )
                
        # Validate token
        with open(self.token_path) as f:
            token_data = json.load(f)
            
        token = DesignApprovalToken.from_dict(token_data)
        if not token.is_valid():
            raise TokenExpiredError(
                f"⛔ BUILD BLOCKED: Design approval token expired.\n\n"
                f"   Approved: {token.approved_at}\n"
                f"   Expired: {token.expires_at}\n\n"
                f"   Re-approve with:\n"
                f"   $ carby-sprint approve-design {self.sprint_id}"
            )
            
        return {
            "approved": True,
            "token": token.to_dict(),
            "spec_path": str(self.spec_path)
        }

    def _get_design_version(self) -> str:
        """Extract version from spec file or generate timestamp."""
        if self.spec_path.exists():
            content = self.spec_path.read_text()
            # Look for version header
            for line in content.split('\n')[:20]:
                if line.startswith('version:'):
                    return line.split(':', 1)[1].strip()
        return datetime.utcnow().strftime('%Y%m%d-%H%M%S')
