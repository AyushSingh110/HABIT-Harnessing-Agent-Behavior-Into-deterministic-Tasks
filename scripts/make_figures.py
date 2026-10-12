# Render paper-ready figures and a results CSV from the HABIT evaluation experiments.

import csv
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402

from habit.baseline import (  # noqa: E402
    FakeModel,
    run_invoice_baseline,
    run_report_baseline,
    run_ticket_baseline,
)
from habit.compiler import (  # noqa: E402
    cluster_trajectories,
    compile_habit,
    induce_skeleton,
)
from habit.eval import (  # noqa: E402
    compare_strategies,
    detection_roc,
    generalization_gap,
    reliability_study,
    roc_auc,
    run_benchmark,
    run_injection_study,
    run_long_horizon_study,
    safety_under_shift,
)
from habit.runtime import expected_tool_fingerprints  # noqa: E402
from habit.storage import SqlAlchemyTrajectoryStore  # noqa: E402
from habit.workloads import (  # noqa: E402
    InvoiceWorkload,
    MockTool,
    ReportWorkload,
    TicketWorkload,
)

FIGURES = Path("figures")
LIVE_COLOR = "#0072B2"
HABIT_COLOR = "#E69F00"
DOMAINS = [
    (InvoiceWorkload(), run_invoice_baseline),
    (TicketWorkload(), run_ticket_baseline),
    (ReportWorkload(), run_report_baseline),
]
N_STEPS = [10, 20, 50, 100, 200]


def _shape_injector(tools: dict[str, MockTool]) -> dict[str, MockTool]:
    real = tools["validate_totals"]

    def bad(**kwargs: Any) -> dict[str, Any]:
        return {**real(**kwargs), "EXTRA": 1}

    return {**tools, "validate_totals": MockTool(name="validate_totals", fn=bad)}


def _value_injector(tools: dict[str, MockTool]) -> dict[str, MockTool]:
    real = tools["validate_totals"]

    def bad(**kwargs: Any) -> dict[str, Any]:
        result = real(**kwargs)
        return {**result, "totals_valid": not result["totals_valid"]}

    return {**tools, "validate_totals": MockTool(name="validate_totals", fn=bad)}


def _invoice_injection_inputs() -> tuple[
    Any, list[str | None], list[Any], dict[str, MockTool]
]:
    workload = InvoiceWorkload()
    tools = {tool.name: tool for tool in workload.tools()}
    store = SqlAlchemyTrajectoryStore(create_engine("sqlite:///:memory:"))
    for i, task in enumerate(workload.generate(40, seed=0)):
        run_invoice_baseline(
            task, model=FakeModel(), store=store, tools=tools, trajectory_id=f"i-{i}"
        )
    trajectories = store.query()
    by_id = {t.trajectory_id: t for t in trajectories}
    cluster = cluster_trajectories(trajectories)[0]
    plan = compile_habit(cluster, by_id, tools).plan
    expected = expected_tool_fingerprints(induce_skeleton(cluster, by_id))
    return plan, expected, workload.generate(40, seed=1), tools


