from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class DrawingUnits(StrEnum):
    MILLIMETERS = "mm"
    CENTIMETERS = "cm"
    METERS = "m"


class Point(BaseModel):
    x: float
    y: float


class LineSegment(BaseModel):
    id: str | None = None
    start: Point
    end: Point
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    source: str = "detected"
    kind: Literal["wall", "opening", "dimension", "reference"] = "wall"
    reviewed: bool = False


class DetectionResult(BaseModel):
    image_width_px: int
    image_height_px: int
    lines: list[LineSegment]
    preview_image: str | None = None
    perspective_corrected: bool = False
    warnings: list[str] = Field(default_factory=list)


class ExportRequest(BaseModel):
    lines: list[LineSegment]
    units: DrawingUnits = DrawingUnits.MILLIMETERS
    scale_mm_per_pixel: float = Field(default=1.0, gt=0.0)
    filename: str = "drawing.dxf"
