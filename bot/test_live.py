#!/usr/bin/env python3
"""
Live Bot Testing - Tests against the actual running bot process
Uses the state_manager directly to verify operations
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from state_manager import StateManager
from safety import SafetyManager


def test_delete_confirmation_flow():
    """Test the delete confirmation flow directly."""
    print("\n🔍 Testing Delete Confirmation Flow")
    print("-" * 50)
    
    state_manager = StateManager()
    safety = SafetyManager(state_manager)
    
    test_project = "test-delete-flow"
    
    # Test 1: Request confirmation
    print("\n1. Requesting delete confirmation...")
    code = safety.request_delete_confirmation(test_project)
    print(f"   Confirmation code: '{code}'")
    assert code == "DELETE", f"Expected 'DELETE', got '{code}'"
    print("   ✅ Confirmation code is 'DELETE'")
    
    # Test 2: Verify correct confirmation
    print("\n2. Verifying with 'DELETE'...")
    result = safety.verify_delete_confirmation(test_project, "DELETE")
    print(f"   Result: {result}")
    assert result == True, "Should accept 'DELETE'"
    print("   ✅ Accepted 'DELETE'")
    
    # Test 3: Request again (should work after first verify consumed it)
    print("\n3. Requesting new confirmation...")
    code = safety.request_delete_confirmation(test_project)
    
    # Test 4: Verify with wrong input
    print("\n4. Verifying with 'NO' (wrong)...")
    result = safety.verify_delete_confirmation(test_project, "NO")
    print(f"   Result: {result}")
    assert result == False, "Should reject 'NO'"
    print("   ✅ Rejected 'NO'")
    
    # Test 5: Verify case insensitive
    print("\n5. Requesting confirmation...")
    code = safety.request_delete_confirmation(test_project)
    
    print("6. Verifying with 'delete' (lowercase)...")
    result = safety.verify_delete_confirmation(test_project, "delete")
    print(f"   Result: {result}")
    assert result == True, "Should accept lowercase 'delete'"
    print("   ✅ Accepted lowercase 'delete'")
    
    # Test 6: Verify with whitespace
    print("\n7. Requesting confirmation...")
    code = safety.request_delete_confirmation(test_project)
    
    print("8. Verifying with '  DELETE  ' (with spaces)...")
    result = safety.verify_delete_confirmation(test_project, "  DELETE  ")
    print(f"   Result: {result}")
    assert result == True, "Should accept 'DELETE' with whitespace"
    print("   ✅ Accepted with whitespace")
    
    # Test 7: Double verification should fail (confirmation consumed)
    print("\n9. Verifying again with 'DELETE' (should fail - already consumed)...")
    result = safety.verify_delete_confirmation(test_project, "DELETE")
    print(f"   Result: {result}")
    assert result == False, "Should reject - confirmation already used"
    print("   ✅ Correctly rejected - confirmation was consumed")
    
    print("\n" + "-" * 50)
    print("✅ All delete confirmation tests PASSED")
    return True


def test_state_manager_consistency():
    """Test that state manager operations are consistent."""
    print("\n🔍 Testing State Manager Consistency")
    print("-" * 50)
    
    state_manager = StateManager()
    
    # List projects
    projects = state_manager.list_projects()
    print(f"\n1. Listed {len(projects)} projects from cache")
    
    # Test get_project_summary for each
    print("\n2. Getting summaries...")
    for pid in projects[:3]:  # Test first 3
        summary = state_manager.get_project_summary(pid)
        if summary:
            print(f"   ✅ {pid}: status={summary.get('current_status', 'unknown')}")
        else:
            print(f"   ⚠️ {pid}: no summary")
    
    print("\n" + "-" * 50)
    print("✅ State manager tests PASSED")
    return True


def test_format_delete_preview():
    """Test delete preview formatting."""
    print("\n🔍 Testing Delete Preview Formatting")
    print("-" * 50)
    
    state_manager = StateManager()
    safety = SafetyManager(state_manager)
    
    # Use an existing project
    projects = state_manager.list_projects()
    if not projects:
        print("   ⚠️ No projects to test with")
        return True
        
    test_project = projects[0]
    print(f"\n1. Testing with project: {test_project}")
    
    # Check delete
    check = safety.check_delete(test_project)
    print(f"   Allowed: {check.allowed}")
    print(f"   Reason: {check.reason}")
    
    if check.allowed:
        # Format preview
        preview = safety.format_delete_preview(test_project, check.details or {})
        print(f"\n2. Preview:\n{preview}")
        
        # Verify preview contains expected elements
        assert "Delete" in preview or "delete" in preview.lower(), "Should mention delete"
        assert test_project in preview, "Should mention project name"
        print("   ✅ Preview contains required elements")
    else:
        print(f"   ⚠️ Delete not allowed: {check.reason}")
    
    print("\n" + "-" * 50)
    print("✅ Delete preview tests PASSED")
    return True


def run_all_tests():
    """Run all live tests."""
    print("=" * 60)
    print("🧪 LIVE BOT COMPONENT TESTS")
    print("=" * 60)
    
    results = []
    
    try:
        results.append(("Delete Confirmation Flow", test_delete_confirmation_flow()))
        results.append(("State Manager Consistency", test_state_manager_consistency()))
        results.append(("Delete Preview Formatting", test_format_delete_preview()))
    except Exception as e:
        print(f"\n❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Exception", False))
    
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status}: {name}")
    
    print(f"\nTotal: {total} | ✅ Passed: {passed} | ❌ Failed: {total - passed}")
    print(f"Success Rate: {passed/total*100:.1f}%")
    print("=" * 60)
    
    return all(r for _, r in results)


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
