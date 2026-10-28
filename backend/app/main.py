"""Sukkar Plus API — FastAPI application factory.

An independent concept prototype. Not affiliated with Sehhaty, the Ministry
of Health, or any device manufacturer or healthcare provider. No diagnosis,
no emergency triage, no dose or treatment advice. Review requests are
simulated and never reach a real clinician.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api import (
    appointments,
    followups,
    home,
    meta,
    notifications,
    profile,
    reports,
    reviewer,
    visit_prep,
    wellness,
)
from .config import get_settings

logging.basicConfig(
    level=logging.INFO,
    # Never log request bodies, file contents or metric values.
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

DESCRIPTION = """
واجهة برمجية لنموذج سكر بلس الأولي.

* قراءة تقارير الحساس المطبوعة (PDF) بالتحليل النصي الحتمي.
* فحوص اتساق وقواعد موثّقة المصدر، وأربع نتائج فقط.
* ملخص استعداد للموعد وطلب مراجعة تجريبي.

هذا نموذج أولي مستقل غير مرتبط بتطبيق صحتي أو بأي جهة صحية.
"""


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Sukkar Plus API",
        description=DESCRIPTION,
        version=meta.VERSION,
        docs_url="/docs",
        openapi_url="/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

    api_prefix = "/api/v1"
    app.include_router(meta.router, prefix=api_prefix)
    app.include_router(profile.router, prefix=api_prefix)
    app.include_router(home.router, prefix=api_prefix)
    app.include_router(reports.router, prefix=api_prefix)
    app.include_router(visit_prep.router, prefix=api_prefix)
    app.include_router(followups.router, prefix=api_prefix)
    app.include_router(reviewer.router, prefix=api_prefix)
    app.include_router(appointments.router, prefix=api_prefix)
    app.include_router(notifications.router, prefix=api_prefix)
    app.include_router(wellness.router, prefix=api_prefix)

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception) -> JSONResponse:  # pragma: no cover
        logging.getLogger("sukkar").exception("unhandled error on %s", request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": {"code": "internal_error",
                                "message_ar": "حدث خطأ غير متوقع. حاول مرة أخرى."}},
        )

    @app.get("/", include_in_schema=False)
    def root() -> dict:
        return {"service": "sukkar-plus-api", "docs": "/docs", "health": f"{api_prefix}/health"}

    return app


app = create_app()
