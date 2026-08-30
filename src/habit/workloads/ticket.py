# Support-ticket triage workload (Domain 2). Keyword-based deterministic classification.

import random
from typing import Any

from habit.workloads.base import GroundTruthChecker, MockTool, WorkloadTask

CATEGORIES = ["billing", "technical", "refund", "account", "other"]

KEYWORDS = {
    "billing": "bill",
    "technical": "error",
    "refund": "refund",
    "account": "password",
}

TEAM = {
    "billing": "Finance",
    "technical": "Engineering",
    "refund": "Finance",
    "account": "Identity",
    "other": "General",
}

PRIORITY = {
    "billing": "normal",
    "technical": "high",
    "refund": "high",
    "account": "normal",
    "other": "normal",
}

NORMAL_TEMPLATES = {
    "billing": [
        "I have a question about my bill this month.",
        "My latest bill seems higher than usual.",
    ],
    "technical": [
        "The app shows an error and keeps crashing.",
        "I keep getting an error when uploading.",
    ],
    "refund": [
        "I would like a refund for my last payment.",
        "Please issue a refund for this order.",
    ],
    "account": [
        "I cannot log in and need to reset my password.",
        "How do I change my password?",
    ],
    "other": [
        "I have a general question about your service.",
        "Just checking in on the status of my order.",
    ],
}

SHIFTED_TEMPLATES = {
    "billing": [
        "A charge on my bill looks wrong.",
        "Why did my bill increase this cycle?",
    ],
    "technical": [
        "Seeing an error code on startup.",
        "An error appears every time I click save.",
    ],
    "refund": [
        "Kindly process a refund as soon as possible.",
        "I am still waiting for my refund.",
    ],
    "account": [
        "The reset password link is broken.",
        "I forgot my password again.",
    ],
    "other": [
        "Sharing some general feedback about the product.",
        "Following up on my previous conversation.",
    ],
}

KNOWN_CUSTOMERS = [
    "CUST-000001",
    "CUST-000002",
    "CUST-000003",
    "CUST-000004",
    "CUST-000005",
]

UNKNOWN_CUSTOMERS = [
    "CUST-100001",
    "CUST-100002",
    "CUST-100003",
]

SHIFTED_CUSTOMERS = [
    "CUST-900001",
    "CUST-900002",
    "CUST-900003",
    "CUST-900004",
]


# Ground-truth helpers shared by tools and the generator so they never diverge.
def _classify(message: str) -> str:
    for category, keyword in KEYWORDS.items():
        if keyword in message:
            return category
    return "other"


def _customer_known(customer_id: str) -> bool:
    return customer_id in KNOWN_CUSTOMERS


# Mock tools an agent could call; each pure.
def classify_ticket(message: str) -> dict[str, Any]:
    return {"category": _classify(message)}


def lookup_customer(customer_id: str) -> dict[str, Any]:
    return {"customer_known": _customer_known(customer_id)}


def decide_priority(category: str) -> dict[str, Any]:
    return {"priority": PRIORITY[category]}


def route_ticket(category: str) -> dict[str, Any]:
    return {"team": TEAM[category]}


def close_ticket(ticket_id: str) -> dict[str, Any]:
    return {"closed": True}


def _check(task: WorkloadTask, final_output: dict[str, Any]) -> bool:
    return all(final_output.get(key) == value for key, value in task.expected.items())


class TicketWorkload:
    @property
    def domain(self) -> str:
        return "ticket"

    def generate(
        self, n: int, *, seed: int, shifted: bool = False
    ) -> list[WorkloadTask]:
        rng = random.Random(seed)
        templates = SHIFTED_TEMPLATES if shifted else NORMAL_TEMPLATES
        prefix = "ticket-shift" if shifted else "ticket"
        tasks: list[WorkloadTask] = []
        for i in range(n):
            category = rng.choice(CATEGORIES)
            message = rng.choice(templates[category])
            if shifted:
                customer_id = rng.choice(SHIFTED_CUSTOMERS)
            else:
                customer_id = (
                    rng.choice(KNOWN_CUSTOMERS)
                    if rng.random() < 0.7
                    else rng.choice(UNKNOWN_CUSTOMERS)
                )
            ticket_id = f"TKT-{rng.randint(0, 999999):06d}"
            tasks.append(
                WorkloadTask(
                    task_id=f"{prefix}-{seed}-{i}",
                    task_input={
                        "ticket_id": ticket_id,
                        "customer_id": customer_id,
                        "message": message,
                    },
                    expected={
                        "ticket_id": ticket_id,
                        "category": category,
                        "team": TEAM[category],
                        "priority": PRIORITY[category],
                        "customer_known": _customer_known(customer_id),
                    },
                )
            )
        return tasks

    def tools(self) -> list[MockTool]:
        return [
            MockTool(name="classify_ticket", fn=classify_ticket),
            MockTool(name="lookup_customer", fn=lookup_customer),
            MockTool(name="decide_priority", fn=decide_priority),
            MockTool(name="route_ticket", fn=route_ticket),
            MockTool(name="close_ticket", fn=close_ticket),
        ]

    def checker(self) -> GroundTruthChecker:
        return _check
