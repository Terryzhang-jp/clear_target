from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel

from ..dependencies import get_db, get_current_user, get_password_hash
from ..models import User
from ..schemas import UserCreate, User as UserSchema

router = APIRouter(prefix="/users", tags=["users"])

@router.post("", response_model=UserSchema)
async def create_user(user: UserCreate, db: Session = Depends(get_db)):
    """创建新用户"""
    # 检查邮箱是否已存在
    db_user = await db.execute(
        User.__table__.select().where(User.email == user.email)
    )
    if db_user.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="邮箱已被注册"
        )
    
    # 创建新用户
    db_user = User(
        email=user.email,
        hashed_password=get_password_hash(user.password)
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user

@router.get("/me", response_model=UserSchema)
async def read_users_me(current_user: User = Depends(get_current_user)):
    """获取当前用户信息"""
    return current_user 