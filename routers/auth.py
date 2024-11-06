from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from passlib.context import CryptContext
from datetime import datetime, timedelta
from jose import JWTError, jwt
from database import get_db
from models import User
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
import logging
from redis_client import redis 
from uuid import uuid4
from fastapi import Body

REFRESH_TOKEN_EXPIRE_MINUTES = 1440  # Например, 1 день

SECRET_KEY = "your-secret-key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Модели данных
class UserCreate(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenWithRefresh(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class TokenData(BaseModel):
    username: str | None = None

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_user(db: AsyncSession, username: str):
    result = await db.execute(select(User).where(User.username == username))
    return result.scalars().first()

async def authenticate_user(db: AsyncSession, username: str, password: str):
    user = await get_user(db, username)
    if not user:
        return None
    # Используем правильное имя поля
    if not verify_password(password, user.password_hash):
        return None
    return user

async def create_refresh_token(username: str):
    refresh_token = str(uuid4())
    await redis.setex(refresh_token, timedelta(minutes=REFRESH_TOKEN_EXPIRE_MINUTES), username)
    return refresh_token


# Регистрация пользователя
@router.post("/register", response_model=Token)
async def register(user: UserCreate, db: Session = Depends(get_db)):
    db_user = await get_user(db, user.username)
    if db_user:
        logger.warning(f"Регистрация не удалась: имя пользователя '{user.username}' уже зарегистрировано.")
        raise HTTPException(status_code=400, detail="Username already registered")
    
    hashed_password = get_password_hash(user.password)
    new_user = User(username=user.username, password_hash=hashed_password)
    db.add(new_user)
    await db.commit()  # Убедитесь, что вы используете асинхронный метод
    await db.refresh(new_user)
    
    access_token = create_access_token(data={"sub": user.username})
    logger.info(f"Пользователь '{user.username}' успешно зарегистрирован.")
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/login", response_model=TokenWithRefresh)
async def login(user: UserCreate, db: AsyncSession = Depends(get_db)):
    db_user = await authenticate_user(db, user.username, user.password)
    if not db_user:
        logger.warning(f"Неудачный вход: неверные имя пользователя или пароль для '{user.username}'.")
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    
    access_token = create_access_token(data={"sub": db_user.username})
    refresh_token = await create_refresh_token(db_user.username)
    
    logger.info(f"Пользователь '{user.username}' успешно вошел в систему.")
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }


@router.post("/refresh", response_model=Token)
async def refresh_token(request: RefreshTokenRequest):
    username = await redis.get(request.refresh_token)
    if not username:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    
    new_access_token = create_access_token(data={"sub": username})
    logger.info(f"Токен успешно обновлен для пользователя '{username}'.")
    return {"access_token": new_access_token, "token_type": "bearer"}
