from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from pydantic import BaseModel
from database import get_db
from models import Task, User
from routers.auth import get_user, TokenData
from jose import JWTError, jwt

SECRET_KEY = "your-secret-key"
ALGORITHM = "HS256"

router = APIRouter()

# Модели данных
class TaskCreate(BaseModel):
    title: str
    description: str
    status: str

class TaskResponse(TaskCreate):
    id: int
    user_id: int

async def get_current_user(authorization: str = Header(...), db: AsyncSession = Depends(get_db)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authorization header")
    
    token = authorization.split(" ")[1]  # Извлекаем токен после "Bearer"
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        
        # Используем асинхронный запрос к базе данных
        result = await db.execute(select(User).where(User.username == username))
        user = result.scalars().first()
        
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        
        return user
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

# Создание задачи
@router.post("/", response_model=TaskResponse)
async def create_task(task: TaskCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    new_task = Task(title=task.title, description=task.description, status=task.status, user_id=current_user.id)
    db.add(new_task)
    await db.commit()
    await db.refresh(new_task)

    # Возвращаем TaskResponse
    return TaskResponse(
        id=new_task.id,
        title=new_task.title,
        description=new_task.description,
        status=new_task.status,
        user_id=new_task.user_id
    )

# Получение списка задач
@router.get("/", response_model=list[TaskResponse])
async def get_tasks(status: str | None = None, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    query = await db.execute(select(Task).filter(Task.user_id == current_user.id))
    tasks = query.scalars().all()
    
    if status:
        tasks = [task for task in tasks if task.status == status]

    # Возвращаем список TaskResponse
    return [TaskResponse(
        id=task.id,
        title=task.title,
        description=task.description,
        status=task.status,
        user_id=task.user_id
    ) for task in tasks]

# Обновление задачи
@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(task_id: int, task: TaskCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    db_task = await db.execute(select(Task).filter(Task.id == task_id, Task.user_id == current_user.id))
    db_task = db_task.scalars().first()
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")

    db_task.title = task.title
    db_task.description = task.description
    db_task.status = task.status
    await db.commit()
    await db.refresh(db_task)

    # Возвращаем TaskResponse
    return TaskResponse(
        id=db_task.id,
        title=db_task.title,
        description=db_task.description,
        status=db_task.status,
        user_id=db_task.user_id
    )

# Удаление задачи
@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(task_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    db_task = await db.execute(select(Task).filter(Task.id == task_id, Task.user_id == current_user.id))
    db_task = db_task.scalars().first()
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    await db.delete(db_task)
    await db.commit()
