from habit.workloads import TicketWorkload, WorkloadGenerator
from habit.workloads.ticket import (
    KNOWN_CUSTOMERS,
    PRIORITY,
    TEAM,
    classify_ticket,
    decide_priority,
    lookup_customer,
    route_ticket,
)


def test_conformance_and_domain() -> None:
    gen: WorkloadGenerator = TicketWorkload()
    assert gen.domain == "ticket"


def test_determinism() -> None:
    assert TicketWorkload().generate(8, seed=5) == TicketWorkload().generate(8, seed=5)
    assert TicketWorkload().generate(
        8, seed=5, shifted=True
    ) == TicketWorkload().generate(8, seed=5, shifted=True)


def test_different_seed_differs() -> None:
    assert TicketWorkload().generate(8, seed=5) != TicketWorkload().generate(8, seed=6)


def test_self_consistency() -> None:
    for task in TicketWorkload().generate(40, seed=11):
        message = task.task_input["message"]
        category = task.expected["category"]
        assert classify_ticket(message) == {"category": category}
        assert task.expected["team"] == TEAM[category]
        assert task.expected["priority"] == PRIORITY[category]
        assert task.expected["customer_known"] == (
            task.task_input["customer_id"] in KNOWN_CUSTOMERS
        )


def test_variety() -> None:
    tasks = TicketWorkload().generate(40, seed=11)
    categories = {task.expected["category"] for task in tasks}
    customer_known = {task.expected["customer_known"] for task in tasks}
    assert len(categories) >= 3
    assert customer_known == {True, False}


def test_shifted_split() -> None:
    tasks = TicketWorkload().generate(30, seed=5, shifted=True)
    assert all(task.expected["customer_known"] is False for task in tasks)
    for task in tasks:
        assert classify_ticket(task.task_input["message"]) == {
            "category": task.expected["category"]
        }


def test_tools() -> None:
    assert classify_ticket("I have a question about my bill this month.") == {
        "category": "billing"
    }
    assert classify_ticket("The app shows an error and keeps crashing.") == {
        "category": "technical"
    }
    assert classify_ticket("I would like a refund for my last payment.") == {
        "category": "refund"
    }
    assert classify_ticket("I need to reset my password.") == {"category": "account"}
    assert classify_ticket("Just a general question.") == {"category": "other"}
    assert lookup_customer(KNOWN_CUSTOMERS[0]) == {"customer_known": True}
    assert lookup_customer("CUST-777777") == {"customer_known": False}
    assert route_ticket("refund") == {"team": "Finance"}
    assert decide_priority("technical") == {"priority": "high"}
    assert decide_priority("billing") == {"priority": "normal"}


def test_checker() -> None:
    workload = TicketWorkload()
    checker = workload.checker()
    task = workload.generate(1, seed=2)[0]
    assert checker(task, dict(task.expected)) is True
    wrong = dict(task.expected)
    wrong["team"] = "WrongTeam"
    assert checker(task, wrong) is False
