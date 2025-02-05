# Clear Target - 目标管理与实现系统

Clear Target 是一个智能目标管理系统，帮助用户将大目标分解为可执行的具体步骤，并提供详细的实施方案。

## 功能特点

- 🎯 智能目标分析：通过 AI 分析用户目标，提供针对性问题
- 📊 目标分解：将大目标分解为可管理的阶段和维度
- 📝 详细实施方案：为每个维度提供具体可执行的行动选项
- 📈 进度追踪：可视化展示目标完成进度
- 🔄 灵活调整：根据实际情况随时调整实施方案

## 技术栈

### 后端
- FastAPI
- SQLAlchemy
- Google Gemini AI
- Python 3.11+

### 前端
- Next.js 14
- React
- Tailwind CSS
- TypeScript

## 快速开始

### 后端设置

1. 进入后端目录：
```bash
cd backend
```

2. 安装依赖：
```bash
pip install -r requirements.txt
```

3. 设置环境变量：
```bash
cp .env.example .env
# 编辑 .env 文件，填入必要的配置信息
```

4. 运行数据库迁移：
```bash
python init_db.py
```

5. 启动服务器：
```bash
uvicorn app.main:app --reload
```

### 前端设置

1. 进入前端目录：
```bash
cd frontend
```

2. 安装依赖：
```bash
npm install
```

3. 设置环境变量：
```bash
cp .env.example .env.local
# 编辑 .env.local 文件，填入必要的配置信息
```

4. 启动开发服务器：
```bash
npm run dev
```

## 系统功能说明

1. **目标设定**
   - 用户输入期望达成的目标和期望结果
   - 系统通过 AI 分析目标的可行性和关键要素

2. **目标分析**
   - 系统生成针对性问题，帮助用户深入思考
   - 收集用户回答，用于后续方案制定

3. **目标分解**
   - 将目标分解为多个阶段
   - 每个阶段设定具体的里程碑和验收标准

4. **实施方案**
   - 为每个维度提供多个可选的学习/执行方案
   - 每个选项包含具体的行动步骤
   - 标注难度和预计时间成本

5. **进度追踪**
   - 可视化展示整体进度
   - 分阶段、分维度的完成情况
   - 提供学习建议和最佳实践

## 贡献指南

欢迎提交 Pull Request 或创建 Issue！

## 许可证

本项目采用 MIT 许可证。 