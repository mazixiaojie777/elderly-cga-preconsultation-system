# -*- coding: utf-8 -*-
"""
老年智能预问诊系统 - FastAPI 后端入口

遵循 AGENT.md v1.2 技术栈约束：
    - Python 3.11+
    - FastAPI 异步接口
    - pydantic v2 校验输入输出
    - PostgreSQL + Redis（后续接入，当前使用内存存储）

当前版本实现（v0.2.0）：
    - GET  /health                      健康检查
    - POST /api/session/start           启动预问诊会话（AGENT.md 8.1 契约）
    - POST /api/session/verify-token    扫码令牌核验（医院蓝多设备适配新增）

医院蓝多设备适配集成说明：
    - 前端 patient-verify.html 通过 API_BASE 调用本服务
    - 扫码令牌核验接口支持自助机扫码进入流程
    - 所有接口返回统一错误结构，便于前端降级提示
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

# ============================================================
# 日志配置（遵循 AGENT.md 错误处理规范）
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("preconsult-backend")


# ============================================================
# 运行时配置（环境变量驱动）
# ============================================================

class AppConfig:
    """集中管理运行时配置

    支持通过环境变量覆盖，方便对接医院蓝多设备适配前端的不同端口。
    """

    # 后端监听端口（默认 8766，与前端 patient-verify.html 的 API_BASE 对齐）
    APP_PORT: int = int(os.getenv("APP_PORT", "8766"))

    # 允许的 CORS 来源（开发期含前端 dev server 端口 3000 / 3014）
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3014",
        "http://127.0.0.1:3014",
        # 静态 HTML 通过 file:// 或本地 HTTP 打开时也需要放行
        "null",
    ]

    # 会话有效期（小时），遵循 AGENT.md 2.2
    SESSION_TTL_HOURS: int = int(os.getenv("SESSION_TTL_HOURS", "72"))

    # 扫码令牌有效期（分钟），令牌一次性使用
    SCAN_TOKEN_TTL_MINUTES: int = int(os.getenv("SCAN_TOKEN_TTL_MINUTES", "10"))


config = AppConfig()


# ============================================================
# 领域枚举（遵循 AGENT.md 8.1 契约）
# ============================================================

class Department(str, Enum):
    """就诊科室枚举

    AGENT.md 8.1 明确限定启动会话时可选的科室范围：
        - 老年医学科
        - 全科医学科
        - 康复科
    """

    GERIATRICS = "老年医学科"
    GENERAL_PRACTICE = "全科医学科"
    REHABILITATION = "康复科"


class SessionStatus(str, Enum):
    """会话状态（遵循 AGENT.md 2.2 生命周期）"""

    ACTIVE = "active"          # 进行中
    PAUSED = "paused"          # 暂停（断点续填等待中）
    COMPLETED = "completed"    # 已完成
    EXPIRED = "expired"        # 超过 72 小时未续填
    CANCELLED = "cancelled"    # 用户主动取消


# ============================================================
# 请求 / 响应模型（pydantic v2）
# ============================================================

class HealthResponse(BaseModel):
    """健康检查响应"""

    status: str = "ok"
    timestamp: str


class SessionStartRequest(BaseModel):
    """会话启动请求（严格遵循 AGENT.md 8.1 契约）

    字段说明（一字不差对齐文档）：
        | 字段            | 类型     | 必填 | 约束                              |
        |----------------|----------|------|-----------------------------------|
        | patient_id     | string   | 是   | UUID 格式                         |
        | department     | enum     | 是   | 限"老年医学科""全科医学科""康复科" |
        | consent_given  | boolean  | 是   | 患者知情同意标记                   |
        | callback_url   | string   | 否   | 结果推送地址                       |
    """

    model_config = ConfigDict(extra="forbid")  # 禁止多余字段，严格契约

    patient_id: str = Field(
        ...,
        description="患者唯一标识（UUID 格式）",
        min_length=1,
    )
    department: Department = Field(
        ...,
        description="就诊科室，限老年医学科/全科医学科/康复科",
    )
    consent_given: bool = Field(
        ...,
        description="患者是否已签署知情同意书",
    )
    callback_url: Optional[str] = Field(
        default=None,
        description="评估完成后的结果回调地址（可选）",
    )


class SessionStartResponse(BaseModel):
    """会话启动响应

    返回字段：
        - session_id：后端生成的会话唯一标识（UUID）
        - patient_id：原样回传
        - department：原样回传
        - consent_given：原样回传
        - callback_url：原样回传（可为空）
        - status：初始状态 active
        - started_at：启动时间（ISO 8601 + UTC）
        - expires_at：过期时间（启动时间 + 72 小时，遵循 AGENT.md 2.2）
    """

    model_config = ConfigDict(extra="forbid")

    session_id: str
    patient_id: str
    department: str
    consent_given: bool
    callback_url: Optional[str] = None
    status: str = "active"
    started_at: str
    expires_at: str


class ScanTokenVerifyRequest(BaseModel):
    """扫码令牌核验请求（医院蓝多设备适配新增）

    患者在自助机扫码后，将二维码中的一次性令牌提交核验。
    令牌由护士端生成，只能使用一次，过期后需重新生成。
    """

    model_config = ConfigDict(extra="forbid")

    token: str = Field(
        ...,
        description="院内一次性扫码令牌",
        min_length=24,
        max_length=128,
    )


class ScanTokenVerifyResponse(BaseModel):
    """扫码令牌核验响应"""

    model_config = ConfigDict(extra="forbid")

    valid: bool
    session_id: Optional[str] = None
    patient_id: Optional[str] = None
    message: str


class SessionQueryResponse(BaseModel):
    """会话查询响应（feature/session-query-endpoint 新增）

    根据 session_id 查询会话详情，用于前端轮询会话状态、
    医生端查看患者会话进度等场景。
    """

    model_config = ConfigDict(extra="forbid")

    session_id: str
    patient_id: str
    department: str
    consent_given: bool
    callback_url: Optional[str] = None
    status: str
    started_at: str
    expires_at: str
    is_expired: bool = Field(
        default=False,
        description="会话是否已过期（当前时间 > expires_at）",
    )


# ============================================================
# 内存会话存储（生产环境由 Redis 接管）
# ============================================================

# 结构：session_id -> {patient_id, department, consent_given, callback_url,
#                      status, started_at, expires_at}
_SESSION_STORE: dict[str, dict] = {}

# 扫码令牌存储：token -> {patient_id, session_id, expires_at, used}
# 令牌一次性使用，过期后自动失效
_SCAN_TOKEN_STORE: dict[str, dict] = {}


# ============================================================
# FastAPI 应用实例
# ============================================================

app = FastAPI(
    title="老年智能预问诊系统 - 后端服务",
    description=(
        "基于 FastAPI 的预问诊与 CGA 报告后端。"
        "遵循 AGENT.md v1.2 契约规范，集成医院蓝多设备适配前端。"
    ),
    version="0.2.0",
    docs_url=None,   # 禁用默认 Swagger UI（改用本地资源，见下方自定义路由）
    redoc_url=None,  # 禁用默认 ReDoc
)

# 挂载本地静态资源目录（Swagger UI / ReDoc 离线托管）
# 使用绝对路径，确保从任意工作目录启动都能找到 static 目录
_STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    """自定义 Swagger UI 页面（引用本地 JS/CSS，避免 CDN 不可达）"""
    return HTMLResponse(
        f"""
