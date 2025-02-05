from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, Any, List
from datetime import datetime

class UserBase(BaseModel):
    email: EmailStr

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: int
    
    class Config:
        from_attributes = True

class GoalBase(BaseModel):
    wish: str
    outcome: str

class GoalCreate(GoalBase):
    pass

class GoalUpdate(BaseModel):
    questions_answers: Optional[List[Dict[str, Any]]] = None
    goal_breakdown: Optional[Dict[str, Any]] = None
    implementation_plan: Optional[Dict[str, Any]] = None

class Goal(GoalBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime
    questions_answers: Optional[List[Dict[str, Any]]] = None
    goal_breakdown: Optional[Dict[str, Any]] = None
    implementation_plan: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

# Gemini API响应模型
class QuestionGeneration(BaseModel):
    analysis: Dict[str, Any]
    questions: List[Dict[str, Any]]

class GoalBreakdown(BaseModel):
    goal: Dict[str, Any]
    phases: List[Dict[str, Any]]

class ImplementationPlan(BaseModel):
    dimensions: List[Dict[str, Any]]
