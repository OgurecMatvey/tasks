from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Status = Literal["todo", "in_progress", "done"]


def _clean_title(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("Title must not be empty")
    return value


class TaskCreate(BaseModel):
    title: str = Field(max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    status: Status = "todo"
    priority: int = Field(default=2, ge=1, le=3, description="1 низкий, 2 средний, 3 высокий")
    due_date: date | None = None

    @field_validator("title")
    @classmethod
    def check_title(cls, value: str) -> str:
        return _clean_title(value)


class TaskUpdate(BaseModel):
    """PATCH: передаются только изменяемые поля. description и due_date можно очистить, передав null;
    для остальных полей null недопустим (проверяет роутер)."""

    title: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    status: Status | None = None
    priority: int | None = Field(default=None, ge=1, le=3)
    due_date: date | None = None

    @field_validator("title")
    @classmethod
    def check_title(cls, value: str | None) -> str | None:
        return None if value is None else _clean_title(value)


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None
    status: str
    priority: int
    due_date: date | None
    created_at: datetime
    updated_at: datetime


class TaskPage(BaseModel):
    items: list[TaskOut]
    total: int  # всего задач под фильтр, независимо от limit/offset
    limit: int
    offset: int
