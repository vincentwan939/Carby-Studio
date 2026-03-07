#!/usr/bin/env python3
"""Carby Studio Metrics Collection

Tracks pipeline performance, success rates, and execution metrics.
Stores data in JSONL format for easy analysis.
"""

import json
import os
import time
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

# Default metrics directory
DEFAULT_METRICS_DIR = Path.home() / ".openclaw" / "workspace" / "metrics"


class MetricsCollector:
    """Collects and manages Carby Studio execution metrics."""
    
    def __init__(self, metrics_dir: Optional[str] = None):
        self.metrics_dir = Path(metrics_dir) if metrics_dir else DEFAULT_METRICS_DIR
        self.metrics_dir.mkdir(parents=True, exist_ok=True)
        self.session_id = self._generate_session_id()
        
    def _generate_session_id(self) -> str:
        """Generate a unique session ID."""
        return hashlib.md5(str(time.time()).encode()).hexdigest()[:8]
    
    def _get_log_file(self) -> Path:
        """Get the log file for today."""
        date_str = datetime.now().strftime("%Y-%m-%d")
        return self.metrics_dir / f"carby-metrics-{date_str}.jsonl"
    
    def record(self, event_type: str, **kwargs) -> None:
        """Record a metric event.
        
        Args:
            event_type: Type of event (pipeline_start, stage_complete, etc.)
            **kwargs: Additional event data
        """
        event = {
            "timestamp": datetime.now().isoformat(),
            "session_id": self.session_id,
            "event_type": event_type,
            "data": kwargs
        }
        
        log_file = self._get_log_file()
        with open(log_file, "a") as f:
            f.write(json.dumps(event) + "\n")
    
    def record_pipeline_start(self, project: str, mode: str) -> None:
        """Record pipeline start."""
        self.record("pipeline_start", project=project, mode=mode)
    
    def record_pipeline_complete(self, project: str, mode: str, 
                                  duration_ms: int, success: bool) -> None:
        """Record pipeline completion."""
        self.record("pipeline_complete", project=project, mode=mode,
                   duration_ms=duration_ms, success=success)
    
    def record_stage_start(self, project: str, stage: str, 
                           agent: str) -> None:
        """Record stage start."""
        self.record("stage_start", project=project, stage=stage, 
                   agent=agent, start_time=datetime.now().isoformat())
    
    def record_stage_complete(self, project: str, stage: str,
                              duration_ms: int, success: bool,
                              validation_score: Optional[float] = None) -> None:
        """Record stage completion."""
        data = {
            "project": project,
            "stage": stage,
            "duration_ms": duration_ms,
            "success": success
        }
        if validation_score is not None:
            data["validation_score"] = validation_score
        self.record("stage_complete", **data)
    
    def record_command(self, command: str, duration_ms: int, 
                       args: Optional[str] = None) -> None:
        """Record command execution."""
        args_hash = hashlib.md5((args or "").encode()).hexdigest()[:8] if args else None
        self.record("command_execution", command=command, 
                   duration_ms=duration_ms, args_hash=args_hash)
    
    def record_model_call(self, model: str, stage: str,
                          tokens_in: int, tokens_out: int,
                          duration_ms: int) -> None:
        """Record model API call."""
        self.record("model_call", model=model, stage=stage,
                   tokens_in=tokens_in, tokens_out=tokens_out,
                   duration_ms=duration_ms)
    
    def record_retry(self, project: str, stage: str, 
                     retry_count: int, reason: str) -> None:
        """Record a retry event."""
        self.record("retry", project=project, stage=stage,
                   retry_count=retry_count, reason=reason)
    
    def record_failure(self, project: str, stage: str, 
                       reason: str) -> None:
        """Record a failure."""
        self.record("failure", project=project, stage=stage, reason=reason)
    
    def get_summary(self, days: int = 7) -> Dict[str, Any]:
        """Get metrics summary for the last N days.
        
        Returns:
            Dictionary with aggregated metrics
        """
        events = self._load_events(days)
        
        # Initialize counters
        total_pipelines = 0
        successful_pipelines = 0
        stage_counts = {}
        stage_success = {}
        stage_durations = {}
        failure_reasons = {}
        
        for event in events:
            event_type = event.get("event_type")
            data = event.get("data", {})
            
            if event_type == "pipeline_complete":
                total_pipelines += 1
                if data.get("success"):
                    successful_pipelines += 1
            
            elif event_type == "stage_complete":
                stage = data.get("stage", "unknown")
                stage_counts[stage] = stage_counts.get(stage, 0) + 1
                
                if data.get("success"):
                    stage_success[stage] = stage_success.get(stage, 0) + 1
                
                duration = data.get("duration_ms", 0)
                if stage not in stage_durations:
                    stage_durations[stage] = []
                stage_durations[stage].append(duration)
            
            elif event_type == "failure":
                reason = data.get("reason", "unknown")
                failure_reasons[reason] = failure_reasons.get(reason, 0) + 1
        
        # Calculate averages
        avg_stage_duration = {}
        for stage, durations in stage_durations.items():
            avg_stage_duration[stage] = sum(durations) / len(durations) if durations else 0
        
        # Calculate success rates
        stage_success_rates = {}
        for stage in stage_counts:
            success_count = stage_success.get(stage, 0)
            total_count = stage_counts[stage]
            stage_success_rates[stage] = (success_count / total_count * 100) if total_count > 0 else 0
        
        return {
            "period_days": days,
            "total_pipelines": total_pipelines,
            "successful_pipelines": successful_pipelines,
            "pipeline_success_rate": (successful_pipelines / total_pipelines * 100) 
                                      if total_pipelines > 0 else 0,
            "stage_counts": stage_counts,
            "stage_success_rates": stage_success_rates,
            "avg_stage_duration_ms": avg_stage_duration,
            "failure_reasons": failure_reasons
        }
    
    def _load_events(self, days: int) -> List[Dict]:
        """Load events from the last N days."""
        events = []
        
        for i in range(days):
            date = datetime.now() - __import__('datetime').timedelta(days=i)
            date_str = date.strftime("%Y-%m-%d")
            log_file = self.metrics_dir / f"carby-metrics-{date_str}.jsonl"
            
            if log_file.exists():
                with open(log_file) as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                events.append(json.loads(line))
                            except json.JSONDecodeError:
                                continue
        
        return events
    
    def print_dashboard(self, days: int = 7) -> None:
        """Print a dashboard to the console."""
        summary = self.get_summary(days)
        
        print("=" * 50)
        print(f"Carby Studio Metrics (Last {days} days)")
        print("=" * 50)
        print()
        
        print(f"Pipelines: {summary['total_pipelines']}")
        print(f"Success Rate: {summary['pipeline_success_rate']:.1f}%")
        print()
        
        if summary['stage_success_rates']:
            print("Stage Success Rates:")
            for stage, rate in sorted(summary['stage_success_rates'].items()):
                avg_duration = summary['avg_stage_duration_ms'].get(stage, 0)
                print(f"  {stage:12} {rate:5.1f}% (avg: {avg_duration/1000:.1f}s)")
            print()
        
        if summary['failure_reasons']:
            print("Top Failure Reasons:")
            for reason, count in sorted(summary['failure_reasons'].items(), 
                                       key=lambda x: x[1], reverse=True)[:5]:
                print(f"  {reason}: {count}")
            print()
        
        print("=" * 50)


def main():
    """CLI for metrics."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Carby Studio Metrics")
    parser.add_argument("--dashboard", "-d", action="store_true",
                       help="Show metrics dashboard")
    parser.add_argument("--days", "-n", type=int, default=7,
                       help="Number of days to include (default: 7)")
    parser.add_argument("--record", "-r", metavar="EVENT_TYPE",
                       help="Record a metric event")
    parser.add_argument("--data", metavar="JSON",
                       help="JSON data for the event")
    
    args = parser.parse_args()
    
    collector = MetricsCollector()
    
    if args.dashboard:
        collector.print_dashboard(args.days)
    elif args.record:
        data = json.loads(args.data) if args.data else {}
        collector.record(args.record, **data)
        print(f"Recorded: {args.record}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
