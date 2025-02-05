import json

class PromptManager:
    @staticmethod
    def get_question_generation_prompt(wish: str, outcome: str) -> str:
        return f"""你是一个目标分析专家。在你面前的用户对实现目标没有清晰认知。你的任务是基于用户的目标(W)和期望结果(O)，生成3个最关键的问题，这些问题的答案将帮助我们更好地理解用户情况并制定计划。

输入：
- W (Wish): {wish}
- O (Outcome): {outcome}

要求：
1. 问题必须针对目标实现最关键的因素
2. 问题要简单直接，容易回答
3. 问题要能获取有价值的信息
4. 避免一般性或显而易见的问题

请以JSON格式输出，格式如下：
{{
  "analysis": {{
    "goal_summary": "对目标的理解",
    "key_concerns": ["需要明确的关键点1", "关键点2", "关键点3"]
  }},
  "questions": [
    {{
      "id": "q1",
      "question": "问题1",
      "purpose": "这个问题为什么重要",
      "expected_insight": "期望获得什么信息"
    }}
  ]
}}"""

    @staticmethod
    def get_questions_prompt(wish: str, outcome: str) -> str:
        return f"""作为一个目标分解专家，我需要你帮助用户更好地理解和分解他们的目标。
用户的愿望是：{wish}
期望的结果是：{outcome}

请生成5个问题来帮助用户更好地思考和分解这个目标。每个问题都应该：
1. 有助于深入理解目标
2. 引导用户思考具体的行动步骤
3. 帮助识别潜在的障碍和解决方案

请按以下格式返回JSON：
{{
    "questions": [
        {{
            "id": "1",
            "question": "问题内容",
            "purpose": "这个问题的目的是什么",
            "expected_insight": "期望从答案中获得什么洞察"
        }},
        ...
    ]
}}"""

    @staticmethod
    def get_goal_breakdown_prompt(wish: str, outcome: str, answers: list, phase_count: int = 3) -> str:
        """生成目标分解的提示词"""
        # 构建问题答案的字符串
        answers_text = "\n".join([
            f"问题：{answer['question'] if isinstance(answer, dict) else str(answer)}\n" +
            f"回答：{answer['answer'] if isinstance(answer, dict) and 'answer' in answer else ''}"
            for answer in answers
        ])
        
        return f"""你是一个目标分解与规划专家。基于用户的目标(W)、期望结果(O)和问题回答，你的任务是制定清晰的目标达成路径。

输入：
- W (Wish): {wish}
- O (Outcome): {outcome}
- 阶段数量: {phase_count}
- Answers: 
{answers_text}

请基于以上信息，制定详细的目标分解和阶段规划。要求：
1. 分析目标的可测量标准
2. 设计清晰的阶段性规划，必须严格按照指定的 {phase_count} 个阶段来规划
3. 每个阶段都要有明确的里程碑和验收标准
4. 确保每个技能和任务都有具体的测试方法
5. 阶段之间要有清晰的递进关系，后一个阶段建立在前一个阶段的基础上
6. 每个阶段的重点维度要互补，共同推进目标达成

输出格式：
{{
  "goal": {{
    "description": "整合后的目标描述",
    "completion_criteria": {{
      "must_have_skills": [
        {{
          "skill": "核心技能1",
          "measure": "如何测试这个技能",
          "standard": "达到什么水平算及格"
        }}
      ],
      "must_complete_tasks": [
        {{
          "task": "必须能完成的任务1",
          "success_criteria": "完成到什么程度算成功"
        }}
      ],
      "validation_methods": [
        "如何验证真的达到目标"
      ]
    }}
  }},
  "phases": [
    {{
      "id": "p1",
      "name": "阶段1",
      "focus_dimensions": ["重点维度1", "重点维度2"],
      "milestones": [
        {{
          "name": "里程碑1",
          "test_method": "如何测试",
          "passing_criteria": "达到什么标准算通过",
          "validation_task": "能完成什么实际任务"
        }}
      ],
      "exit_criteria": {{
        "skills_checklist": [
          {{
            "skill": "需要掌握的技能",
            "level": "要求达到的水平",
            "test": "如何测试"
          }}
        ],
        "practical_tasks": [
          {{
            "task": "需要完成的任务",
            "acceptance_criteria": "验收标准"
          }}
        ]
      }}
    }}
  ]
}}"""

    @staticmethod
    def get_implementation_plan_prompt(goal_breakdown: dict) -> str:
        return f"""你是一个解决方案设计专家。基于已确认的目标分解和阶段规划，你的任务是设计具体的实施方案。

输入：
- 已确认的目标分解和阶段规划：
{json.dumps(goal_breakdown, ensure_ascii=False, indent=2)}

要求：
1. 每个维度至少5-20个选项
2. 每个选项3-10个具体行动
3. 所有内容必须直接贡献目标实现
4. 行动必须具体可执行
5. 必须完整输出所有维度的所有选项，不得使用省略号或注释
6. 不要使用任何形式的注释（包括 // 或 /* */）
7. 确保输出的是完整且有效的JSON格式

输出格式：
{{
  "dimensions": [
    {{
      "id": "d1",
      "name": "维度名称",
      "why": "为什么这个维度重要",
      "phase": "属于哪个阶段",
      "options": [
        {{
          "id": "d1_o1",
          "name": "选项名称",
          "difficulty": "1-5",
          "time_cost": "预计时间",
          "actions": [
            "具体可执行的行动1",
            "具体可执行的行动2"
          ]
        }}
      ]
    }}
  ]
}}

验证要求：
1. 所有选项和行动必须与目标阶段匹配
2. 确保难度递进合理
3. 每个行动都必须具体可执行
4. 时间预估要实际可行
5. 确保每个维度都有完整的选项列表，不要使用省略或注释
6. 输出必须是完整且有效的JSON格式"""
