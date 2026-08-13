from pathlib import Path
from typing import Any, TypedDict

import pytest
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langgraph.graph import END, START, StateGraph
from sqlalchemy import create_engine

from habit.adapters.langgraph import HabitCallbackHandler, record_langgraph_run
from habit.schemas import StepType, schema_fingerprint
from habit.storage import SqlAlchemyTrajectoryStore

TOOL_RESULT = {"total": 42, "lines": [{"sku": "A"}]}


@pytest.fixture
def store(tmp_path: Path) -> SqlAlchemyTrajectoryStore:
    return SqlAlchemyTrajectoryStore(
        create_engine(f"sqlite:///{tmp_path / 'habit.db'}")
    )


class _State(TypedDict):
    x: str
    llm: str
    result: dict[str, Any]


@tool
def fetch(x: str) -> dict[str, Any]:
    """Return a fixed invoice-like dict."""
    return {"total": 42, "lines": [{"sku": x}]}


@tool
def boom(x: str) -> dict[str, Any]:
    """Always fail."""
    raise ValueError("tool exploded")


def _build_app(tool_fn: Any) -> Any:
    model = FakeMessagesListChatModel(
        responses=[
            AIMessage(
                content="ok",
                usage_metadata={
                    "input_tokens": 7,
                    "output_tokens": 3,
                    "total_tokens": 10,
                },
            )
        ]
    )

    def call_model(state: _State, config: RunnableConfig) -> dict[str, Any]:
        response = model.invoke("hello", config=config)
        return {"llm": str(response.content)}

    def call_tool(state: _State, config: RunnableConfig) -> dict[str, Any]:
        return {"result": tool_fn.invoke({"x": state["x"]}, config=config)}

    graph = StateGraph(_State)
    graph.add_node("call_model", call_model)
    graph.add_node("call_tool", call_tool)
    graph.add_edge(START, "call_model")
    graph.add_edge("call_model", "call_tool")
    graph.add_edge("call_tool", END)
    return graph.compile()


def test_records_llm_and_tool_steps(store: SqlAlchemyTrajectoryStore) -> None:
    app = _build_app(fetch)
    traj = record_langgraph_run(
        app,
        {"x": "A"},
        store=store,
        trajectory_id="t1",
        domain="invoice",
        task_type="extract",
    )

    assert store.get("t1") == traj
    assert traj.outcome.success is True
    step_types = [s.step_type for s in traj.steps]
    assert step_types == [StepType.LLM_CALL, StepType.TOOL_CALL]


def test_tool_fingerprint(store: SqlAlchemyTrajectoryStore) -> None:
    app = _build_app(fetch)
    traj = record_langgraph_run(
        app,
        {"x": "A"},
        store=store,
        trajectory_id="t1",
        domain="invoice",
        task_type="extract",
    )
    tool_step = next(s for s in traj.steps if s.step_type == StepType.TOOL_CALL)
    assert tool_step.tool_result_schema_fingerprint == schema_fingerprint(TOOL_RESULT)


def test_context_is_empty(store: SqlAlchemyTrajectoryStore) -> None:
    app = _build_app(fetch)
    traj = record_langgraph_run(
        app,
        {"x": "A"},
        store=store,
        trajectory_id="t1",
        domain="invoice",
        task_type="extract",
    )
    for step in traj.steps:
        assert step.context_available == []
        assert step.context_reads == []


def test_failed_run_recorded(store: SqlAlchemyTrajectoryStore) -> None:
    app = _build_app(boom)
    with pytest.raises(ValueError):
        record_langgraph_run(
            app,
            {"x": "A"},
            store=store,
            trajectory_id="t1",
            domain="invoice",
            task_type="extract",
        )
    persisted = store.get("t1")
    assert persisted is not None
    assert persisted.outcome.success is False
    assert persisted.outcome.error


def test_handler_is_callback_handler() -> None:
    from langchain_core.callbacks import BaseCallbackHandler

    assert issubclass(HabitCallbackHandler, BaseCallbackHandler)
