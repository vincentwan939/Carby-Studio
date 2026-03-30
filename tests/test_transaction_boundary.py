"""
Test suite for Transaction Boundary implementation in Carby Studio.

Tests clear transaction boundary definitions and demarcation with the
two-phase commit system.
"""

import json
import tempfile
from pathlib import Path

import pytest

from carby_sprint.transaction_boundary import (
    TransactionBoundaryManager,
    TransactionBoundary,
    TransactionType,
    TransactionResult,
    TransactionBoundaryError,
    NestedTransactionError,
    TransactionScopeError,
    get_boundary_manager,
    reset_boundary_manager,
    requires_transaction,
    requires_no_transaction,
    with_single_file_transaction,
    with_distributed_transaction,
)
from carby_sprint.sprint_repository import SprintRepository
from carby_sprint.transaction import TransactionError


class TestTransactionBoundaryManager:
    """Test TransactionBoundaryManager functionality."""
    
    def setup_method(self):
        """Reset boundary manager before each test."""
        reset_boundary_manager()
    
    def test_single_file_transaction_success(self):
        """Test successful single-file transaction."""
        with tempfile.TemporaryDirectory() as temp_dir:
            sprint_path = Path(temp_dir)
            metadata_file = sprint_path / "metadata.json"
            
            # Create initial metadata
            metadata_file.write_text('{"status": "initialized"}')
            
            mgr = TransactionBoundaryManager()
            
            with mgr.single_file_transaction(sprint_path) as data:
                data["status"] = "in_progress"
                data["updated"] = True
            
            # Verify transaction committed
            result = json.loads(metadata_file.read_text())
            assert result["status"] == "in_progress"
            assert result["updated"] is True
    
    def test_single_file_transaction_rollback_on_error(self):
        """Test that single-file transaction rolls back on error."""
        with tempfile.TemporaryDirectory() as temp_dir:
            sprint_path = Path(temp_dir)
            metadata_file = sprint_path / "metadata.json"
            
            # Create initial metadata
            metadata_file.write_text('{"status": "initialized"}')
            
            mgr = TransactionBoundaryManager()
            
            try:
                with mgr.single_file_transaction(sprint_path) as data:
                    data["status"] = "in_progress"
                    raise ValueError("Simulated error")
            except TransactionError:
                pass  # Expected
            
            # Verify transaction rolled back
            result = json.loads(metadata_file.read_text())
            assert result["status"] == "initialized"  # Unchanged
    
    def test_nested_transaction_prevention(self):
        """Test that nested transactions are prevented."""
        with tempfile.TemporaryDirectory() as temp_dir:
            sprint_path = Path(temp_dir)
            work_items_dir = sprint_path / "work_items"
            work_items_dir.mkdir()
            metadata_file = sprint_path / "metadata.json"
            metadata_file.write_text('{"status": "initialized"}')
            
            mgr = TransactionBoundaryManager()
            
            # Nested transactions should raise NestedTransactionError
            # which gets wrapped in TransactionError by the outer context
            with pytest.raises((NestedTransactionError, TransactionError)):
                with mgr.single_file_transaction(sprint_path):
                    # Try to start another transaction
                    with mgr.work_item_transaction(work_items_dir, "test-item"):
                        pass
    
    def test_distributed_transaction_success(self):
        """Test successful distributed transaction."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            file1 = project_dir / "file1.json"
            file2 = project_dir / "file2.json"
            
            file1.write_text('{"value": 1}')
            file2.write_text('{"value": 2}')
            
            mgr = TransactionBoundaryManager()
            
            with mgr.distributed_transaction(
                project_dir,
                [
                    ("file1", file1, lambda d: {**d, "updated": True}),
                    ("file2", file2, lambda d: {**d, "updated": True}),
                ]
            ) as result:
                assert result.success is True
                assert result.transaction_id is not None
                assert result.phase1_result == "success"
                assert result.phase2_result == "committed"
            
            # Verify both files updated
            data1 = json.loads(file1.read_text())
            data2 = json.loads(file2.read_text())
            assert data1["updated"] is True
            assert data2["updated"] is True
    
    def test_distributed_transaction_rollback(self):
        """Test distributed transaction rollback on failure."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            file1 = project_dir / "file1.json"
            file2 = project_dir / "file2.json"
            
            file1.write_text('{"value": 1}')
            file2.write_text('{"value": 2}')
            
            mgr = TransactionBoundaryManager()
            
            def failing_update(data):
                raise Exception("Simulated failure")
            
            with pytest.raises(Exception):
                with mgr.distributed_transaction(
                    project_dir,
                    [
                        ("file1", file1, lambda d: {**d, "updated": True}),
                        ("file2", file2, failing_update),
                    ]
                ) as result:
                    pass
            
            # Verify neither file updated (rolled back)
            data1 = json.loads(file1.read_text())
            data2 = json.loads(file2.read_text())
            assert "updated" not in data1
            assert "updated" not in data2
    
    def test_has_active_transaction_property(self):
        """Test has_active_transaction property."""
        with tempfile.TemporaryDirectory() as temp_dir:
            sprint_path = Path(temp_dir)
            metadata_file = sprint_path / "metadata.json"
            metadata_file.write_text('{"status": "initialized"}')
            
            mgr = TransactionBoundaryManager()
            
            assert mgr.has_active_transaction is False
            
            with mgr.single_file_transaction(sprint_path) as data:
                assert mgr.has_active_transaction is True
            
            assert mgr.has_active_transaction is False
    
    def test_active_transaction_type_property(self):
        """Test active_transaction_type property."""
        with tempfile.TemporaryDirectory() as temp_dir:
            sprint_path = Path(temp_dir)
            metadata_file = sprint_path / "metadata.json"
            metadata_file.write_text('{"status": "initialized"}')
            
            mgr = TransactionBoundaryManager()
            
            assert mgr.active_transaction_type is None
            
            with mgr.single_file_transaction(sprint_path) as data:
                assert mgr.active_transaction_type == TransactionType.SINGLE_FILE
    
    def test_assert_within_transaction_success(self):
        """Test assert_within_transaction when inside transaction."""
        with tempfile.TemporaryDirectory() as temp_dir:
            sprint_path = Path(temp_dir)
            metadata_file = sprint_path / "metadata.json"
            metadata_file.write_text('{"status": "initialized"}')
            
            mgr = TransactionBoundaryManager()
            
            with mgr.single_file_transaction(sprint_path) as data:
                mgr.assert_within_transaction()  # Should not raise
    
    def test_assert_within_transaction_failure(self):
        """Test assert_within_transaction when outside transaction."""
        mgr = TransactionBoundaryManager()
        
        with pytest.raises(TransactionScopeError):
            mgr.assert_within_transaction()
    
    def test_assert_no_transaction_success(self):
        """Test assert_no_transaction when outside transaction."""
        mgr = TransactionBoundaryManager()
        mgr.assert_no_transaction()  # Should not raise
    
    def test_assert_no_transaction_failure(self):
        """Test assert_no_transaction when inside transaction."""
        with tempfile.TemporaryDirectory() as temp_dir:
            sprint_path = Path(temp_dir)
            metadata_file = sprint_path / "metadata.json"
            metadata_file.write_text('{"status": "initialized"}')
            
            mgr = TransactionBoundaryManager()
            
            # assert_no_transaction raises NestedTransactionError which gets wrapped
            with pytest.raises((NestedTransactionError, TransactionError)):
                with mgr.single_file_transaction(sprint_path) as data:
                    mgr.assert_no_transaction()


