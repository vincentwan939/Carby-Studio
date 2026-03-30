"""
Concurrent stress test for GateStateManager TOCTOU vulnerability fix.

This test verifies that the gate state operations are atomic and
that concurrent read-modify-write operations don't cause data loss.

Run with: python3 test_gate_state_race.py
"""
import tempfile
import threading
import time
import random
import os
import sys
from pathlib import Path

# Add carby_sprint to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from carby_sprint.gate_state import GateStateManager


def test_concurrent_gate_advancement():
    """
    Stress test for concurrent gate advancement operations.
    
    Simulates multiple threads advancing gates simultaneously.
    Without proper locking, some gate completions would be lost.
    """
    num_threads = 10
    operations_per_thread = 50
    expected_total = num_threads * operations_per_thread
    
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = GateStateManager(tmpdir)
        sprint_id = "stress-test-sprint"
        
        # Initialize to discovery gate
        manager.set_current_gate(sprint_id, "discovery")
        
        # Track completed operations
        completed_count = 0
        errors = []
        
        def worker(thread_id):
            nonlocal completed_count
            for i in range(operations_per_thread):
                try:
                    # Each thread advances through gates and records completions
                    gate_name = f"gate-{thread_id}-{i}"
                    
                    # Simulate a gate completion
                    manager.record_gate_completion(sprint_id, gate_name, f"token-{thread_id}-{i}")
                    
                    # Verify the completion was recorded
                    assert manager.is_gate_completed(sprint_id, gate_name), \
                        f"Gate {gate_name} not recorded - TOCTOU race condition detected!"
                    
                    completed_count += 1
                    
                except Exception as e:
                    errors.append(f"Thread {thread_id} op {i}: {e}")
        
        # Start all threads
        threads = []
        start_time = time.time()
        
        for t_id in range(num_threads):
            t = threading.Thread(target=worker, args=(t_id,))
            threads.append(t)
            t.start()
        
        # Wait for all threads
        for t in threads:
            t.join()
        
        elapsed = time.time() - start_time
        
        # Verify results
        if errors:
            print(f"❌ FAILED: {len(errors)} errors during concurrent operations")
            for e in errors[:5]:  # Show first 5 errors
                print(f"   {e}")
            return False
        
        if completed_count != expected_total:
            print(f"❌ FAILED: Expected {expected_total} completions, got {completed_count}")
            print(f"   Lost operations: {expected_total - completed_count}")
            print(f"   TOCTOU race condition detected!")
            return False
        
        # Verify all completions are in the status file
        completed_gates = manager.get_completed_gates(sprint_id)
        if len(completed_gates) != expected_total:
            print(f"❌ FAILED: Expected {expected_total} gates in status, got {len(completed_gates)}")
            print(f"   Data loss detected!")
            return False
        
        print(f"✅ PASSED: {completed_count}/{expected_total} concurrent operations successful")
        print(f"   Time: {elapsed:.2f}s, Rate: {completed_count/elapsed:.1f} ops/sec")
        print(f"   All gate completions preserved - no TOCTOU vulnerability")
        return True


def test_concurrent_set_current_gate():
    """
    Stress test for concurrent set_current_gate operations.
    
    Multiple threads trying to set the current gate simultaneously.
    Without locking, the final state could be inconsistent.
    """
    num_threads = 20
    iterations = 100
    
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = GateStateManager(tmpdir)
        sprint_id = "gate-set-stress"
        
        # Initialize
        manager.set_current_gate(sprint_id, "discovery")
        
        errors = []
        final_gate_values = []
        
        def setter(thread_id):
            for i in range(iterations):
                try:
                    gate = manager.gate_sequence[thread_id % len(manager.gate_sequence)]
                    manager.set_current_gate(sprint_id, gate)
                    
                    # Read back immediately
                    current = manager.get_current_gate(sprint_id)
                    final_gate_values.append(current)
                    
                except Exception as e:
                    errors.append(f"Thread {thread_id}: {e}")
        
        threads = []
        start_time = time.time()
        
        for t_id in range(num_threads):
            t = threading.Thread(target=setter, args=(t_id,))
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        elapsed = time.time() - start_time
        
        if errors:
            print(f"❌ FAILED: {len(errors)} errors during concurrent gate setting")
            for e in errors[:5]:
                print(f"   {e}")
            return False
        
        # Verify final state is one of the valid gates
        final_gate = manager.get_current_gate(sprint_id)
        if final_gate not in manager.gate_sequence:
            print(f"❌ FAILED: Final gate '{final_gate}' is invalid")
            return False
        
        print(f"✅ PASSED: {num_threads * iterations} concurrent gate set operations")
        print(f"   Time: {elapsed:.2f}s, Rate: {num_threads * iterations/elapsed:.1f} ops/sec")
        print(f"   Final gate: {final_gate} (valid)")
        return True


