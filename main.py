from fastapi import FastAPI
from routers import auth, tasks
from database import create_database

app = FastAPI()

# Регистрация роутов
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(tasks.router, prefix="/tasks", tags=["Tasks"])

@app.on_event("startup")
async def startup():
    await create_database()