def main() -> None:
    FIGURES.mkdir(exist_ok=True)
    rows: list[tuple[str, str, str, float]] = []

    # Figure 1: LLM calls per task, live vs habit.
    benchmark = run_benchmark(
        model=FakeModel(), train_per_domain=40, eval_per_domain=40
    )
    domains = list(benchmark.per_domain)
    live = [benchmark.per_domain[d].live.mean_llm_calls for d in domains]
    habit = [benchmark.per_domain[d].habit.mean_llm_calls for d in domains]
    fig, ax = plt.subplots()
    x = range(len(domains))
    ax.bar([i - 0.2 for i in x], live, width=0.4, label="live agent", color=LIVE_COLOR)
    ax.bar(
        [i + 0.2 for i in x],
        habit,
        width=0.4,
        label="compiled habit",
        color=HABIT_COLOR,
    )
    ax.set_xticks(list(x))
    ax.set_xticklabels(domains)
    ax.set_xlabel("domain")
    ax.set_ylabel("mean LLM calls per task")
    ax.set_title("LLM calls per task: live agent vs. compiled habit")
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIGURES / "fig_cost.png", dpi=200)
    plt.close(fig)
    for d, lv, hb in zip(domains, live, habit):
        rows.append(("fig_cost", d, "live_mean_llm_calls", lv))
        rows.append(("fig_cost", d, "habit_mean_llm_calls", hb))

    # Figure 2: context window vs task length.
    naive = []
    policy = []
    for n in N_STEPS:
        result = run_long_horizon_study(n_steps=n, count=4)
        naive.append(result.naive_peak)
        policy.append(result.policy_peak)
        rows.append(
            ("fig_survival", f"n_steps={n}", "naive_peak", float(result.naive_peak))
        )
        rows.append(
            ("fig_survival", f"n_steps={n}", "policy_peak", float(result.policy_peak))
        )
    fig, ax = plt.subplots()
    ax.plot(N_STEPS, naive, marker="o", label="naive (keep all)", color=LIVE_COLOR)
    ax.plot(N_STEPS, policy, marker="s", label="HABIT policy", color=HABIT_COLOR)
    ax.set_xlabel("task length (steps)")
    ax.set_ylabel("peak context items")
    ax.set_title("Context window vs. task length (naive vs. HABIT policy)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIGURES / "fig_survival.png", dpi=200)
    plt.close(fig)

    # Figure 3: generalization, normal vs shifted split.
    gen = [generalization_gap(w, r, train_n=40, eval_n=40) for w, r in DOMAINS]
    gen_domains = [g.domain for g in gen]
    normal = [g.normal_success for g in gen]
    shifted = [g.shifted_success for g in gen]
    fig, ax = plt.subplots()
    x = range(len(gen_domains))
    ax.bar(
        [i - 0.2 for i in x], normal, width=0.4, label="normal split", color=LIVE_COLOR
    )
    ax.bar(
        [i + 0.2 for i in x],
        shifted,
        width=0.4,
        label="shifted split",
        color=HABIT_COLOR,
    )
    ax.set_xticks(list(x))
    ax.set_xticklabels(gen_domains)
    ax.set_xlabel("domain")
    ax.set_ylabel("habit success rate")
    ax.set_ylim(0, 1.1)
    ax.set_title("Habit success: normal vs. shifted split")
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIGURES / "fig_generalization.png", dpi=200)
    plt.close(fig)
    for g in gen:
        rows.append(
            ("fig_generalization", g.domain, "normal_success", g.normal_success)
        )
        rows.append(
            ("fig_generalization", g.domain, "shifted_success", g.shifted_success)
        )

    # Figure 4: divergence detector operating point (invoice).
    plan, expected, tasks, tools = _invoice_injection_inputs()
    stats = run_injection_study(
        plan,
        expected,
        tasks,
        tools,
        shape_injector=_shape_injector,
        value_injector=_value_injector,
    )
    labels = ["shape catch", "value catch", "false abort"]
    values = [stats.shape_catch_rate, stats.value_catch_rate, stats.false_abort_rate]
    fig, ax = plt.subplots()
    ax.bar(labels, values, color=[HABIT_COLOR, LIVE_COLOR, LIVE_COLOR])
    ax.set_ylabel("rate")
    ax.set_ylim(0, 1.1)
    ax.set_title("Divergence detector operating point")
    ax.legend(["invoice"])
    fig.tight_layout()
    fig.savefig(FIGURES / "fig_divergence.png", dpi=200)
    plt.close(fig)
    rows.append(
        ("fig_divergence", "invoice", "shape_catch_rate", stats.shape_catch_rate)
    )
    rows.append(
        ("fig_divergence", "invoice", "value_catch_rate", stats.value_catch_rate)
    )
    rows.append(
        ("fig_divergence", "invoice", "false_abort_rate", stats.false_abort_rate)
    )

    # Safety-under-shift results (no figure; recorded in the CSV).
    for workload, runner in DOMAINS:
        safety = safety_under_shift(workload, runner, train_n=40, eval_n=40)
        rows.append(
            (
                "safety_under_shift",
                safety.domain,
                "normal_safe",
                float(safety.normal_safe),
            )
        )
        rows.append(
            (
                "safety_under_shift",
                safety.domain,
                "shifted_safe",
                float(safety.shifted_safe),
            )
        )
        rows.append(
            (
                "safety_under_shift",
                safety.domain,
                "shifted_starvations",
                float(safety.shifted_starvations),
            )
        )

    # Figure 5: baseline ladder — live LLM calls per task by strategy (invoice).
    strategies = compare_strategies(InvoiceWorkload(), run_invoice_baseline, n=60)
    order = ["vanilla", "cache", "habit"]
    calls = [strategies[s].mean_live_llm_calls for s in order]
    fig, ax = plt.subplots()
    ax.bar(order, calls, color=[LIVE_COLOR, LIVE_COLOR, HABIT_COLOR])
    ax.set_xlabel("strategy")
    ax.set_ylabel("mean live LLM calls per task")
    ax.set_title("Live LLM calls per task by strategy")
    ax.legend(["invoice"])
    fig.tight_layout()
    fig.savefig(FIGURES / "fig_baselines.png", dpi=200)
    plt.close(fig)
    for s in order:
        rows.append(
            (
                "fig_baselines",
                s,
                "mean_live_llm_calls",
                strategies[s].mean_live_llm_calls,
            )
        )
        rows.append(("fig_baselines", s, "reuse_rate", strategies[s].reuse_rate))

    # Figure 6: end-to-end success vs per-step LLM reliability (live agent vs habit).
    fig, ax = plt.subplots()
    xs: list[float] = []
    for workload, runner in DOMAINS:
        series = reliability_study(workload, runner, n_tasks=100)
        xs = [r.reliability for r in series]
        live = [r.live_success_rate for r in series]
        ax.plot(
            xs, live, marker="o", color=LIVE_COLOR, label=f"{workload.domain} (live)"
        )
        for r in series:
            rows.append(
                (
                    "fig_reliability",
                    r.domain,
                    f"live@r={r.reliability}",
                    r.live_success_rate,
                )
            )
            rows.append(
                (
                    "fig_reliability",
                    r.domain,
                    f"habit@r={r.reliability}",
                    r.habit_success_rate,
                )
            )
    ax.plot(xs, [1.0] * len(xs), color=HABIT_COLOR, linestyle="--", label="habit (all)")
    ax.set_xlabel("per-step LLM reliability r")
    ax.set_ylabel("end-to-end success rate")
    ax.set_ylim(0, 1.1)
    ax.set_title("End-to-end success vs per-step reliability: live vs habit")
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIGURES / "fig_reliability.png", dpi=200)
    plt.close(fig)

    # Figure 7: value-guard ROC vs the structural detector's (0,0) point (invoice).
    points = detection_roc(InvoiceWorkload(), run_invoice_baseline)
    auc = roc_auc(points)
    fig, ax = plt.subplots()
    fprs = [0.0] + [p.fpr for p in points] + [1.0]
    tprs = [0.0] + [p.tpr for p in points] + [1.0]
    ax.plot(
        fprs, tprs, marker="o", color=HABIT_COLOR, label=f"value guard (AUC={auc:.3f})"
    )
    ax.plot([0, 1], [0, 1], linestyle=":", color="#999999", label="chance")
    ax.scatter(
        [0.0],
        [0.0],
        color=LIVE_COLOR,
        zorder=5,
        label="structural fingerprint (value anomalies)",
    )
    ax.set_xlabel("false positive rate")
    ax.set_ylabel("true positive rate")
    ax.set_xlim(-0.02, 1.02)
    ax.set_ylim(-0.02, 1.02)
    ax.set_title(f"Value-anomaly detection ROC (AUC={auc:.3f})")
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIGURES / "fig_detection_roc.png", dpi=200)
    plt.close(fig)
    for p in points:
        rows.append(("fig_detection_roc", "invoice", f"tpr@tol={p.tolerance}", p.tpr))
        rows.append(("fig_detection_roc", "invoice", f"fpr@tol={p.tolerance}", p.fpr))
    rows.append(("fig_detection_roc", "invoice", "auc", auc))

    with (FIGURES / "results.csv").open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["figure", "domain", "metric", "value"])
        writer.writerows(rows)

    for name in (
        "fig_cost",
        "fig_survival",
        "fig_generalization",
        "fig_divergence",
        "fig_baselines",
        "fig_reliability",
        "fig_detection_roc",
    ):
        print(FIGURES / f"{name}.png")
    print(FIGURES / "results.csv")


if __name__ == "__main__":
    main()
