from habit.workloads import (
    ArithmeticWorkload,
    MockTool,
    WorkloadGenerator,
    WorkloadTask,
)


def test_determinism() -> None:
    a = ArithmeticWorkload().generate(5, seed=7)
    b = ArithmeticWorkload().generate(5, seed=7)
    assert a == b


def test_different_seed_differs() -> None:
    a = ArithmeticWorkload().generate(5, seed=7)
    b = ArithmeticWorkload().generate(5, seed=8)
    assert a != b


def test_tasks_self_consistent() -> None:
    for task in ArithmeticWorkload().generate(10, seed=1):
        assert isinstance(task.task_input, dict)
        assert isinstance(task.expected, dict)
        assert task.expected["result"] == sum(task.task_input["numbers"])


def test_add_tool() -> None:
    workload = ArithmeticWorkload()
    add = next(t for t in workload.tools() if t.name == "add")
    assert isinstance(add, MockTool)
    assert add(numbers=[1, 2, 3]) == {"result": 6}


def test_checker() -> None:
    workload = ArithmeticWorkload()
    checker = workload.checker()
    task = workload.generate(1, seed=3)[0]
    assert checker(task, {"result": task.expected["result"]}) is True
    assert checker(task, {"result": task.expected["result"] + 1}) is False


def test_domain() -> None:
    assert ArithmeticWorkload().domain == "arithmetic"


def test_conforms_to_protocol() -> None:
    workload: WorkloadGenerator = ArithmeticWorkload()
    assert isinstance(workload.generate(1, seed=0)[0], WorkloadTask)
