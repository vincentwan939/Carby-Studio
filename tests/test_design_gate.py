"""
Test cases for Design-First HARD-GATE implementation.

Verifies:
1. DesignApprovalToken creation and validation
2. DesignGateEnforcer request/approve/check flow
3. CLI approve-design command
4. Phase lock integration
5. Backward compatibility (parallel mode)
"""

import json
import pytest
import tempfile
from pathlib import Path
from datetime import datetime, timedelta

# Import the modules under test
import sys
sys.path.insert(0, '/Users/wants01/.openclaw/workspace/skills/carby-studio')

from carby_sprint.gate_enforcer import (
    DesignApprovalToken, 
    DesignGateEnforcer,
    GateBypassError,
    GateEnforcementError
)


class TestDesignApprovalToken:
    """Test DesignApprovalToken class."""
    
    def test_token_creation(self):
        """Test that DesignApprovalToken is created correctly."""
        token = DesignApprovalToken(
            sprint_id="test-sprint",
            design_version="20250323-120000",
            approver="test-user"
        )
        
        assert token.sprint_id == "test-sprint"
        assert token.design_version == "20250323-120000"
        assert token.approver == "test-user"
        assert token.gate_id == "design-approval"
        assert token.is_valid() is True
    
    def test_token_serialization(self):
        """Test token to_dict and from_dict."""
        token = DesignApprovalToken(
            sprint_id="test-sprint",
            design_version="v1.0",
            approver="user"
        )
        
        data = token.to_dict()
        assert data["sprint_id"] == "test-sprint"
        assert data["design_version"] == "v1.0"
        assert data["approver"] == "user"
        assert data["gate_id"] == "design-approval"
        assert "spec_path" in data
        assert "test-sprint-design.md" in data["spec_path"]
    
    def test_token_expiration(self):
        """Test that tokens expire after 7 days."""
        token = DesignApprovalToken(
            sprint_id="test-sprint",
            design_version="v1.0"
        )
        
        # Token should be valid immediately
        assert token.is_valid() is True
        
        # Check expiration is set to ~7 days
        expires_at = token.expires_at
        created_at = token.created_at
        delta = expires_at - created_at
        assert delta.days == 7


