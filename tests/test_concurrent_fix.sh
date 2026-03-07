#!/bin/bash
# Test concurrent access with file locking fix

set -e

echo "=== Testing Concurrent Access Fix ==="
echo ""

# Create test project
echo "Creating test project..."
python3 team-tasks/scripts/task_manager.py init test-concurrent-fix -g "Test concurrent access" -m dag --force 2>/dev/null

# Add multiple tasks
python3 team-tasks/scripts/task_manager.py add test-concurrent-fix task1 -a code-agent --desc "Task 1" 2>/dev/null
python3 team-tasks/scripts/task_manager.py add test-concurrent-fix task2 -a test-agent --desc "Task 2" 2>/dev/null
python3 team-tasks/scripts/task_manager.py add test-concurrent-fix task3 -a docs-agent -d "task1,task2" --desc "Task 3" 2>/dev/null

echo "Starting 5 concurrent update processes..."

# Function to update task status multiple times
update_task() {
    local task=$1
    local iterations=$2
    for i in $(seq 1 $iterations); do
        python3 team-tasks/scripts/task_manager.py update test-concurrent-fix $task in-progress 2>/dev/null
        sleep 0.01
        python3 team-tasks/scripts/task_manager.py log test-concurrent-fix $task "Log entry $i" 2>/dev/null
        sleep 0.01
        python3 team-tasks/scripts/task_manager.py result test-concurrent-fix $task "Result $i" 2>/dev/null
        sleep 0.01
        python3 team-tasks/scripts/task_manager.py update test-concurrent-fix $task done 2>/dev/null
        sleep 0.01
        python3 team-tasks/scripts/task_manager.py reset test-concurrent-fix $task 2>/dev/null
        sleep 0.01
    done
}

# Run concurrent updates in background
update_task task1 5 &
PID1=$!
update_task task2 5 &
PID2=$!
update_task task1 5 &
PID3=$!
update_task task2 5 &
PID4=$!
update_task task1 5 &
PID5=$!

echo "Waiting for concurrent processes to complete..."
wait $PID1 $PID2 $PID3 $PID4 $PID5

echo ""
echo "=== Checking for data corruption ==="

# Validate JSON
if python3 -c "import json; json.load(open('${TEAM_TASKS_DIR:-$HOME/.openclaw/workspace/projects}/test-concurrent-fix.json'))" 2>/dev/null; then
    echo "✅ JSON is valid - no corruption detected!"
else
    echo "❌ JSON is corrupted!"
    exit 1
fi

# Show final status
echo ""
echo "Final status:"
python3 team-tasks/scripts/task_manager.py status test-concurrent-fix 2>/dev/null

echo ""
echo "=== Concurrent Access Fix Test Complete ==="
