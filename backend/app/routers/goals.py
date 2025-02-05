from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
import logging
from pydantic import BaseModel

from ..dependencies import get_db, get_current_user, generate_goal_breakdown
from ..models import Goal, User
from ..schemas import GoalCreate, GoalBreakdown

# 配置logger
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/goals", tags=["goals"])

class RegenerateRequest(BaseModel):
    phase_count: int

@router.post("/{goal_id}/regenerate")
async def regenerate_goal_breakdown(
    goal_id: int,
    request: RegenerateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """重新生成目标分解，可以指定阶段数量"""
    try:
        # 获取目标
        result = await db.execute(
            Goal.__table__.select().where(
                Goal.id == goal_id,
                Goal.user_id == current_user.id
            )
        )
        goal = result.first()
        if not goal:
            raise HTTPException(status_code=404, detail="目标不存在")
        
        # 验证权限
        if goal[1] != current_user.id:  # goal[1] 是 user_id
            raise HTTPException(status_code=403, detail="没有权限访问此目标")
        
        # 确保有问题答案
        questions_answers = goal[6]  # goal[6] 是 questions_answers
        if not questions_answers:
            raise HTTPException(status_code=400, detail="请先完成问题回答")
        
        logger.info(f"开始重新生成目标分解，目标ID: {goal_id}, 阶段数量: {request.phase_count}")
        logger.debug(f"问题答案: {questions_answers}")
        
        # 重新生成目标分解
        try:
            breakdown = await generate_goal_breakdown(
                goal[2],  # wish
                goal[3],  # outcome
                questions_answers,
                request.phase_count
            )
            
            # 更新数据库
            await db.execute(
                Goal.__table__.update()
                .where(Goal.id == goal_id)
                .values(goal_breakdown=breakdown)
            )
            await db.commit()
            
            logger.info(f"成功生成目标分解，目标ID: {goal_id}")
            return breakdown
            
        except Exception as e:
            logger.error(f"生成目标分解失败: {str(e)}")
            await db.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"生成目标分解时出错：{str(e)}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"处理请求时出错: {str(e)}")
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail="处理请求时出错，请重试"
        ) 