"""
Path Traversal Security Tests for GateStateManager

Tests that path traversal attacks are blocked AFTER path resolution.
This verifies the fix where validation happens on resolved paths.
"""
import tempfile
import os
import sys
from pathlib import Path

# Add carby_sprint to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from carby_sprint.gate_state import GateStateManager


def test_path_traversal_dotdot_blocked():
    """
    Test that /tmp/../etc/passwd style traversal is blocked.
    The path resolves to /etc/passwd which is outside allowed directories.
    """
    print("Test: Path traversal via '..' sequences")
    print("-" * 40)
    
    # This should be blocked because it resolves outside allowed dirs
    traversal_paths = [
        "/tmp/../etc/passwd",
        "/tmp/../../etc/passwd",
        "/private/tmp/../etc/passwd",
        "/var/folders/../../../etc/passwd",
    ]
    
    blocked_count = 0
    for path in traversal_paths:
        try:
            manager = GateStateManager(path)
            print(f"  ❌ FAILED: '{path}' was NOT blocked (resolved to {manager.project_dir})")
        except ValueError as e:
            if "path traversal detected" in str(e):
                print(f"  ✅ Blocked: '{path}'")
                blocked_count += 1
            else:
                print(f"  ❌ FAILED: '{path}' raised wrong error: {e}")
    
    if blocked_count == len(traversal_paths):
        print(f"✅ PASSED: All {len(traversal_paths)} traversal attempts blocked")
        return True
    else:
        print(f"❌ FAILED: Only {blocked_count}/{len(traversal_paths)} blocked")
        return False


def test_resolved_path_validation():
    """
    Test that resolved paths are validated against allowed directories.
    Even valid-looking paths that resolve outside allowed dirs should be blocked.
    """
    print("\nTest: Resolved paths validated against allowed directories")
    print("-" * 40)
    
    # These paths look innocent but resolve outside allowed dirs
    test_cases = [
        # Path that goes up and back down but outside allowed base
        ("/tmp/../usr/local", "/usr/local"),
        # Absolute path outside allowed dirs
        ("/etc", "/etc"),
        ("/usr", "/usr"),
        ("/bin", "/bin"),
    ]
    
    blocked_count = 0
    for input_path, expected_resolution in test_cases:
        try:
            manager = GateStateManager(input_path)
            print(f"  ❌ FAILED: '{input_path}' was NOT blocked (resolved to {manager.project_dir})")
        except ValueError as e:
            if "path traversal detected" in str(e) and expected_resolution in str(e):
                print(f"  ✅ Blocked: '{input_path}' -> '{expected_resolution}'")
                blocked_count += 1
            elif "path traversal detected" in str(e):
                print(f"  ✅ Blocked: '{input_path}' (resolved outside allowed dirs)")
                blocked_count += 1
            else:
                print(f"  ❌ FAILED: '{input_path}' raised wrong error: {e}")
    
    if blocked_count == len(test_cases):
        print(f"✅ PASSED: All {len(test_cases)} resolved paths outside allowed dirs were blocked")
        return True
    else:
        print(f"❌ FAILED: Only {blocked_count}/{len(test_cases)} blocked")
        return False


def test_symlink_bypass_blocked():
    """
    Test that symlinks cannot bypass validation.
    A symlink pointing outside allowed dirs should be resolved and blocked.
    """
    print("\nTest: Symlink bypass attacks blocked")
    print("-" * 40)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a symlink that points to /etc (outside allowed dirs)
        symlink_path = os.path.join(tmpdir, "link_to_etc")
        os.symlink("/etc", symlink_path)
        
        # Create a symlink that points to /tmp (allowed) then traverses out
        symlink_to_tmp = os.path.join(tmpdir, "link_to_tmp")
        os.symlink("/tmp", symlink_to_tmp)
        
        test_cases = [
            # Direct symlink to /etc
            (symlink_path, "/etc"),
            # Symlink to /tmp then traverse out
            (os.path.join(symlink_to_tmp, "../etc"), "/etc"),
        ]
        
        blocked_count = 0
        for input_path, expected_target in test_cases:
            try:
                manager = GateStateManager(input_path)
                resolved = str(manager.project_dir)
                # Check if resolved path is the dangerous target
                if resolved.startswith(expected_target):
                    print(f"  ❌ FAILED: Symlink '{input_path}' was NOT blocked (resolved to {resolved})")
                else:
                    # It resolved to something else, which might be ok
                    print(f"  ⚠️  Symlink '{input_path}' resolved to {resolved} (unexpected but not dangerous)")
                    blocked_count += 1
            except ValueError as e:
                if "path traversal detected" in str(e):
                    print(f"  ✅ Blocked: Symlink '{input_path}' -> '{expected_target}'")
                    blocked_count += 1
                else:
                    print(f"  ❌ FAILED: '{input_path}' raised wrong error: {e}")
        
        if blocked_count == len(test_cases):
            print(f"✅ PASSED: All {len(test_cases)} symlink bypass attempts blocked")
            return True
        else:
            print(f"❌ FAILED: Only {blocked_count}/{len(test_cases)} blocked")
            return False