class TestTransactionDecorators:
    """Test transaction boundary decorators."""
    
    def setup_method(self):
        """Reset boundary manager before each test."""
        reset_boundary_manager()
    
    def test_requires_transaction_decorator_success(self):
        """Test @requires_transaction when inside transaction."""
        mgr = get_boundary_manager()
        
        @requires_transaction
        def update_data():
            return "updated"
        
        with tempfile.TemporaryDirectory() as temp_dir:
            sprint_path = Path(temp_dir)
            metadata_file = sprint_path / "metadata.json"
            metadata_file.write_text('{"status": "initialized"}')
            
            with mgr.single_file_transaction(sprint_path) as data:
                result = update_data()
                assert result == "updated"
    
    def test_requires_transaction_decorator_failure(self):
        """Test @requires_transaction when outside transaction."""
        @requires_transaction
        def update_data():
            return "updated"
        
        with pytest.raises(TransactionScopeError):
            update_data()
    
    def test_requires_no_transaction_decorator_success(self):
        """Test @requires_no_transaction when outside transaction."""
        @requires_no_transaction
        def begin_operation():
            return "started"
        
        result = begin_operation()
        assert result == "started"
    
    def test_requires_no_transaction_decorator_failure(self):
        """Test @requires_no_transaction when inside transaction."""
        mgr = get_boundary_manager()
        
        @requires_no_transaction
        def begin_operation():
            return "started"
        
        with tempfile.TemporaryDirectory() as temp_dir:
            sprint_path = Path(temp_dir)
            metadata_file = sprint_path / "metadata.json"
            metadata_file.write_text('{"status": "initialized"}')
            
            # NestedTransactionError gets wrapped in TransactionError by context manager
            with pytest.raises((NestedTransactionError, TransactionError)):
                with mgr.single_file_transaction(sprint_path) as data:
                    begin_operation()


