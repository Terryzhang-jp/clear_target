from typing import Generator, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
import google.generativeai as genai
import json
import logging

from .config import get_settings
from . import models, schemas
from .prompts import PromptManager

# 配置logger
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

settings = get_settings()

# 数据库配置
engine = create_async_engine(settings.DATABASE_URL, echo=True)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# 密码哈希配置
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2配置
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/login")

# Gemini配置
genai.configure(api_key=settings.GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

async def get_db() -> Generator:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

async def get_user(db: AsyncSession, email: str):
    stmt = models.User.__table__.select().where(models.User.email == email)
    result = await db.execute(stmt)
    user = result.first()
    if user:
        return models.User(
            id=user[0],
            email=user[1],
            hashed_password=user[2]
        )
    return None

async def authenticate_user(db: AsyncSession, email: str, password: str):
    user = await get_user(db, email)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

async def get_current_user(
    db: AsyncSession = Depends(get_db),
    token: str = Depends(oauth2_scheme)
) -> models.User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        token_data = schemas.TokenData(email=email)
    except JWTError:
        raise credentials_exception
    user = await get_user(db, email=token_data.email)
    if user is None:
        raise credentials_exception
    return user

# Gemini相关函数
async def generate_questions(wish: str, outcome: str) -> dict:
    try:
        # 获取提示词
        prompt = PromptManager.get_question_generation_prompt(wish, outcome)
        print(f"Sending prompt to Gemini: {prompt}")
        
        # 调用 Gemini API
        response = model.generate_content(prompt)
        print(f"Received response from Gemini: {response.text}")
        
        # 尝试解析响应
        response_text = response.text.strip()
        
        # 如果响应为空
        if not response_text:
            print("Empty response from Gemini")
            return get_default_questions()
        
        # 清理 Markdown 代码块标记
        if response_text.startswith('```'):
            # 找到第一个和最后一个 ``` 的位置
            first_block = response_text.find('```')
            last_block = response_text.rfind('```')
            if first_block != last_block:
                # 提取代码块内容
                start_content = response_text.find('\n', first_block) + 1
                content = response_text[start_content:last_block].strip()
                response_text = content
                print(f"Extracted content from code block: {content[:100]}...")  # 打印前100个字符
        
        # 尝试找到并提取 JSON 部分
        try:
            # 首先尝试直接解析整个响应
            result = json.loads(response_text)
        except json.JSONDecodeError as e:
            print(f"Initial JSON parse failed: {e}")
            print("Attempting to clean and parse JSON")
            
            # 清理常见的格式问题
            response_text = response_text.replace('\n', ' ').replace('\r', '')
            response_text = response_text.strip()
            
            # 尝试查找 JSON 对象
            start = response_text.find('{')
            end = response_text.rfind('}') + 1
            
            if start >= 0 and end > start:
                json_str = response_text[start:end]
                try:
                    result = json.loads(json_str)
                    print(f"Successfully parsed JSON after cleaning: {json_str[:100]}...")
                except json.JSONDecodeError as e:
                    print(f"Failed to parse cleaned JSON: {e}")
                    return get_default_questions()
            else:
                print("No JSON object found in response")
                return get_default_questions()
        
        # 验证响应格式
        if not isinstance(result, dict):
            print(f"Result is not a dict: {type(result)}")
            return get_default_questions()
            
        if 'questions' not in result:
            print(f"No questions field in result: {result.keys()}")
            # 如果有 analysis 但没有 questions，尝试从 analysis 构建问题
            if 'analysis' in result and 'key_concerns' in result['analysis']:
                questions = []
                for i, concern in enumerate(result['analysis']['key_concerns'], 1):
                    questions.append({
                        'id': str(i),
                        'question': f'关于"{concern}"，你的具体情况是什么？',
                        'purpose': f'了解关于{concern}的详细信息',
                        'expected_insight': f'获取用户在{concern}方面的具体情况'
                    })
                result['questions'] = questions
            else:
                return get_default_questions()
            
        if not isinstance(result['questions'], list):
            print(f"Questions is not a list: {type(result['questions'])}")
            return get_default_questions()
            
        # 确保每个问题都有必要的字段
        for i, q in enumerate(result['questions']):
            if not isinstance(q, dict):
                print(f"Question {i} is not a dict: {type(q)}")
                continue
            
            # 确保必要的字段存在
            required_fields = ['id', 'question', 'purpose']
            missing_fields = [f for f in required_fields if f not in q]
            if missing_fields:
                print(f"Question {i} missing fields: {missing_fields}")
                # 补充缺失的字段
                if 'id' not in q:
                    q['id'] = str(i + 1)
                if 'question' not in q:
                    q['question'] = "请描述你的想法"
                if 'purpose' not in q:
                    q['purpose'] = "了解更多详细信息"
                if 'expected_insight' not in q:
                    q['expected_insight'] = "获取用户的具体想法"
        
        return result
        
    except Exception as e:
        print(f"Error in generate_questions: {str(e)}")
        return get_default_questions()

def get_default_questions():
    """返回默认的问题列表"""
    return {
        "questions": [
        {
            "id": "1",
                "question": "你对这个目标的理解是什么？",
                "purpose": "确保我们对目标有共同的理解",
                "expected_insight": "了解用户对目标的具体认知"
        },
        {
            "id": "2",
                "question": "你目前在这个方向上遇到的主要挑战是什么？",
                "purpose": "识别潜在的障碍",
                "expected_insight": "了解需要克服的具体困难"
        },
        {
            "id": "3",
                "question": "你希望在多长时间内达成这个目标？",
                "purpose": "设定时间框架",
                "expected_insight": "了解用户的时间期望"
            }
        ]
    }

async def generate_goal_breakdown(wish: str, outcome: str, answers: dict, phase_count: int = 3) -> dict:
    """生成目标分解"""
    try:
        logger.info(f"开始生成目标分解，阶段数量: {phase_count}")
        logger.debug(f"收到的answers: {answers}")  # 添加日志
        
        # 确保 answers 是列表格式
        if isinstance(answers, dict):
            answers_list = [
                {
                    "question": qa.get("question", ""),
                    "answer": qa.get("answer", "")
                }
                for qa in answers.values()
            ]
        else:
            answers_list = answers
        
        # 构建提示词
        try:
            prompt = PromptManager.get_goal_breakdown_prompt(wish, outcome, answers_list, phase_count)
            logger.info(f"生成的提示词: {prompt[:200]}...")  # 只记录前200个字符
        except Exception as e:
            logger.error(f"构建提示词失败: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail="生成提示词时出错，请重试"
            )
        
        # 调用Gemini API
        try:
            response = await get_gemini_response(prompt)
            logger.info("收到Gemini响应")
        except HTTPException as e:
            raise e
        except Exception as e:
            logger.error(f"调用Gemini API失败: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail="AI服务暂时不可用，请稍后重试"
            )
        
        # 清理响应文本
        response_text = response.text
        logger.debug(f"原始响应: {response_text[:200]}...")
        
        try:
            # 清理Markdown格式
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
                logger.info("从json代码块中提取内容")
            elif "```" in response_text:
                response_text = response_text.split("```")[1].strip()
                logger.info("从代码块中提取内容")
            
            # 解析JSON
            data = json.loads(response_text)
            logger.info("成功解析JSON响应")
            
            # 验证响应格式
            validate_goal_breakdown(data)
            logger.info("数据格式验证通过")
            
            # 确保每个阶段都有正确的ID
            for i, phase in enumerate(data["phases"]):
                phase["id"] = f"p{i+1}"
            
            return data
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析错误: {str(e)}\n响应文本: {response_text}")
            raise HTTPException(
                status_code=500,
                detail="生成的内容格式不正确，请重试"
            )
        except KeyError as e:
            logger.error(f"缺少必要字段: {str(e)}\n数据: {data}")
            raise HTTPException(
                status_code=500,
                detail=f"生成的内容缺少必要字段: {str(e)}"
            )
        except ValueError as e:
            logger.error(f"数据验证错误: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"生成的内容格式有误: {str(e)}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"生成目标分解时出错: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="生成目标分解时出错，请重试。如果问题持续存在，请联系支持。"
        )

def process_implementation_data(data: dict) -> dict:
    """处理实施方案数据，确保维度和选项的正确关系"""
    logger.info("开始处理实施方案数据")
    
    try:
        if not isinstance(data, dict):
            raise ValueError("输入数据必须是字典格式")
            
        if "dimensions" not in data:
            raise ValueError("数据缺少 dimensions 字段")
            
        if not isinstance(data["dimensions"], list):
            raise ValueError("dimensions 必须是列表格式")
        
        processed_dimensions = []
        
        # 遍历原始维度数据
        for i, dimension in enumerate(data.get("dimensions", [])):
            if not isinstance(dimension, dict):
                raise ValueError(f"维度 {i+1} 必须是字典格式")
                
            # 验证必要字段
            required_fields = ["id", "name", "why", "phase"]
            missing_fields = [f for f in required_fields if f not in dimension]
            if missing_fields:
                raise ValueError(f"维度 {dimension.get('name', f'#{i+1}')} 缺少必要字段: {', '.join(missing_fields)}")
            
            # 确保维度有基本结构
            processed_dimension = {
                "id": dimension.get("id"),
                "name": dimension.get("name"),
                "why": dimension.get("why", ""),
                "phase": dimension.get("phase", "p1"),
                "options": []
            }
            
            # 验证和处理选项
            if "options" not in dimension:
                raise ValueError(f"维度 {dimension.get('name')} 缺少 options 字段")
                
            if not isinstance(dimension["options"], list):
                raise ValueError(f"维度 {dimension.get('name')} 的 options 必须是列表格式")
            
            # 处理选项
            for j, option in enumerate(dimension["options"]):
                if not isinstance(option, dict):
                    raise ValueError(f"维度 {dimension.get('name')} 的选项 {j+1} 必须是字典格式")
                
                # 验证选项必要字段
                required_option_fields = ["id", "name", "difficulty", "time_cost", "actions"]
                missing_option_fields = [f for f in required_option_fields if f not in option]
                if missing_option_fields:
                    raise ValueError(f"选项 {option.get('name', f'#{j+1}')} 缺少必要字段: {', '.join(missing_option_fields)}")
                
                # 验证 actions 字段
                if not isinstance(option.get("actions"), list):
                    raise ValueError(f"选项 {option.get('name')} 的 actions 必须是列表格式")
                
                processed_option = {
                    "id": option.get("id"),
                    "name": option.get("name"),
                    "difficulty": option.get("difficulty", 1),
                    "time_cost": option.get("time_cost", ""),
                    "actions": option.get("actions", [])
                }
                
                # 验证 actions 不为空
                if not processed_option["actions"]:
                    raise ValueError(f"选项 {option.get('name')} 的 actions 不能为空")
                
                processed_dimension["options"].append(processed_option)
            
            # 验证选项不为空
            if not processed_dimension["options"]:
                raise ValueError(f"维度 {dimension.get('name')} 必须至少包含一个选项")
            
            processed_dimensions.append(processed_dimension)
        
        # 验证至少有一个维度
        if not processed_dimensions:
            raise ValueError("处理后的数据必须至少包含一个维度")
        
        logger.info(f"处理完成，共处理 {len(processed_dimensions)} 个维度")
        return {"dimensions": processed_dimensions}
        
    except Exception as e:
        logger.error(f"处理实施方案数据时出错: {str(e)}")
        raise ValueError(f"处理数据时出错: {str(e)}")

async def generate_implementation_plan(goal_breakdown: dict) -> dict:
    """生成实施方案"""
    try:
        logger.info("开始生成实施方案")
        
        # 构建提示词
        try:
            prompt = PromptManager.get_implementation_plan_prompt(goal_breakdown)
            logger.info("成功生成提示词")
        except Exception as e:
            logger.error(f"构建提示词失败: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail="生成提示词时出错，请重试"
            )
        
        # 调用Gemini API
        try:
            response = await get_gemini_response(prompt)
            logger.info("收到Gemini响应")
            logger.debug(f"原始响应: {response.text}")
        except Exception as e:
            logger.error(f"调用Gemini API失败: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail="AI服务暂时不可用，请稍后重试"
            )
        
        # 清理响应文本
        response_text = response.text.strip()
        
        try:
            # 提取JSON部分
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
            
            # 清理注释和格式化问题
            lines = []
            for line in response_text.split('\n'):
                # 跳过注释行和空行
                if line.strip().startswith('//') or not line.strip():
                    continue
                # 移除行内注释
                if '//' in line:
                    line = line.split('//')[0]
                lines.append(line.strip())
            
            # 重新组合文本
            cleaned_text = '\n'.join(lines)
            logger.debug(f"清理后的文本: {cleaned_text}")
            
            try:
                data = json.loads(cleaned_text)
            except json.JSONDecodeError as e:
                logger.error(f"JSON解析错误: {str(e)}\n清理后的文本: {cleaned_text}")
                # 尝试修复常见的JSON格式问题
                cleaned_text = cleaned_text.replace(',]', ']').replace(',}', '}')
                data = json.loads(cleaned_text)
            
            # 处理数据结构
            processed_data = process_implementation_data(data)
            logger.info("数据处理完成")
            
            return processed_data
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析错误: {str(e)}\n响应文本: {response_text}")
            raise HTTPException(
                status_code=500,
                detail="生成的内容格式不正确，请重试"
            )
        except ValueError as e:
            logger.error(f"数据验证错误: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=str(e)
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"生成实施方案时出错: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="生成实施方案时出错，请重试。如果问题持续存在，请联系支持。"
        )

def validate_goal_breakdown(data: dict) -> None:
    """验证目标分解的数据格式"""
    # 验证基本结构
    if not isinstance(data, dict):
        raise ValueError("数据必须是字典格式")
        
    # 验证goal字段
    if "goal" not in data:
        raise KeyError("缺少goal字段")
    
    goal = data["goal"]
    if not isinstance(goal, dict):
        raise ValueError("goal必须是字典格式")
        
    if "description" not in goal:
        raise KeyError("缺少goal.description字段")
        
    if "completion_criteria" not in goal:
        raise KeyError("缺少goal.completion_criteria字段")
        
    criteria = goal["completion_criteria"]
    if not isinstance(criteria, dict):
        raise ValueError("completion_criteria必须是字典格式")
        
    required_criteria_fields = ["must_have_skills", "must_complete_tasks", "validation_methods"]
    for field in required_criteria_fields:
        if field not in criteria:
            raise KeyError(f"缺少completion_criteria.{field}字段")
            
    # 验证phases字段
    if "phases" not in data:
        raise KeyError("缺少phases字段")
        
    phases = data["phases"]
    if not isinstance(phases, list):
        raise ValueError("phases必须是列表格式")
        
    for phase in phases:
        if not isinstance(phase, dict):
            raise ValueError("phase必须是字典格式")
            
        required_phase_fields = ["name", "focus_dimensions", "milestones", "exit_criteria"]
        for field in required_phase_fields:
            if field not in phase:
                raise KeyError(f"阶段缺少{field}字段")
                
        if not isinstance(phase["focus_dimensions"], list):
            raise ValueError("focus_dimensions必须是列表格式")
            
        if not isinstance(phase["milestones"], list):
            raise ValueError("milestones必须是列表格式")
            
        if not isinstance(phase["exit_criteria"], dict):
            raise ValueError("exit_criteria必须是字典格式")
            
        exit_criteria = phase["exit_criteria"]
        if "skills_checklist" not in exit_criteria or "practical_tasks" not in exit_criteria:
            raise KeyError("exit_criteria缺少必要字段")

async def get_gemini_response(prompt: str):
    """调用Gemini API并获取响应"""
    try:
        response = model.generate_content(prompt)
        if not response.text:
            raise ValueError("Empty response from Gemini")
        return response
    except Exception as e:
        logger.error(f"Gemini API调用失败: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="AI服务暂时不可用，请稍后重试"
        )
