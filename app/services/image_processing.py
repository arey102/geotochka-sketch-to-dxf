from __future__ import annotations

import math

import cv2
import numpy as np

from app.models import DetectionResult, LineSegment, Point


class InvalidImageError(ValueError):
    """Raised when uploaded bytes cannot be decoded as an image."""


def _line_length(raw: np.ndarray) -> float:
    x1, y1, x2, y2 = (float(value) for value in raw)
    return math.hypot(x2 - x1, y2 - y1)


def _canonical(raw: np.ndarray) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = (int(value) for value in raw)
    if (x1, y1) > (x2, y2):
        return x2, y2, x1, y1
    return x1, y1, x2, y2


def _deduplicate(lines: list[np.ndarray], tolerance_px: int = 12) -> list[np.ndarray]:
    """Collapse nearly identical Hough segments using a stable quantized key."""
    selected: dict[tuple[int, int, int, int], np.ndarray] = {}
    for line in sorted(lines, key=_line_length, reverse=True):
        x1, y1, x2, y2 = _canonical(line)
        key = tuple(round(value / tolerance_px) for value in (x1, y1, x2, y2))
        selected.setdefault(key, np.array((x1, y1, x2, y2)))
    return list(selected.values())


def detect_lines(image_bytes: bytes, max_lines: int = 250) -> DetectionResult:
    encoded = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
    if image is None:
        raise InvalidImageError("Файл не удалось прочитать как JPEG или PNG")

    height, width = image.shape[:2]
    max_side = max(height, width)
    resize_factor = min(1.0, 2200 / max_side)
    if resize_factor < 1.0:
        image = cv2.resize(image, None, fx=resize_factor, fy=resize_factor)

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)

    processed_height, processed_width = edges.shape
    min_length = max(30, round(min(processed_height, processed_width) * 0.04))
    detected = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 180,
        threshold=45,
        minLineLength=min_length,
        maxLineGap=18,
    )

    raw_lines = [] if detected is None else list(detected.reshape(-1, 4))
    raw_lines = _deduplicate(raw_lines)[:max_lines]
    inverse_scale = 1.0 / resize_factor
    diagonal = math.hypot(processed_width, processed_height)

    lines = []
    for raw in raw_lines:
        x1, y1, x2, y2 = _canonical(raw)
        confidence = min(0.99, 0.45 + _line_length(raw) / diagonal)
        lines.append(
            LineSegment(
                start=Point(x=x1 * inverse_scale, y=y1 * inverse_scale),
                end=Point(x=x2 * inverse_scale, y=y2 * inverse_scale),
                confidence=round(confidence, 3),
            )
        )

    warnings = [
        "Автоматический результат необходимо проверить перед использованием в AutoCAD.",
        "Масштаб и единицы не определяются без подтверждённого размера.",
    ]
    if not lines:
        warnings.append("Прямые линии не найдены: попробуйте фото без теней и под прямым углом.")

    return DetectionResult(
        image_width_px=width,
        image_height_px=height,
        lines=lines,
        warnings=warnings,
    )
