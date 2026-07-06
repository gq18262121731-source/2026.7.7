# Runbook

## Backend

```powershell
cd F:\学校\病虫害识别\mark-video-demo\backend
..\.venv\Scripts\python.exe -m pip install -r requirements.txt
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

## Frontend

```powershell
cd F:\学校\病虫害识别\mark-video-demo\frontend
npm install
npm run dev
```

前端地址：

```text
http://localhost:5173
```

后端 API：

```text
http://localhost:8000/api/health
```
