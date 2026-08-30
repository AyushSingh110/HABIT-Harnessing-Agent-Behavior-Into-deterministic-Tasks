# Invoice workload (Domain 1), DocILE-aligned. Integer money, pure-code checker.

import random
from datetime import date, timedelta
from typing import Any

from habit.workloads.base import GroundTruthChecker, MockTool, WorkloadTask

KNOWN_VENDORS = [
    "Acme Supplies Ltd",
    "Globex Trading Co",
    "Initech Systems",
    "Umbrella Distribution",
    "Wayne Industrial",
    "Stark Components",
]

UNKNOWN_VENDORS = [
    "N_Ryctor Holdings",
    "Zephyr Unlisted LLP",
    "Obscure Traders",
]

SHIFTED_VENDORS = [
    "Meridian Offshore Inc",
    "Pole Star Exports",
    "Kestrel Logistics GmbH",
    "Aurora Pacific Corp",
]

ITEM_DESCRIPTIONS = [
    "A4 paper ream",
    "Toner cartridge",
    "Ballpoint pens (box)",
    "USB-C cable",
    "Desk organizer",
    "Wireless mouse",
    "Notebook set",
    "Stapler",
]

TAX_PERCENT = 18


# Ground-truth helpers, shared by tools and the checker so they never diverge.
def _totals_valid(invoice: dict[str, Any]) -> bool:
    line_sum = sum(item["amount"] for item in invoice["line_items"])
    return bool(
        line_sum == invoice["subtotal"]
        and invoice["subtotal"] + invoice["tax"] == invoice["total"]
    )


def _vendor_known(vendor: str) -> bool:
    return vendor in KNOWN_VENDORS


# Mock tools an agent could call; each pure and operating on the invoice dict.
def extract_header(invoice: dict[str, Any]) -> dict[str, Any]:
    return {
        "invoice_id": invoice["invoice_id"],
        "vendor": invoice["vendor"],
        "invoice_date": invoice["invoice_date"],
        "total": invoice["total"],
    }


def extract_line_items(invoice: dict[str, Any]) -> dict[str, Any]:
    return {"line_items": invoice["line_items"], "count": len(invoice["line_items"])}


def validate_totals(invoice: dict[str, Any]) -> dict[str, Any]:
    return {"totals_valid": _totals_valid(invoice)}


def lookup_vendor(vendor: str) -> dict[str, Any]:
    return {"vendor_known": _vendor_known(vendor)}


def post_to_ledger(invoice_id: str, total: int) -> dict[str, Any]:
    return {"posted": True}


def _check(task: WorkloadTask, final_output: dict[str, Any]) -> bool:
    return all(final_output.get(key) == value for key, value in task.expected.items())


class InvoiceWorkload:
    @property
    def domain(self) -> str:
        return "invoice"

    def generate(
        self, n: int, *, seed: int, shifted: bool = False
    ) -> list[WorkloadTask]:
        rng = random.Random(seed)
        prefix = "invoice-shift" if shifted else "invoice"
        tasks: list[WorkloadTask] = []
        for i in range(n):
            invoice = _build_invoice(rng, shifted=shifted)
            tasks.append(
                WorkloadTask(
                    task_id=f"{prefix}-{seed}-{i}",
                    task_input=invoice,
                    expected={
                        "invoice_id": invoice["invoice_id"],
                        "vendor": invoice["vendor"],
                        "total": invoice["total"],
                        "line_item_count": len(invoice["line_items"]),
                        "totals_valid": _totals_valid(invoice),
                        "vendor_known": _vendor_known(invoice["vendor"]),
                    },
                )
            )
        return tasks

    def tools(self) -> list[MockTool]:
        return [
            MockTool(name="extract_header", fn=extract_header),
            MockTool(name="extract_line_items", fn=extract_line_items),
            MockTool(name="validate_totals", fn=validate_totals),
            MockTool(name="lookup_vendor", fn=lookup_vendor),
            MockTool(name="post_to_ledger", fn=post_to_ledger),
        ]

    def checker(self) -> GroundTruthChecker:
        return _check


# One DocILE-aligned invoice, valid by construction unless a total tamper is applied.
def _build_invoice(rng: random.Random, *, shifted: bool) -> dict[str, Any]:
    if shifted:
        vendor = rng.choice(SHIFTED_VENDORS)
        currency = "USD"
        n_items = rng.randint(1, 8)
        qty_range = (1, 20)
        price_range = (500, 5000)
    else:
        vendor = (
            rng.choice(KNOWN_VENDORS)
            if rng.random() < 0.7
            else rng.choice(UNKNOWN_VENDORS)
        )
        currency = "INR"
        n_items = rng.randint(1, 5)
        qty_range = (1, 10)
        price_range = (10, 500)

    line_items: list[dict[str, Any]] = []
    for _ in range(n_items):
        quantity = rng.randint(*qty_range)
        unit_price = rng.randint(*price_range)
        line_items.append(
            {
                "description": rng.choice(ITEM_DESCRIPTIONS),
                "quantity": quantity,
                "unit_price": unit_price,
                "amount": quantity * unit_price,
            }
        )

    subtotal = sum(item["amount"] for item in line_items)
    tax = subtotal * TAX_PERCENT // 100
    total = subtotal + tax
    if rng.random() < 0.2:
        total += rng.randint(1, 100)

    invoice_date = date(2026, 1, 1) + timedelta(days=rng.randint(0, 364))
    due_date = invoice_date + timedelta(days=30)
    invoice_id = f"INV-{rng.randint(0, 999999):06d}"

    return {
        "invoice_id": invoice_id,
        "vendor": vendor,
        "invoice_date": invoice_date.isoformat(),
        "due_date": due_date.isoformat(),
        "currency": currency,
        "line_items": line_items,
        "subtotal": subtotal,
        "tax": tax,
        "total": total,
    }
