# Evaluation utilities: corpus generation and summary statistics.

from habit.eval.baselines import (
    SemanticCache,
    StrategyResult,
    compare_strategies,
)
from habit.eval.benchmark import (
    Benchmark,
    DomainBenchmark,
    SystemMetrics,
    run_benchmark,
)
from habit.eval.corpus import CorpusSummary, DomainStats, generate_corpus
from habit.eval.injection import DetectionStats, run_injection_study
from habit.eval.long_horizon import (
    LongHorizonResult,
    generate_long_horizon,
    run_long_horizon_study,
)
from habit.eval.research import (
    GeneralizationResult,
    SafetyUnderShiftResult,
    generalization_gap,
    safety_under_shift,
)

__all__ = [
    "generate_corpus",
    "CorpusSummary",
    "DomainStats",
    "run_benchmark",
    "Benchmark",
    "DomainBenchmark",
    "SystemMetrics",
    "generate_long_horizon",
    "LongHorizonResult",
    "run_long_horizon_study",
    "DetectionStats",
    "run_injection_study",
    "GeneralizationResult",
    "generalization_gap",
    "SafetyUnderShiftResult",
    "safety_under_shift",
    "SemanticCache",
    "StrategyResult",
    "compare_strategies",
]