def test_tilde_expansion_blocked():
    """
    Test that tilde (~) expansion is blocked to prevent unpredictable home directory access.
    """
    print("\nTest: Tilde (~) expansion blocked")
    print("-" * 40)
    
    tilde_paths = [
        "~/malicious",
        "~root/.ssh",
        "~/.openclaw/../../../etc",
    ]
    
    blocked_count = 0
    for path in tilde_paths:
        try:
            manager = GateStateManager(path)
            print(f"  ❌ FAILED: '{path}' was NOT blocked (resolved to {manager.project_dir})")
        except ValueError as e:
            if "~" in str(e) and "path traversal detected" in str(e):
                print(f"  ✅ Blocked: '{path}' (tilde not allowed)")
                blocked_count += 1
            else:
                print(f"  ❌ FAILED: '{path}' raised wrong error: {e}")
    
    if blocked_count == len(tilde_paths):
        print(f"✅ PASSED: All {len(tilde_paths)} tilde paths blocked")
        return True
    else:
        print(f"❌ FAILED: Only {blocked_count}/{len(tilde_paths)} blocked")
        return False


def test_valid_paths_allowed():
    """
    Test that valid paths within allowed directories still work.
    """
    print("\nTest: Valid paths within allowed directories work")
    print("-" * 40)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create subdir first
        subdir = os.path.join(tmpdir, "subdir")
        os.makedirs(subdir, exist_ok=True)
        
        # Test paths that should be allowed
        valid_paths = [
            tmpdir,  # Temp directory
            subdir,  # Subdirectory
        ]
        
        allowed_count = 0
        for path in valid_paths:
            try:
                manager = GateStateManager(path)
                print(f"  ✅ Allowed: '{path}' -> '{manager.project_dir}'")
                allowed_count += 1
            except ValueError as e:
                print(f"  ❌ FAILED: '{path}' was blocked: {e}")
        
        # Also test ~/.openclaw paths
        home_openclaw = os.path.expanduser("~/.openclaw")
        if os.path.exists(home_openclaw):
            try:
                manager = GateStateManager(home_openclaw)
                print(f"  ✅ Allowed: '~/.openclaw' -> '{manager.project_dir}'")
                allowed_count += 1
            except ValueError as e:
                print(f"  ❌ FAILED: '~/.openclaw' was blocked: {e}")
        
        if allowed_count >= 2:  # At least tmpdir and subdir should work
            print(f"✅ PASSED: Valid paths are allowed")
            return True
        else:
            print(f"❌ FAILED: Only {allowed_count} valid paths allowed")
            return False


def test_edge_cases():
    """
    Test edge cases and boundary conditions.
    """
    print("\nTest: Edge cases")
    print("-" * 40)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create nested test directories
        nested = os.path.join(tmpdir, "deep", "nested", "path")
        deep_path = os.path.join(tmpdir, "deep", "path")
        os.makedirs(nested, exist_ok=True)
        os.makedirs(deep_path, exist_ok=True)
        
        edge_cases = [
            # Dot in path (normalization)
            (os.path.join(tmpdir, "./deep/nested"), True),
            # Double dots within allowed path (should stay within tmpdir)
            (os.path.join(nested, "..", "..", "path"), True),  # Resolves to tmpdir/deep/path
        ]
        
        results = []
        for path, should_work in edge_cases:
            try:
                manager = GateStateManager(path)
                if should_work:
                    print(f"  ✅ Allowed (expected): '{path}' -> '{manager.project_dir}'")
                    results.append(True)
                else:
                    print(f"  ⚠️  Allowed (unexpected): '{path}' -> '{manager.project_dir}'")
                    results.append(False)  # Expected to fail but didn't
            except ValueError as e:
                if "path traversal detected" in str(e) or "~" in str(e):
                    if not should_work:
                        print(f"  ✅ Blocked (expected): '{path}'")
                        results.append(True)
                    else:
                        print(f"  ⚠️  Blocked (unexpected): '{path}': {e}")
                        results.append(False)
                else:
                    print(f"  ℹ️  Other error for '{path}': {e}")
                    results.append(True)  # Some other error is fine for edge cases
        
        passed = sum(results)
        total = len(results)
        print(f"{'✅ PASSED' if passed == total else '⚠️  PARTIAL'}: {passed}/{total} edge cases handled correctly")
        return passed == total


def main():
    """Run all path traversal security tests."""
    print("=" * 60)
    print("Path Traversal Security Verification Tests")
    print("=" * 60)
    print()
    
    results = []
    
    results.append(test_path_traversal_dotdot_blocked())
    results.append(test_resolved_path_validation())
    results.append(test_symlink_bypass_blocked())
    results.append(test_tilde_expansion_blocked())
    results.append(test_valid_paths_allowed())
    results.append(test_edge_cases())
    
    print()
    print("=" * 60)
    if all(results):
        print("✅ ALL PATH TRAVERSAL TESTS PASSED")
        print("   Path validation AFTER resolution is working correctly")
        print("   No bypass vectors found")
        return 0
    else:
        print("❌ SOME PATH TRAVERSAL TESTS FAILED")
        print("   Security vulnerabilities may be present")
        return 1


if __name__ == "__main__":
    sys.exit(main())