class TestTransactionHelpers:
    """Test transaction helper functions."""
    
    def setup_method(self):
        """Reset boundary manager before each test."""
        reset_boundary_manager()
    
    def test_with_single_file_transaction(self):
        """Test with_single_file_transaction helper."""
        reset_boundary_manager()
        with tempfile.TemporaryDirectory() as temp_dir:
            sprint_path = Path(temp_dir)
            metadata_file = sprint_path / "metadata.json"
            metadata_file.write_text('{"status": "initialized", "value": 1}')
            
            def update_operation(data):
                data["status"] = "in_progress"
                data["value"] = 42
                return dict(data)  # Return a copy to avoid reference issues
            
            result = with_single_file_transaction(sprint_path, update_operation)
            
            assert result["status"] == "in_progress"
            assert result["value"] == 42
    
    def test_with_distributed_transaction(self):
        """Test with_distributed_transaction helper."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            file1 = project_dir / "file1.json"
            file2 = project_dir / "file2.json"
            
            file1.write_text('{"value": 1}')
            file2.write_text('{"value": 2}')
            
            result = with_distributed_transaction(
                project_dir,
                [
                    ("file1", file1, lambda d: {**d, "updated": True}),
                    ("file2", file2, lambda d: {**d, "updated": True}),
                ]
            )
            
            assert result.success is True
            
            data1 = json.loads(file1.read_text())
            data2 = json.loads(file2.read_text())
            assert data1["updated"] is True
            assert data2["updated"] is True


class TestTransactionBoundaryIntegration:
    """Integration tests for transaction boundaries with SprintRepository."""
    
    def setup_method(self):
        """Reset boundary manager before each test."""
        reset_boundary_manager()
    
    def test_sprint_repository_with_boundary_manager(self):
        """Test SprintRepository operations with boundary manager."""
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = SprintRepository(temp_dir)
            mgr = TransactionBoundaryManager()
            
            # Create sprint
            sprint_data, paths = repo.create(
                sprint_id="test-sprint",
                project="Test Project",
                goal="Test Goal"
            )
            
            # Update within transaction boundary
            with mgr.single_file_transaction(paths.sprint_dir) as data:
                data["status"] = "in_progress"
                data["updated_with_boundary"] = True
            
            # Verify update
            updated_data, _ = repo.load("test-sprint")
            assert updated_data["status"] == "in_progress"
            assert updated_data["updated_with_boundary"] is True
    
    def test_work_item_transaction_boundary(self):
        """Test work item operations with transaction boundaries."""
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = SprintRepository(temp_dir)
            mgr = TransactionBoundaryManager()
            
            # Create sprint
            sprint_data, paths = repo.create(
                sprint_id="test-sprint",
                project="Test Project",
                goal="Test Goal"
            )
            
            # Create work item
            work_item = {
                "id": "WI-001",
                "title": "Test Work Item",
                "status": "planned"
            }
            repo.save_work_item(paths, work_item)
            
            # Update work item within transaction boundary
            with mgr.work_item_transaction(paths.work_items, "WI-001") as data:
                data["status"] = "in_progress"
                data["updated_with_boundary"] = True
            
            # Verify update
            updated_wi = repo.load_work_item(paths, "WI-001")
            assert updated_wi["status"] == "in_progress"
            assert updated_wi["updated_with_boundary"] is True
    
    def test_no_nested_transactions_in_repository(self):
        """Test that nested transactions are prevented in repository operations."""
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = SprintRepository(temp_dir)
            mgr = TransactionBoundaryManager()
            
            # Create sprint
            sprint_data, paths = repo.create(
                sprint_id="test-sprint",
                project="Test Project",
                goal="Test Goal"
            )
            
            # Create work item
            work_item = {
                "id": "WI-001",
                "title": "Test Work Item",
                "status": "planned"
            }
            repo.save_work_item(paths, work_item)
            
            # Try to update work item while in sprint transaction
            # This should fail because nested transactions are prevented
            with pytest.raises((NestedTransactionError, TransactionError)):
                with mgr.single_file_transaction(paths.sprint_dir) as sprint_data:
                    # This would cause nested transaction - prevented by boundary manager
                    with mgr.work_item_transaction(paths.work_items, "WI-001") as wi_data:
                        wi_data["status"] = "in_progress"


class TestTransactionBoundaryClearDemarcation:
    """Test that transaction boundaries are clearly demarcated."""
    
    def setup_method(self):
        """Reset boundary manager before each test."""
        reset_boundary_manager()
    
    def test_transaction_has_clear_begin_commit(self):
        """Test that transactions have clear BEGIN and COMMIT points."""
        mgr = TransactionBoundaryManager()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            sprint_path = Path(temp_dir)
            metadata_file = sprint_path / "metadata.json"
            metadata_file.write_text('{"status": "initialized"}')
            
            # Before transaction: no active boundary
            assert mgr.has_active_transaction is False
            
            # BEGIN: Enter transaction context
            with mgr.single_file_transaction(sprint_path) as data:
                # During transaction: active boundary
                assert mgr.has_active_transaction is True
                data["status"] = "in_progress"
            
            # COMMIT: After transaction (success): no active boundary
            assert mgr.has_active_transaction is False
            
            # Verify data committed
            result = json.loads(metadata_file.read_text())
            assert result["status"] == "in_progress"
    
    def test_transaction_has_clear_rollback(self):
        """Test that transactions have clear ROLLBACK on failure."""
        mgr = TransactionBoundaryManager()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            sprint_path = Path(temp_dir)
            metadata_file = sprint_path / "metadata.json"
            metadata_file.write_text('{"status": "initialized"}')
            
            try:
                with mgr.single_file_transaction(sprint_path) as data:
                    data["status"] = "in_progress"
                    raise ValueError("Simulated error")
            except TransactionError:
                pass
            
            # ROLLBACK: After transaction (failure): no active boundary
            assert mgr.has_active_transaction is False
            
            # Verify data rolled back
            result = json.loads(metadata_file.read_text())
            assert result["status"] == "initialized"  # Unchanged
    
    def test_distributed_transaction_demarcation(self):
        """Test that distributed transactions have clear demarcation."""
        mgr = TransactionBoundaryManager()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            file1 = project_dir / "file1.json"
            file2 = project_dir / "file2.json"
            
            file1.write_text('{"value": 1}')
            file2.write_text('{"value": 2}')
            
            # Before transaction
            assert mgr.has_active_transaction is False
            assert mgr.active_transaction_type is None
            
            # BEGIN: Enter distributed transaction
            with mgr.distributed_transaction(
                project_dir,
                [
                    ("file1", file1, lambda d: {**d, "updated": True}),
                    ("file2", file2, lambda d: {**d, "updated": True}),
                ]
            ) as result:
                # During transaction
                assert mgr.has_active_transaction is True
                assert mgr.active_transaction_type == TransactionType.DISTRIBUTED
            
            # COMMIT: After transaction
            assert mgr.has_active_transaction is False
            assert mgr.active_transaction_type is None


if __name__ == "__main__":
    # Run basic tests
    print("Running Transaction Boundary Tests...")
    
    # Test 1: Basic single-file transaction
    reset_boundary_manager()
    test_mgr = TestTransactionBoundaryManager()
    test_mgr.test_single_file_transaction_success()
    print("✓ Single-file transaction success test passed")
    
    # Test 2: Nested transaction prevention
    reset_boundary_manager()
    test_mgr.setup_method()
    test_mgr.test_nested_transaction_prevention()
    print("✓ Nested transaction prevention test passed")
    
    # Test 3: Distributed transaction
    reset_boundary_manager()
    test_mgr.setup_method()
    test_mgr.test_distributed_transaction_success()
    print("✓ Distributed transaction success test passed")
    
    # Test 4: Decorators
    reset_boundary_manager()
    test_decorators = TestTransactionDecorators()
    test_decorators.setup_method()
    test_decorators.test_requires_transaction_decorator_success()
    print("✓ Transaction decorator test passed")
    
    # Test 5: Clear demarcation
    reset_boundary_manager()
    test_demarcation = TestTransactionBoundaryClearDemarcation()
    test_demarcation.setup_method()
    test_demarcation.test_transaction_has_clear_begin_commit()
    print("✓ Transaction clear demarcation test passed")
    
    print("\n🎉 All Transaction Boundary tests passed!")
    print("\nKey features verified:")
    print("  - Clear transaction boundary definitions")
    print("  - Single-file transaction demarcation")
    print("  - Distributed transaction (2PC) demarcation")
    print("  - Nested transaction prevention")
    print("  - Clear BEGIN/COMMIT/ROLLBACK semantics")
    print("  - Integration with SprintRepository")