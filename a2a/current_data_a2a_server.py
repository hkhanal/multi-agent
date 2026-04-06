from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import pandas as pd
import uvicorn
from agents import Agent, RunContextWrapper, Runner, function_tool
from a2a.server.agent_execution import AgentExecutor
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentInterface,
    AgentSkill,
    TaskArtifactUpdateEvent,
    TaskState,
    TaskStatus,
    TaskStatusUpdateEvent,
)
from a2a.utils import get_message_text, new_agent_text_message, new_task, new_text_artifact

CURRENT_DATA_MODEL = os.getenv("CURRENT_DATA_MODEL", "gpt-5.4")
CURRENT_DATA_FILE = os.getenv("CURRENT_DATA_FILE", "sales.xlsx")
CURRENT_DATA_HOST = os.getenv("CURRENT_DATA_HOST", "127.0.0.1")
CURRENT_DATA_PORT = int(os.getenv("CURRENT_DATA_PORT", "9101"))
CURRENT_DATA_PUBLIC_URL = os.getenv(
    "CURRENT_DATA_PUBLIC_URL",
    f"http://{CURRENT_DATA_HOST}:{CURRENT_DATA_PORT}",
)


@dataclass
class WorkbookContext:
    workbook_path: str
    sheets: dict[str, pd.DataFrame] = field(default_factory=dict)
    active_sheet: Optional[str] = None

    def load(self) -> None:
        path = Path(self.workbook_path)
        suffix = path.suffix.lower()

        if suffix == ".csv":
            df = pd.read_csv(path)
            self.sheets = {"default": df}
            if self.active_sheet not in self.sheets:
                self.active_sheet = "default"
            return

        if suffix in {".xlsx", ".xls", ".xlsm"}:
            xls = pd.ExcelFile(path)
            self.sheets = {
                name: pd.read_excel(xls, sheet_name=name)
                for name in xls.sheet_names
            }
            if self.active_sheet not in self.sheets:
                self.active_sheet = xls.sheet_names[0] if xls.sheet_names else None
            return

        raise ValueError(f"Unsupported file type: {suffix}")

    def get_df(self, sheet_name: Optional[str] = None) -> pd.DataFrame:
        chosen = sheet_name or self.active_sheet
        if not chosen:
            raise ValueError("No active sheet is set.")
        if chosen not in self.sheets:
            raise ValueError(f"Unknown sheet: {chosen}")
        return self.sheets[chosen]


def _safe_json_value(value: Any) -> Any:
    if pd.isna(value):
        return None
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            pass
    return value


def _rows_to_records(df: pd.DataFrame, limit: int = 20) -> list[dict[str, Any]]:
    clipped = df.head(limit).copy()
    records = clipped.to_dict(orient="records")
    return [{k: _safe_json_value(v) for k, v in row.items()} for row in records]


@function_tool
def list_sheets(context: RunContextWrapper[WorkbookContext]) -> dict[str, Any]:
    """Return all sheet names in the current workbook or the default CSV pseudo-sheet."""
    ctx = context.context
    return {
        "sheets": list(ctx.sheets.keys()),
        "active_sheet": ctx.active_sheet,
    }


@function_tool
def set_active_sheet(
    context: RunContextWrapper[WorkbookContext],
    sheet_name: str,
) -> dict[str, Any]:
    """Set the active sheet for follow-up questions in this run."""
    ctx = context.context
    if sheet_name not in ctx.sheets:
        return {"error": f"Unknown sheet: {sheet_name}"}
    ctx.active_sheet = sheet_name
    return {"ok": True, "active_sheet": ctx.active_sheet}


@function_tool
def get_schema(
    context: RunContextWrapper[WorkbookContext],
    sheet_name: Optional[str] = None,
) -> dict[str, Any]:
    """Return row count, columns, and dtypes for one sheet."""
    ctx = context.context
    try:
        df = ctx.get_df(sheet_name)
        chosen = sheet_name or ctx.active_sheet
        return {
            "sheet": chosen,
            "row_count": int(len(df)),
            "columns": [{"name": c, "dtype": str(df[c].dtype)} for c in df.columns],
        }
    except Exception as exc:
        return {"error": str(exc)}


@function_tool
def filter_equals(
    context: RunContextWrapper[WorkbookContext],
    column: str,
    value: str,
    sheet_name: Optional[str] = None,
    limit: int = 20,
) -> dict[str, Any]:
    """Return rows where a column exactly matches the provided value."""
    ctx = context.context
    try:
        df = ctx.get_df(sheet_name)
        chosen = sheet_name or ctx.active_sheet

        if column not in df.columns:
            return {"error": f"Unknown column: {column}"}

        mask = df[column].astype(str).str.strip() == str(value).strip()
        matched = df[mask]

        return {
            "sheet": chosen,
            "matched_rows": int(mask.sum()),
            "rows": _rows_to_records(matched, limit=limit),
        }
    except Exception as exc:
        return {"error": str(exc)}