<!DOCTYPE html>
<html>
<head>
    <link type="text/css" rel="stylesheet" href="/static/swagger-ui.css">
    <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>📋</text></svg>">
    <title>{app.title} - Swagger UI</title>
</head>
<body>
<div id="swagger-ui"></div>
<script src="/static/swagger-ui-bundle.js"></script>
<script src="/static/swagger-ui-standalone-preset.js"></script>
<script>
    const ui = SwaggerUIBundle({{
        url: "{app.openapi_url}",
        dom_id: '#swagger-ui',
        deepLinking: true,
        presets: [SwaggerUIBundle.presets.apis, SwaggerUIStandalonePreset],
        layout: "BaseLayout",
        defaultModelsExpandDepth: 1,
    }});
    window.ui = ui;
</script>
</body>
</html>
"""
    )


@app.get("/redoc", include_in_schema=False)
async def custom_redoc_html():
    """自定义 ReDoc 页面（引用本地 JS，避免 CDN 不可达）"""
    return HTMLResponse(
        f"""
<!DOCTYPE html>
<html>
<head>
    <title>{app.title} - ReDoc</title>
    <meta charset="utf-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>📖</text></svg>">
</head>
<body>
<redoc spec-url="{app.openapi_url}"></redoc>
<script src="/static/redoc.standalone.js"> </script>
</body>
</html>
"""
    )

# CORS 配置（开发期允许本地前端携带凭据）
# 医院蓝多设备适配前端 dev server 默认端口为 3014（见测试交接说明）
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# 全局异常处理器（对应 AGENT.md 错误处理规范）
# ============================================================

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """全局未捕获异常处理

    按照 AGENT.md 3.3 节错误处理规范：
        - 返回统一 JSON 结构
        - 记录日志（不向客户端暴露内部堆栈）
        - 前端可根据 status 字段做降级提示
    """
    logger.exception("未捕获异常: path=%s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "message": "服务器内部错误",
            "path": str(request.url.path),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """HTTP 异常统一处理，保证前端错误提示格式一致"""
    logger.warning(
        "HTTP %s: path=%s detail=%s",
        exc.status_code,
        request.url.path,
        exc.detail,
    )
    detail = exc.detail
    if isinstance(detail, dict):
        message = detail.get("message", str(detail))
        code = detail.get("code")
    else:
        message = str(detail)
        code = None

    body = {
        "status": "error",
        "message": message,
        "path": str(request.url.path),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if code:
        body["code"] = code
    return JSONResponse(status_code=exc.status_code, content=body)


# ============================================================
# 健康检查接口
# ============================================================

@app.get(
    "/health",
    tags=["system"],
    response_model=HealthResponse,
    summary="健康检查",
    description="服务存活探针。返回当前时间戳，供 Docker/K8s liveness/readiness 探针使用。",
)
async def health_check() -> HealthResponse:
    """健康检查接口

    Returns:
        HealthResponse: {"status": "ok", "timestamp": "ISO 8601 格式时间"}

    约束（AGENT.md 7 章 / 8 章）：
        - GET /health
        - 返回 JSON 格式
        - timestamp 使用 ISO 8601 + UTC 时区
    """
    return HealthResponse(
        status="ok",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


# ============================================================
# 会话启动接口（AGENT.md 8.1 领域契约）
# ============================================================

@app.post(
    "/api/session/start",
    tags=["session"],
    response_model=SessionStartResponse,
    summary="启动预问诊会话",
    description=(
        "创建一个新的老年综合评估（CGA）预问诊会话。"
        "患者必须先签署知情同意书（consent_given=true）才能启动。"
        "会话有效期 72 小时，超时未续填自动归档。"
    ),
    status_code=201,
)
async def start_session(req: SessionStartRequest) -> SessionStartResponse:
    """启动预问诊会话

    实现要点（对齐 AGENT.md 8.1 / 2.2）：
        1. consent_given 为 false 时拒绝启动（HTTP 400）
        2. 生成 UUID session_id 写入内存存储
        3. 设置 72 小时过期时间
        4. 返回完整会话上下文

    Args:
        req: 启动请求（patient_id / department / consent_given / callback_url）

    Returns:
        SessionStartResponse: 包含 session_id 与会话元信息

    Raises:
        HTTPException 400: 未签署知情同意书
    """
    # 前置校验：知情同意必须为 true（AGENT.md 2.1 会话生命周期要求）
    if not req.consent_given:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "CONSENT_REQUIRED",
                "message": "患者知情同意书未签署，无法启动预问诊会话",
                "hint": "请先完成知情同意流程后再调用本接口",
            },
        )

    # 生成会话唯一标识（UUID v4）
    session_id = str(uuid.uuid4())

    # 计算时间戳（ISO 8601 + UTC）
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=config.SESSION_TTL_HOURS)

    # 写入会话存储（内存字典；生产环境替换为 Redis SETEX）
    session_record = {
        "session_id": session_id,
        "patient_id": req.patient_id,
        "department": req.department.value,
        "consent_given": req.consent_given,
        "callback_url": req.callback_url,
        "status": SessionStatus.ACTIVE.value,
        "started_at": now.isoformat(),
        "expires_at": expires_at.isoformat(),
    }
    _SESSION_STORE[session_id] = session_record

    logger.info(
        "会话已创建: session_id=%s patient_id=%s department=%s",
        session_id,
        req.patient_id,
        req.department.value,
    )

    return SessionStartResponse(**session_record)


# ============================================================
# 会话查询接口（feature/session-query-endpoint 新增）
# ============================================================

@app.get(
    "/api/session/{session_id}",
    tags=["session"],
    response_model=SessionQueryResponse,
    summary="查询会话详情",
    description=(
        "根据 session_id 查询预问诊会话的完整信息。"
        "用于前端轮询会话状态、医生端查看患者会话进度。"
        "若会话不存在返回 404，若已过期则 is_expired=true。"
    ),
    status_code=200,
)
async def get_session(session_id: str) -> SessionQueryResponse:
    """查询会话详情

    实现要点：
        1. 根据 session_id 从内存存储中查找会话
        2. 不存在时返回 404 SESSION_NOT_FOUND
        3. 计算 is_expired 字段（当前时间 > expires_at）
        4. 过期会话仍可查询，但 is_expired=true 供前端判断

    Args:
        session_id: 会话唯一标识（UUID 格式）

    Returns:
        SessionQueryResponse: 会话完整信息

    Raises:
        HTTPException 404: 会话不存在
    """
    session = _SESSION_STORE.get(session_id)
    if session is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "SESSION_NOT_FOUND",
                "message": f"会话 {session_id} 不存在",
                "hint": "请检查 session_id 是否正确，或会话已被清理",
            },
        )

    # 计算是否过期
    now = datetime.now(timezone.utc)
    expires_at = datetime.fromisoformat(session["expires_at"])
    is_expired = now > expires_at

    logger.info(
        "查询会话: session_id=%s is_expired=%s",
        session_id,
        is_expired,
    )

    return SessionQueryResponse(
        session_id=session["session_id"],
        patient_id=session["patient_id"],
        department=session["department"],
        consent_given=session["consent_given"],
        callback_url=session.get("callback_url"),
        status=session["status"],
        started_at=session["started_at"],
        expires_at=session["expires_at"],
        is_expired=is_expired,
    )


# ============================================================
# 扫码令牌核验接口（医院蓝多设备适配新增）
# ============================================================

@app.post(
    "/api/session/verify-token",
    tags=["session"],
    response_model=ScanTokenVerifyResponse,
    summary="扫码令牌核验",
    description=(
        "患者在自助机扫码后提交一次性令牌进行核验。"
        "令牌由护士端生成，只能使用一次，过期后需重新生成。"
        "核验成功后返回关联的会话 ID。"
    ),
    status_code=200,
)
async def verify_scan_token(req: ScanTokenVerifyRequest) -> ScanTokenVerifyResponse:
    """扫码令牌核验

    对接医院蓝多设备适配前端 patient-verify.html 的「使用扫码令牌」功能。

    校验规则：
        1. 令牌必须存在于存储中
        2. 令牌未过期（默认 10 分钟）
        3. 令牌未被使用过（一次性）

    Args:
        req: 包含 token 字段的核验请求

    Returns:
        ScanTokenVerifyResponse: 核验结果，成功时返回 session_id 和 patient_id
    """
    token = req.token.strip()

    record = _SCAN_TOKEN_STORE.get(token)
    if record is None:
        logger.warning("扫码令牌不存在: token=%s", token[:8] + "***")
        return ScanTokenVerifyResponse(
            valid=False,
            message="令牌不存在或无效，请联系护士重新生成",
        )

    # 检查是否已使用
    if record.get("used"):
        logger.warning("扫码令牌已被使用: token=%s", token[:8] + "***")
        return ScanTokenVerifyResponse(
            valid=False,
            message="该令牌已被使用，请联系护士重新生成",
        )

    # 检查是否过期
    now = datetime.now(timezone.utc)
    expires_at = datetime.fromisoformat(record["expires_at"])
    if now > expires_at:
        logger.warning("扫码令牌已过期: token=%s", token[:8] + "***")
        return ScanTokenVerifyResponse(
            valid=False,
            message="令牌已过期，请联系护士重新生成",
        )

    # 标记为已使用（一次性）
    record["used"] = True
    _SCAN_TOKEN_STORE[token] = record

    logger.info(
        "扫码令牌核验成功: token=%s session_id=%s",
        token[:8] + "***",
        record["session_id"],
    )

    return ScanTokenVerifyResponse(
        valid=True,
        session_id=record["session_id"],
        patient_id=record["patient_id"],
        message="核验成功",
    )


# ============================================================
# 直接启动入口（py main.py）
# ============================================================

if __name__ == "__main__":
    import uvicorn

    # 端口通过环境变量 APP_PORT 配置，默认 8766（与前端 API_BASE 对齐）
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=config.APP_PORT,
        reload=True,
    )
