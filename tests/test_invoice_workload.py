from habit.workloads import InvoiceWorkload, WorkloadGenerator
from habit.workloads.invoice import (
    KNOWN_VENDORS,
    extract_header,
    lookup_vendor,
    validate_totals,
)


def test_conformance_and_domain() -> None:
    gen: WorkloadGenerator = InvoiceWorkload()
    assert gen.domain == "invoice"


def test_determinism() -> None:
    assert InvoiceWorkload().generate(6, seed=3) == InvoiceWorkload().generate(
        6, seed=3
    )
    assert InvoiceWorkload().generate(
        6, seed=3, shifted=True
    ) == InvoiceWorkload().generate(6, seed=3, shifted=True)


def test_different_seed_differs() -> None:
    assert InvoiceWorkload().generate(6, seed=3) != InvoiceWorkload().generate(
        6, seed=4
    )


def test_task_self_consistency() -> None:
    tasks = InvoiceWorkload().generate(40, seed=11)
    invalid_seen = False
    for task in tasks:
        inv = task.task_input
        assert task.expected["total"] == inv["total"]
        assert task.expected["line_item_count"] == len(inv["line_items"])
        for item in inv["line_items"]:
            assert item["amount"] == item["quantity"] * item["unit_price"]
        assert inv["subtotal"] == sum(item["amount"] for item in inv["line_items"])
        line_ok = inv["subtotal"] + inv["tax"] == inv["total"]
        assert task.expected["totals_valid"] == line_ok
        invalid_seen = invalid_seen or not task.expected["totals_valid"]
    assert invalid_seen


def test_variety() -> None:
    tasks = InvoiceWorkload().generate(40, seed=11)
    vendor_known = {task.expected["vendor_known"] for task in tasks}
    totals_valid = {task.expected["totals_valid"] for task in tasks}
    assert vendor_known == {True, False}
    assert totals_valid == {True, False}


def test_shifted_split_distinct() -> None:
    tasks = InvoiceWorkload().generate(20, seed=5, shifted=True)
    vendors = {task.task_input["vendor"] for task in tasks}
    assert vendors.isdisjoint(KNOWN_VENDORS)
    for task in tasks:
        inv = task.task_input
        assert inv["subtotal"] == sum(item["amount"] for item in inv["line_items"])
        assert task.expected["line_item_count"] == len(inv["line_items"])


def test_tools() -> None:
    workload = InvoiceWorkload()
    valid = workload.generate(60, seed=11)
    good = next(t for t in valid if t.expected["totals_valid"])
    bad = next(t for t in valid if not t.expected["totals_valid"])
    assert validate_totals(good.task_input) == {"totals_valid": True}
    assert validate_totals(bad.task_input) == {"totals_valid": False}
    assert lookup_vendor(KNOWN_VENDORS[0]) == {"vendor_known": True}
    assert lookup_vendor("Nobody Corp") == {"vendor_known": False}
    header = extract_header(good.task_input)
    assert set(header) == {"invoice_id", "vendor", "invoice_date", "total"}


def test_checker() -> None:
    workload = InvoiceWorkload()
    checker = workload.checker()
    task = workload.generate(1, seed=2)[0]
    assert checker(task, dict(task.expected)) is True
    wrong = dict(task.expected)
    wrong["total"] = wrong["total"] + 1
    assert checker(task, wrong) is False
