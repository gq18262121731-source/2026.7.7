# 前后端启动手册

本文档用于固化本项目本地开发启动方式，避免每次联调时重新排查端口、Python venv、Node 环境和存储状态问题。

## 1. 项目路径

```text
主后端：
F:\学校\病虫害识别\agri_uav_disease_system\backend

前端：
F:\学校\病虫害识别\mark-video-demo\frontend
```

默认服务地址：

```text
后端：http://127.0.0.1:8000
前端：http://127.0.0.1:5173
```

## 2. 前端启动

进入前端目录：

```powershell
cd F:\学校\病虫害识别\mark-video-demo\frontend
```

安装依赖：

```powershell
npm.cmd install
```

启动开发服务：

```powershell
npm.cmd run dev -- --host 127.0.0.1 --port 5173
```

构建验证：

```powershell
npm.cmd run build
```

预期：

```text
tsc -b 通过
vite build 通过
前端首页 http://127.0.0.1:5173 返回 200
```

## 3. 后端启动

进入后端目录：

```powershell
cd F:\学校\病虫害识别\agri_uav_disease_system\backend
```

推荐启动命令：

```powershell
.\.venv\Scripts\python.exe -m app.scripts.run_dev
```

如果原 `.venv` 失效，可能出现：

```text
Unable to create process using "C:\Users\13010\AppData\Local\Programs\Python\Python311\python.exe"
```

原因：

```text
backend\.venv\pyvenv.cfg 指向的 Python 3.11 路径已不存在。
```

临时处理方式：

```text
使用可用 Python 重新创建后端虚拟环境，或使用当前机器可用的 Python 环境安装 requirements.txt。
不要把该问题误判为后端业务代码错误。
```

无 reload 启动方式：

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

验证后端：

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/status
```

预期关键字段：

```text
service_status: running
database_status: ok
model_loaded: true 或 false
detector_mode: mock / smoke / real / experimental
```

## 4. 端口检查

检查默认端口：

```powershell
Get-NetTCPConnection -LocalPort 8000,5173 -ErrorAction SilentlyContinue |
  Select-Object LocalAddress,LocalPort,State,OwningProcess
```

如果端口被占用：

```text
前端可临时使用 5174
后端应尽量保持 8000，否则需要同步 VITE_API_BASE_URL
```

## 5. 前端环境变量

前端默认读取：

```text
VITE_API_BASE_URL=http://127.0.0.1:8000
VITE_MAIN_BACKEND_API_BASE=http://127.0.0.1:8000/api
```

如果后端不是 8000，需要在前端环境中配置：

```powershell
$env:VITE_API_BASE_URL="http://127.0.0.1:8000"
$env:VITE_MAIN_BACKEND_API_BASE="http://127.0.0.1:8000/api"
```

## 6. storage_status error 排查

后端 `/api/status` 可能返回：

```text
storage_status: error
static_original_writable: false
static_result_writable: false
```

该问题通常表示静态文件目录不可写，不等同于模型不可用。

重点检查：

```text
backend/app/static
backend/app/static/original
backend/app/static/result
```

建议确认：

```powershell
Test-Path F:\学校\病虫害识别\agri_uav_disease_system\backend\app\static
Test-Path F:\学校\病虫害识别\agri_uav_disease_system\backend\app\static\original
Test-Path F:\学校\病虫害识别\agri_uav_disease_system\backend\app\static\result
```

如果目录不存在：

```powershell
New-Item -ItemType Directory -Force -Path F:\学校\病虫害识别\agri_uav_disease_system\backend\app\static\original
New-Item -ItemType Directory -Force -Path F:\学校\病虫害识别\agri_uav_disease_system\backend\app\static\result
```

前端展示口径：

```text
存储目录不可写会影响上传图片和结果图生成，但不代表模型状态失败。
```

## 7. 中文编码说明

源码、Markdown、接口文档统一使用 UTF-8。

PowerShell 默认输出可能导致中文显示乱码。读取中文文件建议：

```powershell
$OutputEncoding = [Console]::OutputEncoding = [Text.UTF8Encoding]::new()
Get-Content -Encoding UTF8
```

不要仅凭 PowerShell 乱码判断文件损坏。

## 8. 推荐启动顺序

```text
1. 启动后端
2. 验证 /api/status
3. 启动前端
4. 验证 http://127.0.0.1:5173
5. 打开前端页面进行联调
```

## 9. 联调前检查清单

```text
[ ] 后端 /api/status 可访问
[ ] database_status 为 ok
[ ] 前端首页返回 200
[ ] 前端 VITE_API_BASE_URL 指向正确后端
[ ] 协同巡检页能访问 /api/fields
[ ] 图像检测页能调用 /api/detect/image
[ ] 如果 storage_status 为 error，已在页面中明确提示
```
