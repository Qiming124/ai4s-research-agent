# ReAct 子图状态定义。

from __future__ import annotations

import operator
from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

from shared.schemas import PersistedToolCall


class ReactState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    tool_call_records: Annotated[list[PersistedToolCall], operator.add]
    tool_rounds: int
