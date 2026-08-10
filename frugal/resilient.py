# frugal/resilient.py
# MIT License - see LICENSE.txt

from dataclasses import dataclass, field
from datetime import datetime

# Required for the TaskProfile
@dataclass
class RoutingWeights:
    decay: float = 0.4
    performance: float = 0.4
    criticality: float = 0.2

# Policies for skills retention and performance
@dataclass
class SkillsRetentionPolicy:
    decay_constant_days: int = 30
    manual_threshold: float = 0.7
    prefer_manual_threshold: float = 0.4


@dataclass
class PerformancePolicy:
    failure_penalty: float = 0.1
    failure_penalty_cap: float = 0.5


@dataclass
class RoutingPolicy:
    criticality: float = 0.5
    retention: SkillsRetentionPolicy = field(default_factory=SkillsRetentionPolicy)
    performance: PerformancePolicy = field(default_factory=PerformancePolicy)
    weights: RoutingWeights = field(default_factory=RoutingWeights)


# At task-level we can now track performance
@dataclass
class TaskProfile:
    task_id: str
    policy: RoutingPolicy = field(default_factory=RoutingPolicy)

    @classmethod
    def from_dict(cls, task_id: str, data: dict):
        return cls(
            task_id=task_id,
            policy=RoutingPolicy(criticality=data.get("criticality", 0.5),

                retention=SkillsRetentionPolicy(
                    decay_constant_days=data.get("decay_constant_days", 30),
                    manual_threshold=data.get("manual_threshold", 0.7),
                    prefer_manual_threshold=data.get("prefer_manual_threshold", 0.4),
                ),

                performance=PerformancePolicy(
                    failure_penalty=data.get("failure_penalty", 0.1),
                    failure_penalty_cap=data.get("failure_penalty_cap", 0.5),
                ),

                weights=RoutingWeights(
                    decay=data.get("weights", {}).get("decay", 0.4),
                    performance=data.get("weights", {}).get("performance", 0.4),
                    criticality=data.get("weights", {}).get("criticality", 0.2),
                ),
            ),
        )

    
@dataclass
class UserTaskState:
    user_id: str
    task_id: str
    last_manual_execution_ts: datetime
    executions_count: int
    success_rate: float
    avg_completion_time: float
    assistance_ratio: float
    recent_failures: int


class ResilienceEngine:
    def compute_decay_risk(self, task, state, now):
        days_since = ( now - state.last_manual_execution_ts).days
        decay_constant = task.policy.retention.decay_constant_days
        return min(1.0, days_since / max( 1, decay_constant ))

    def compute_performance_risk(self, task, state):
        policy = task.policy.performance
        base = 1.0 - state.success_rate
        penalty = min( policy.failure_penalty_cap, state.recent_failures * policy.failure_penalty )
        return min( 1.0, base + penalty)

    def routing_score(self, task, state, now):
        decay = self.compute_decay_risk( task, state, now)
        performance = self.compute_performance_risk( task, state )
        weights = task.policy.weights
        score = ( weights.decay * decay + weights.performance * performance + weights.criticality * task.policy.criticality )
        # FOR TESTING
        print(
            f"decay={decay:.3f} "
            f"performance={performance:.3f} "
            f"criticality={task.policy.criticality:.3f} "
            f"score={score:.3f}"
        )
        return score

    def diagnostics( self, task, state, now ):
        decay = self.compute_decay_risk( task, state, now )
        performance = self.compute_performance_risk( task, state )
        score = self.routing_score( task, state, now )
        return { "task": task.task_id, "user": state.user_id, "decay_risk": round(decay, 4), "performance_risk": round( performance, 4 ),
                 "score": round( score, 4 ), "policy": task.policy }

    def decision( self, task, state, now ):
        score = self.routing_score( task, state, now )
        policy = task.policy.retention
        # FOR TESTING
        print(f"{score=}")
        if ( score >= policy.manual_threshold):
            return "FORCE_MANUAL"
        if ( score >= policy.prefer_manual_threshold):
            return "PREFER_MANUAL"
        # Manual skills are up-to-date so take the productivity gain of automation.
        return "AUTOMATE"
