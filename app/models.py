from enum import StrEnum

from pydantic import BaseModel, Field


class DrawingUnits(StrEnum):
    MILLIMETERS = "mm"
    CENTIMETERS = "cm"
    METERS = "m"


class Point(BaseModel):
    x: float
    y: float


class LineSegment(BaseModel):
    start: Point
    end: Point
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    source: str = "detected"


class DetectionResult(BaseModel):
    image_width_px: int
    image_height_px: int
    lines: list[LineSegment]
    warnings: list[str] = Field(default_factory=list)


class ExportRequest(BaseModel):
    lines: list[LineSegment]
    units: DrawingUnits = DrawingUnits.MILLIMETERS
    scale_mm_per_pixel: float = Field(default=1.0, gt=0.0)
    filename: str = "drawing.dxf"

