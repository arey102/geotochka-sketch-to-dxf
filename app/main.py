import re
from io import BytesIO
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from app.models import DetectionResult, ExportRequest
from app.services.dxf_export import build_dxf
from app.services.image_processing import InvalidImageError, detect_lines

MAX_UPLOAD_BYTES = 20 * 1024 * 1024

app = FastAPI(
    title="GEOточка Sketch to DXF",
    version="1.0.0",
    description="Фото геодезического эскиза в проверяемую геометрию и DXF.",
)

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/v1/detect", response_model=DetectionResult)
async def detect(file: UploadFile = File(...)) -> DetectionResult:
    if file.content_type not in {"image/jpeg", "image/png"}:
        raise HTTPException(status_code=415, detail="Поддерживаются только JPEG и PNG")

    contents = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Максимальный размер файла — 20 МБ")

    try:
        return detect_lines(contents)
    except InvalidImageError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/v1/export/dxf")
def export_dxf(request: ExportRequest) -> StreamingResponse:
    if not request.lines:
        raise HTTPException(status_code=422, detail="Добавьте хотя бы один отрезок")

    safe_name = request.filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    safe_name = re.sub(r"[^a-zA-Z0-9._-]", "_", safe_name) or "drawing.dxf"
    if not safe_name.lower().endswith(".dxf"):
        safe_name += ".dxf"

    return StreamingResponse(
        BytesIO(build_dxf(request)),
        media_type="application/dxf",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
    )