@function_tool
def top_n(
    context: RunContextWrapper[WorkbookContext],
    sort_by: str,
    n: int = 5,
    ascending: bool = False,
    sheet_name: Optional[str] = None,
) -> dict[str, Any]:
    """Return the top-N rows after sorting by one column."""
    ctx = context.context
    try:
        df = ctx.get_df(sheet_name)
        chosen = sheet_name or ctx.active_sheet

        if sort_by not in df.columns:
            return {"error": f"Unknown column: {sort_by}"}

        out = df.sort_values(sort_by, ascending=ascending)
        return {
            "sheet": chosen,
            "rows": _rows_to_records(out, limit=n),
        }
    except Exception as exc:
        return {"error": str(exc)}


@function_tool
def aggregate(
    context: RunContextWrapper[WorkbookContext],
    group_by: str,
    metric: str,
    agg: str = "sum",
    sheet_name: Optional[str] = None,
    limit: int = 50,
) -> dict[str, Any]:
    """Group by one column and aggregate another with sum/mean/count/min/max."""
    ctx = context.context
    try:
        df = ctx.get_df(sheet_name)
        chosen = sheet_name or ctx.active_sheet

        if group_by not in df.columns:
            return {"error": f"Unknown group_by column: {group_by}"}
        if metric not in df.columns:
            return {"error": f"Unknown metric column: {metric}"}
        if agg not in {"sum", "mean", "count", "min", "max"}:
            return {"error": f"Unsupported aggregation: {agg}"}

        out = df.groupby(group_by, dropna=False)[metric].agg(agg).reset_index()
        return {
            "sheet": chosen,
            "rows": _rows_to_records(out, limit=limit),
        }
    except Exception as exc:
        return {"error": str(exc)}


spreadsheet_agent = Agent[WorkbookContext](
    name="Current Data Spreadsheet Agent",
    model=CURRENT_DATA_MODEL,
    instructions=(
        "You answer questions about the current Excel or CSV file using tools. "
        "Use tools for all factual and numeric claims. "
        "Do not invent values. "
        "Inspect sheets and schema before answering when needed. "
        "Be concise and mention the active sheet when helpful."
    ),
    tools=[
        list_sheets,
        set_active_sheet,
        get_schema,
        filter_equals,
        top_n,
        aggregate,
    ],
)


class CurrentDataAgentExecutor(AgentExecutor):
    """A2A executor that wraps your existing OpenAI spreadsheet agent."""

    def __init__(self, workbook_path: str) -> None:
        self.workbook_path = workbook_path

    async def execute(self, context, event_queue) -> None:
        task = context.current_task or new_task(context.message)
        await event_queue.enqueue_event(task)

        await event_queue.enqueue_event(
            TaskStatusUpdateEvent(
                task_id=context.task_id,
                context_id=context.context_id,
                status=TaskStatus(
                    state=TaskState.TASK_STATE_WORKING,
                    message=new_agent_text_message("Analyzing spreadsheet..."),
                ),
            )
        )

        workbook_ctx = WorkbookContext(workbook_path=self.workbook_path)
        workbook_ctx.load()
        user_text = get_message_text(context.message)

        result = await Runner.run(
            spreadsheet_agent,
            input=user_text,
            context=workbook_ctx,
        )

        answer_text = str(result.final_output).strip()
        if not answer_text:
            answer_text = "No answer was produced."

        await event_queue.enqueue_event(
            TaskArtifactUpdateEvent(
                task_id=context.task_id,
                context_id=context.context_id,
                artifact=new_text_artifact(name="answer", text=answer_text),
            )
        )
        await event_queue.enqueue_event(
            TaskStatusUpdateEvent(
                task_id=context.task_id,
                context_id=context.context_id,
                status=TaskStatus(state=TaskState.TASK_STATE_COMPLETED),
            )
        )

    async def cancel(self, context, event_queue) -> None:
        raise Exception("cancel not supported")


def build_app() -> Any:
    skill = AgentSkill(
        id="spreadsheet_qa",
        name="Spreadsheet Q&A",
        description="Answers user questions from the current Excel or CSV file.",
        tags=["excel", "csv", "spreadsheet", "data"],
        examples=[
            "Which sheet contains sales data?",
            "Show the top 5 rows by revenue.",
            "Total sales by region.",
        ],
    )

    agent_card = AgentCard(
        name="Current Data A2A Agent",
        description="Remote spreadsheet agent backed by the OpenAI Agents SDK.",
        version="1.0.0",
        default_input_modes=["text"],
        default_output_modes=["text"],
        capabilities=AgentCapabilities(streaming=True),
        supported_interfaces=[
            AgentInterface(
                protocol_binding="JSONRPC",
                url=CURRENT_DATA_PUBLIC_URL,
            )
        ],
        skills=[skill],
    )

    request_handler = DefaultRequestHandler(
        agent_executor=CurrentDataAgentExecutor(workbook_path=CURRENT_DATA_FILE),
        task_store=InMemoryTaskStore(),
    )

    return A2AStarletteApplication(
        agent_card=agent_card,
        http_handler=request_handler,
    ).build()


app = build_app()


if __name__ == "__main__":
    uvicorn.run(app, host=CURRENT_DATA_HOST, port=CURRENT_DATA_PORT)
