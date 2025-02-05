from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
import json
import logging

from . import models, schemas
from .dependencies import (
    get_db, get_current_user, create_access_token, authenticate_user,
    generate_questions, generate_goal_breakdown, generate_implementation_plan
)
from .config import get_settings
from .routers import goals

# 配置logger
logger = logging.getLogger(__name__)

settings = get_settings()

app = FastAPI(
    title="Goal Planner API",
    description="API for goal planning and tracking",
    version="1.0.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # 前端开发服务器地址
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600
)

# 注册路由
app.include_router(goals.router, prefix=settings.API_V1_STR)

@app.get("/")
async def root():
    return {"message": "Welcome to Goal Planner API"}

@app.post(f"{settings.API_V1_STR}/register", response_model=schemas.User)
async def register(user: schemas.UserCreate, db: AsyncSession = Depends(get_db)):
    db_user = await db.execute(
        models.User.__table__.select().where(models.User.email == user.email)
    )
    if db_user.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="Email already registered"
        )
    
    from .dependencies import get_password_hash
    db_user = models.User(
        email=user.email,
        hashed_password=get_password_hash(user.password)
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user

@app.post(f"{settings.API_V1_STR}/login")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    user = await authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(
        data={"sub": user.email}
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.post(f"{settings.API_V1_STR}/goals", response_model=schemas.Goal)
async def create_goal(
    goal: schemas.GoalCreate,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    db_goal = models.Goal(**goal.dict(), user_id=current_user.id)
    db.add(db_goal)
    await db.commit()
    await db.refresh(db_goal)
    return db_goal

@app.post(f"{settings.API_V1_STR}/goals/{{goal_id}}/questions")
async def generate_goal_questions(
    goal_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    result = await db.execute(
        models.Goal.__table__.select().where(
            models.Goal.id == goal_id,
            models.Goal.user_id == current_user.id
        )
    )
    goal_data = result.first()
    if not goal_data:
        raise HTTPException(status_code=404, detail="Goal not found")
    
    # 从元组中获取wish和outcome
    wish = goal_data[2]  # 第三个元素是wish
    outcome = goal_data[3]  # 第四个元素是outcome
    
    questions = await generate_questions(wish, outcome)
    return questions  # 直接返回字典，不需要json.loads

@app.post(f"{settings.API_V1_STR}/goals/{{goal_id}}/breakdown")
async def create_goal_breakdown(
    goal_id: int,
    answers: list[dict],
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    try:
        # 获取目标信息
        result = await db.execute(
            models.Goal.__table__.select().where(
                models.Goal.id == goal_id,
                models.Goal.user_id == current_user.id
            )
        )
        goal_data = result.first()
        if not goal_data:
            raise HTTPException(status_code=404, detail="Goal not found")
        
        wish = goal_data[2]  # 第三个元素是wish
        outcome = goal_data[3]  # 第四个元素是outcome
        
        # 转换答案格式
        answers_dict = {
            str(i+1): {
                "question": answer.get("question", ""),
                "answer": answer.get("answer", "")
            }
            for i, answer in enumerate(answers)
        }
        
        # 生成目标分解（现在直接返回字典）
        goal_breakdown = await generate_goal_breakdown(wish, outcome, answers_dict)
        
        # 更新数据库
        await db.execute(
            models.Goal.__table__.update().where(
                models.Goal.id == goal_id
            ).values(
                questions_answers=answers,
                goal_breakdown=goal_breakdown
            )
        )
        await db.commit()
        
        return goal_breakdown
        
    except Exception as e:
        print(f"Error in create_goal_breakdown: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

@app.post(f"{settings.API_V1_STR}/goals/{{goal_id}}/implementation")
async def create_implementation_plan(
    goal_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    try:
        # 获取目标
        result = await db.execute(
            models.Goal.__table__.select().where(
                models.Goal.id == goal_id,
                models.Goal.user_id == current_user.id
            )
        )
        goal_data = result.first()
        if not goal_data:
            raise HTTPException(status_code=404, detail="目标不存在")
        
        # 检查是否有目标分解
        goal_breakdown = goal_data[7]  # goal_breakdown 在第8列
        if not goal_breakdown:
            raise HTTPException(
                status_code=400,
                detail="必须先完成目标分解"
            )
        
        try:
            # 生成实施方案
            implementation = await generate_implementation_plan(goal_breakdown)
            
            # 更新数据库
            await db.execute(
                models.Goal.__table__.update().where(
                    models.Goal.id == goal_id
                ).values(
                    implementation_plan=implementation
                )
            )
            await db.commit()
            
            return implementation
            
        except Exception as e:
            await db.rollback()
            logger.error(f"生成实施方案失败: {str(e)}")
            if isinstance(e, HTTPException):
                raise e
            raise HTTPException(
                status_code=500,
                detail=f"生成实施方案时出错：{str(e)}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"处理请求时出错: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"处理请求时出错：{str(e)}"
        )

@app.get(f"{settings.API_V1_STR}/goals", response_model=list[schemas.Goal])
async def get_goals(
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    result = await db.execute(
        models.Goal.__table__.select().where(models.Goal.user_id == current_user.id)
    )
    goals = result.all()
    return [
        {
            "id": goal[0],
            "user_id": goal[1],
            "wish": goal[2],
            "outcome": goal[3],
            "created_at": goal[4],
            "updated_at": goal[5],
            "questions_answers": goal[6],
            "goal_breakdown": goal[7],
            "implementation_plan": goal[8]
        }
        for goal in goals
    ]

@app.get(f"{settings.API_V1_STR}/goals/{{goal_id}}", response_model=schemas.Goal)
async def get_goal(
    goal_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    result = await db.execute(
        models.Goal.__table__.select().where(
            models.Goal.id == goal_id,
            models.Goal.user_id == current_user.id
        )
    )
    goal = result.first()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    
    return {
        "id": goal[0],
        "user_id": goal[1],
        "wish": goal[2],
        "outcome": goal[3],
        "created_at": goal[4],
        "updated_at": goal[5],
        "questions_answers": goal[6],
        "goal_breakdown": goal[7],
        "implementation_plan": goal[8]
    }

@app.delete(f"{settings.API_V1_STR}/goals/{{goal_id}}")
async def delete_goal(
    goal_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    result = await db.execute(
        models.Goal.__table__.select().where(
            models.Goal.id == goal_id,
            models.Goal.user_id == current_user.id
        )
    )
    goal = result.scalar_one_or_none()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    
    await db.execute(
        models.Goal.__table__.delete().where(
            models.Goal.id == goal_id,
            models.Goal.user_id == current_user.id
        )
    )
    await db.commit()
    
    return {"message": "Goal deleted successfully"}
