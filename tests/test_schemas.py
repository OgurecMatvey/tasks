"""Валидация входных данных на уровне Pydantic: БД не нужна."""

from datetime import date

from pydantic import ValidationError

from app.schemas import TaskCreate, TaskUpdate


def _invalid(model, **kwargs) -> bool:
    try:
        model(**kwargs)
    except ValidationError:
        return True
    return False


def test_defaults():
    task = TaskCreate(title="  Buy milk  ")
    assert task.title == "Buy milk"  # пробелы по краям обрезаются
    assert (task.status, task.priority) == ("todo", 2)
    assert task.description is None and task.due_date is None


def test_full_payload():
    task = TaskCreate(title="Report", description="text", status="in_progress", priority=3, due_date="2026-12-31")
    assert task.due_date == date(2026, 12, 31)


def test_invalid_create_payloads():
    assert _invalid(TaskCreate)  # title обязателен
    assert _invalid(TaskCreate, title="   ")
    assert _invalid(TaskCreate, title="x" * 201)
    assert _invalid(TaskCreate, title="ok", status="finished")
    assert _invalid(TaskCreate, title="ok", priority=0)
    assert _invalid(TaskCreate, title="ok", priority=4)
    assert _invalid(TaskCreate, title="ok", due_date="31-12-2026")


def test_update_distinguishes_missing_from_null():
    only_title = TaskUpdate(title="New")
    assert only_title.model_dump(exclude_unset=True) == {"title": "New"}

    clear_description = TaskUpdate(description=None)
    assert clear_description.model_dump(exclude_unset=True) == {"description": None}

    assert TaskUpdate().model_dump(exclude_unset=True) == {}


def test_invalid_update_payloads():
    assert _invalid(TaskUpdate, title="   ")
    assert _invalid(TaskUpdate, status="nope")
    assert _invalid(TaskUpdate, priority=9)
