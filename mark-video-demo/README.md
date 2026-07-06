# AI 水稻病虫害智能分析平台

面向水稻病虫害识别、风险分析与诊断建议的工程化平台。

## 目录结构

- `.ai/`: AI Coding 规范
- `backend/`: FastAPI 后端服务
- `frontend/`: React + Vite 前端
- `docs/`: 运行说明与项目文档
- `docs/`: 运行说明和录屏脚本
- `assets/`: 演示素材
- `outputs/`: 输出结果

## 后端

```powershell
cd backend
..\.venv\Scripts\python.exe -m pip install -r requirements.txt
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

## 前端

```powershell
cd frontend
npm install
npm run dev
```

打开 `http://localhost:5173`。
