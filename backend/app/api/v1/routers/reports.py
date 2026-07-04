"""Reports endpoints — GET /reports/daily[/{date}] and admin force-generate."""

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.security import require_admin_key
from app.db.session import get_db
from app.models.daily_report import DailyReport
from app.schemas.report import DailyReportResponse
from app.workers.tasks.report_tasks import generate_daily_report

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/daily", response_model=DailyReportResponse)
async def get_latest_report(db: AsyncSession = Depends(get_db)) -> DailyReportResponse:
    """Return the most recent daily report."""
    result = await db.execute(
        select(DailyReport).order_by(DailyReport.report_date.desc()).limit(1)
    )
    report = result.scalar_one_or_none()
    if not report:
        raise NotFoundError("No daily reports generated yet")
    return DailyReportResponse.model_validate(report)


@router.get("/daily/{report_date}", response_model=DailyReportResponse)
async def get_report_by_date(
    report_date: date,
    db: AsyncSession = Depends(get_db),
) -> DailyReportResponse:
    """Return the report for a specific date (YYYY-MM-DD)."""
    result = await db.execute(
        select(DailyReport).where(DailyReport.report_date == report_date)
    )
    report = result.scalar_one_or_none()
    if not report:
        raise NotFoundError(f"No report found for {report_date}")
    return DailyReportResponse.model_validate(report)


@router.post(
    "/daily/generate",
    dependencies=[Depends(require_admin_key)],
)
async def force_generate_report(
    report_date: date | None = Query(None, description="Date to generate report for (default: yesterday)"),
) -> dict:
    """Admin: force-regenerate the daily report on demand."""
    task = generate_daily_report.apply_async(
        kwargs={"report_date": report_date.isoformat() if report_date else None},
        queue="reports",
    )
    return {"status": "enqueued", "task_id": task.id, "report_date": str(report_date) if report_date else "yesterday"}