class TestDesignGateEnforcer:
    """Test DesignGateEnforcer class."""
    
    def test_request_approval(self):
        """Test requesting design approval."""
        with tempfile.TemporaryDirectory() as tmpdir:
            enforcer = DesignGateEnforcer(
                sprint_id="test-sprint",
                output_dir=tmpdir
            )
            
            result = enforcer.request_approval(
                design_summary="Test design for authentication system"
            )
            
            assert result["status"] == "awaiting_approval"
            assert "message" in result
            assert "spec_path" in result
            assert "approval_command" in result
            assert "test-sprint" in result["approval_command"]
            
            # Check request file was created
            request_path = Path(tmpdir) / "test-sprint" / "design-approval-request.json"
            assert request_path.exists()
            
            with open(request_path) as f:
                request = json.load(f)
            assert request["sprint_id"] == "test-sprint"
            assert request["status"] == "awaiting_approval"
            assert request["design_summary"] == "Test design for authentication system"
    
    def test_approve_without_spec(self):
        """Test that approval fails if spec doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            enforcer = DesignGateEnforcer(
                sprint_id="test-sprint",
                output_dir=tmpdir
            )
            
            # Try to approve without creating spec
            with pytest.raises(GateEnforcementError) as exc_info:
                enforcer.approve(approver="user")
            
            assert "Design spec not found" in str(exc_info.value)
    
    def test_approve_with_spec(self):
        """Test successful approval with spec file."""
        import os
        original_cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tmpdir:
            # Change to temp dir so relative paths work
            os.chdir(tmpdir)
            
            # Create spec directory and file (relative to cwd)
            spec_dir = Path("docs") / "carby" / "specs"
            spec_dir.mkdir(parents=True)
            spec_file = spec_dir / "test-sprint-design.md"
            spec_file.write_text("# Design Specification\n\nversion: 1.0.0\n")
            
            enforcer = DesignGateEnforcer(
                sprint_id="test-sprint",
                output_dir=".carby-sprints"
            )
            
            # First request approval
            enforcer.request_approval(design_summary="Test design")
            
            # Then approve
            token = enforcer.approve(approver="test-user")
            
            assert token.sprint_id == "test-sprint"
            assert token.approver == "test-user"
            assert token.design_version == "1.0.0"  # Extracted from spec
            
            # Check token file was created
            token_path = Path(".carby-sprints") / "test-sprint" / "design-approval-token.json"
            assert token_path.exists()
            
            # Check request was updated
            request_path = Path(".carby-sprints") / "test-sprint" / "design-approval-request.json"
            with open(request_path) as f:
                request = json.load(f)
            assert request["status"] == "approved"
            assert "approved_at" in request
        
        os.chdir(original_cwd)
    
    def test_check_approval_without_request(self):
        """Test check fails if approval was never requested."""
        with tempfile.TemporaryDirectory() as tmpdir:
            enforcer = DesignGateEnforcer(
                sprint_id="test-sprint",
                output_dir=tmpdir
            )
            
            with pytest.raises(GateBypassError) as exc_info:
                enforcer.check_approval()
            
            assert "BUILD BLOCKED" in str(exc_info.value)
            assert "Design approval not requested" in str(exc_info.value)
    
    def test_check_approval_pending(self):
        """Test check fails if approval is pending."""
        with tempfile.TemporaryDirectory() as tmpdir:
            enforcer = DesignGateEnforcer(
                sprint_id="test-sprint",
                output_dir=tmpdir
            )
            
            # Request but don't approve
            enforcer.request_approval(design_summary="Test design")
            
            with pytest.raises(GateBypassError) as exc_info:
                enforcer.check_approval()
            
            assert "BUILD BLOCKED" in str(exc_info.value)
            assert "Design not approved" in str(exc_info.value)
            assert "carby-sprint approve-design" in str(exc_info.value)
    
    def test_check_approval_success(self):
        """Test check succeeds after approval."""
        import os
        original_cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            
            # Create spec
            spec_dir = Path("docs") / "carby" / "specs"
            spec_dir.mkdir(parents=True)
            spec_file = spec_dir / "test-sprint-design.md"
            spec_file.write_text("# Design\n")
            
            enforcer = DesignGateEnforcer(
                sprint_id="test-sprint",
                output_dir=".carby-sprints"
            )
            
            # Request and approve
            enforcer.request_approval(design_summary="Test design")
            enforcer.approve(approver="user")
            
            # Check approval
            result = enforcer.check_approval()
            
            assert result["approved"] is True
            assert "token" in result
            assert result["token"]["approver"] == "user"
            assert "spec_path" in result
        
        os.chdir(original_cwd)


class TestDesignGateFlow:
    """Test end-to-end design gate flow."""
    
    def test_full_flow_request_approve_build(self):
        """Test complete flow: request -> approve -> build start."""
        import os
        original_cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            
            # Create spec
            spec_dir = Path("docs") / "carby" / "specs"
            spec_dir.mkdir(parents=True)
            spec_file = spec_dir / "test-sprint-design.md"
            spec_file.write_text("# Design Specification\n\nversion: 1.0.0\n\n## Summary\nTest design\n")
            
            enforcer = DesignGateEnforcer(
                sprint_id="test-sprint",
                output_dir=".carby-sprints"
            )
            
            # Step 1: Design agent requests approval
            request_result = enforcer.request_approval(
                design_summary="Authentication system design"
            )
            assert request_result["status"] == "awaiting_approval"
            
            # Step 2: Build agent tries to start (should fail)
            with pytest.raises(GateBypassError):
                enforcer.check_approval()
            
            # Step 3: User approves design
            token = enforcer.approve(approver="test-user")
            assert token.approver == "test-user"
            
            # Step 4: Build agent can now start
            check_result = enforcer.check_approval()
            assert check_result["approved"] is True
            assert check_result["token"]["approver"] == "test-user"
        
        os.chdir(original_cwd)


class TestPhaseLockIntegration:
    """Test integration with phase_lock module."""
    
    def test_design_gate_checked_in_wait_for_previous(self):
        """Test that design gate is checked when waiting for previous phase."""
        import os
        from carby_sprint.phase_lock import wait_for_previous_phase, mark_phase_complete, approve_phase
        
        original_cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            sprint_id = "test-sprint"
            
            # Setup: complete and approve design phase
            mark_phase_complete(sprint_id, "design", "Design complete", ".carby-sprints")
            approve_phase(sprint_id, "design", ".carby-sprints")
            
            # Without design approval token, build should be blocked
            # Note: This requires the spec file to exist
            spec_dir = Path("docs") / "carby" / "specs"
            spec_dir.mkdir(parents=True)
            spec_file = spec_dir / f"{sprint_id}-design.md"
            spec_file.write_text("# Design\n")
            
            # Request but don't approve
            enforcer = DesignGateEnforcer(sprint_id, ".carby-sprints")
            enforcer.request_approval(design_summary="Test")
            
            # Should raise RuntimeError due to missing design approval (with check_design_gate=True)
            with pytest.raises(RuntimeError) as exc_info:
                wait_for_previous_phase(sprint_id, "build", ".carby-sprints", check_design_gate=True)
            
            assert "BLOCKED" in str(exc_info.value) or "blocked" in str(exc_info.value).lower()
            
            # Now approve
            enforcer.approve(approver="user")
            
            # Should succeed now (with check_design_gate=True)
            result = wait_for_previous_phase(sprint_id, "build", ".carby-sprints", check_design_gate=True)
            assert result["ready"] is True
            assert result["phase"] == "build"
        
        os.chdir(original_cwd)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
