import json
from datetime import UTC, datetime

from fastapi import APIRouter, Response

from app.services.export_service import export_service

router = APIRouter()


@router.get("")
def export_data() -> Response:
    payload = export_service.export_all()
    filename = f"komorebi-backup-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}.json"
    body = json.dumps(payload, ensure_ascii=False, default=str, indent=2)
    return Response(
        content=body,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