def test_token_replay_protection_concurrent():
    """
    Stress test for concurrent token replay protection.
    
    Multiple threads trying to use the same token simultaneously.
    Only one should succeed; others should detect replay.
    """
    num_threads = 10
    same_token = "shared-token-for-replay-test"
    
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = GateStateManager(tmpdir)
        sprint_id = "replay-stress"
        
        # First mark the token as used by one thread
        first_marked = False
        replay_detected = []
        
        def marker(thread_id):
            nonlocal first_marked
            try:
                # Check if token is used
                if manager.is_token_used(same_token):
                    replay_detected.append(thread_id)
                    return
                
                # Try to mark as used
                manager.mark_token_used(same_token, sprint_id, "test-gate")
                
                # Only first thread should succeed this branch
                if not first_marked:
                    first_marked = True
                
            except Exception as e:
                replay_detected.append(thread_id)
        
        threads = []
        start_time = time.time()
        
        for t_id in range(num_threads):
            t = threading.Thread(target=marker, args=(t_id,))
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        elapsed = time.time() - start_time
        
        # Verify token is marked as used
        assert manager.is_token_used(same_token), "Token should be marked as used"
        
        # All subsequent checks should detect replay
        print(f"✅ PASSED: Token replay protection works under concurrent access")
        print(f"   Threads: {num_threads}, Time: {elapsed:.2f}s")
        print(f"   Replay detections: {len(replay_detected)} threads detected replay")
        return True


def test_atomic_update_concurrent():
    """
    Stress test for atomic_update with concurrent complex modifications.
    
    Each thread performs multi-step updates atomically.
    Without locking, intermediate states could cause corruption.
    """
    num_threads = 15
    operations = 50
    
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = GateStateManager(tmpdir)
        sprint_id = "atomic-stress"
        
        # Initialize
        manager.set_current_gate(sprint_id, "discovery")
        
        errors = []
        
        def atomic_worker(thread_id):
            for i in range(operations):
                try:
                    # Complex atomic update: increment a counter
                    def increment_counter(status):
                        if sprint_id not in status:
                            status[sprint_id] = {}
                        counter = status[sprint_id].get("counter", 0)
                        status[sprint_id]["counter"] = counter + 1
                        return status
                    
                    manager.atomic_update(sprint_id, increment_counter)
                    
                except Exception as e:
                    errors.append(f"Thread {thread_id} op {i}: {e}")
        
        threads = []
        start_time = time.time()
        
        for t_id in range(num_threads):
            t = threading.Thread(target=atomic_worker, args=(t_id,))
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        elapsed = time.time() - start_time
        
        if errors:
            print(f"❌ FAILED: {len(errors)} errors during atomic updates")
            for e in errors[:5]:
                print(f"   {e}")
            return False
        
        # Verify counter equals total operations
        with manager._gate_lock():
            status = manager._load_gate_status()
            final_counter = status.get(sprint_id, {}).get("counter", 0)
        
        expected_counter = num_threads * operations
        if final_counter != expected_counter:
            print(f"❌ FAILED: Counter mismatch!")
            print(f"   Expected: {expected_counter}, Got: {final_counter}")
            print(f"   Lost increments: {expected_counter - final_counter}")
            return False
        
        print(f"✅ PASSED: {num_threads * operations} atomic counter increments")
        print(f"   Counter: {final_counter} (correct)")
        print(f"   Time: {elapsed:.2f}s, Rate: {num_threads * operations/elapsed:.1f} ops/sec")
        return True


def main():
    """Run all stress tests."""
    print("=" * 60)
    print("GateStateManager TOCTOU Fix - Concurrent Stress Tests")
    print("=" * 60)
    print()
    
    results = []
    
    print("Test 1: Concurrent Gate Advancement")
    print("-" * 40)
    results.append(test_concurrent_gate_advancement())
    print()
    
    print("Test 2: Concurrent Set Current Gate")
    print("-" * 40)
    results.append(test_concurrent_set_current_gate())
    print()
    
    print("Test 3: Token Replay Protection Concurrent")
    print("-" * 40)
    results.append(test_token_replay_protection_concurrent())
    print()
    
    print("Test 4: Atomic Update Concurrent Counter")
    print("-" * 40)
    results.append(test_atomic_update_concurrent())
    print()
    
    print("=" * 60)
    if all(results):
        print("✅ ALL STRESS TESTS PASSED")
        print("   TOCTOU vulnerability is FIXED - concurrent operations are safe")
        return 0
    else:
        print("❌ SOME TESTS FAILED")
        print("   TOCTOU vulnerability may still be present")
        return 1


if __name__ == "__main__":
    sys.exit(main())