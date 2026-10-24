from datetime import date

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import func, select

from app.clock import utcnow
from app.deps import CurrentUser, SessionDep
from app.models import Task
from app.schemas import Status, TaskCreate, TaskOut, TaskPage, TaskUpdate
from app.utils import escape_like

router = APIRouter(prefix="/tasks", tags=["tasks"])

NULLABLE_FIELDS = {"description", "due_date"}


async def _get_owned(session, user, task_id: int) -> Task:
    task = (
        await session.execute(select(Task).where(Task.id == task_id, Task.user_id == user.id))
    ).scalar_one_or_none()
    if task is None:
        # чужая и несуществующая задача неотличимы: нельзя перебором узнать чужие id
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")
    return task


@router.post("", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
async def create_task(data: TaskCreate, user: CurrentUser, session: SessionDep):
    now = utcnow()
    task = Task(user_id=user.id, created_at=now, updated_at=now, **data.model_dump())
    session.add(task)
    await session.commit()
    return task


@router.get("", response_model=TaskPage)
async def list_tasks(
    user: CurrentUser,
    session: SessionDep,
    status_: Status | None = Query(None, alias="status"),
    priority: int | None = Query(None, ge=1, le=3),
    q: str | None = Query(None, max_length=100, description="Поиск по заголовку"),
    due_before: date | None = Query(None, description="Срок не позже этой даты"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    # user_id в условии есть всегда: пользователь физически не может получить чужие строки
    conditions = [Task.user_id == user.id]
    if status_ is not None:
        conditions.append(Task.status == status_)
    if priority is not None:
        conditions.append(Task.priority == priority)
    if q:
        conditions.append(Task.title.ilike(f"%{escape_like(q)}%", escape="\\"))
    if due_before is not None:
        conditions.append(Task.due_date <= due_before)

    total = await session.scalar(select(func.count()).select_from(Task).where(*conditions))
    # сортировка по id (новые первыми) делает порядок стабильным: страницы не перекрываются
    result = await session.scalars(
        select(Task).where(*conditions).order_by(Task.id.desc()).limit(limit).offset(offset)
    )
    return TaskPage(items=result.all(), total=total, limit=limit, offset=offset)


@router.get("/{task_id}", response_model=TaskOut)
async def get_task(task_id: int, user: CurrentUser, session: SessionDep):
    return await _get_owned(session, user, task_id)


@router.patch("/{task_id}", response_model=TaskOut)
async def update_task(task_id: int, data: TaskUpdate, user: CurrentUser, session: SessionDep):
    task = await _get_owned(session, user, task_id)
    changes = data.model_dump(exclude_unset=True)  # только поля, которые клиент реально передал
    for field, value in changes.items():
        if value is None and field not in NULLABLE_FIELDS:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"{field} cannot be null")
    for field, value in changes.items():
        setattr(task, field, value)
    task.updated_at = utcnow()
    await session.commit()
    return task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(task_id: int, user: CurrentUser, session: SessionDep):
    task = await _get_owned(session, user, task_id)
    await session.delete(task)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
