from __future__ import annotations

import base64
import hashlib
import math
from dataclasses import dataclass

import cv2
import numpy as np

from app.models import DetectionResult, LineSegment, Point


class InvalidImageError(ValueError):
    """Raised when uploaded bytes cannot be decoded as an image."""


@dataclass
class PreparedImage:
    color: np.ndarray
    gray: np.ndarray
    perspective_corrected: bool


def _order_corners(points: np.ndarray) -> np.ndarray:
    points = points.reshape(4, 2).astype(np.float32)
    ordered = np.zeros((4, 2), dtype=np.float32)
    sums = points.sum(axis=1)
    diffs = np.diff(points, axis=1).reshape(-1)
    ordered[0] = points[np.argmin(sums)]
    ordered[2] = points[np.argmax(sums)]
    ordered[1] = points[np.argmin(diffs)]
    ordered[3] = points[np.argmax(diffs)]
    return ordered


def _find_page(image: np.ndarray) -> np.ndarray | None:
    height, width = image.shape[:2]
    scale = min(1.0, 1200 / max(height, width))
    sample = cv2.resize(image, None, fx=scale, fy=scale) if scale < 1 else image.copy()
    gray = cv2.cvtColor(sample, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (7, 7), 0)
    edges = cv2.Canny(gray, 40, 120)
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    image_area = sample.shape[0] * sample.shape[1]
    for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:15]:
        if cv2.contourArea(contour) < image_area * 0.35:
            continue
        perimeter = cv2.arcLength(contour, True)
        polygon = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
        if len(polygon) == 4 and cv2.isContourConvex(polygon):
            mask = np.zeros(gray.shape, dtype=np.uint8)
            cv2.fillConvexPoly(mask, polygon.reshape(4, 2), 255)
            interior = gray[mask == 255]
            exterior = gray[mask == 0]
            # A sheet is normally visibly lighter than its surroundings. This
            # check prevents a large wall rectangle on white paper being
            # mistaken for the paper boundary.
            if exterior.size and float(np.median(interior)) > float(np.median(exterior)) + 12:
                return _order_corners(polygon / scale)
    return None


def _warp_page(image: np.ndarray, corners: np.ndarray) -> np.ndarray:
    top_left, top_right, bottom_right, bottom_left = corners
    width = int(
        max(np.linalg.norm(top_right - top_left), np.linalg.norm(bottom_right - bottom_left))
    )
    height = int(
        max(np.linalg.norm(bottom_left - top_left), np.linalg.norm(bottom_right - top_right))
    )
    width = max(width, 100)
    height = max(height, 100)
    destination = np.array(
        [[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]],
        dtype=np.float32,
    )
    matrix = cv2.getPerspectiveTransform(corners, destination)
    return cv2.warpPerspective(image, matrix, (width, height), borderValue=(255, 255, 255))


def _prepare_image(image: np.ndarray) -> PreparedImage:
    corners = _find_page(image)
    corrected = corners is not None
    if corners is not None:
        image = _warp_page(image, corners)

    height, width = image.shape[:2]
    resize_factor = min(1.0, 2200 / max(height, width))
    if resize_factor < 1.0:
        image = cv2.resize(image, None, fx=resize_factor, fy=resize_factor)

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    # Large blur estimates uneven illumination; division suppresses shadows on paper.
    background = cv2.GaussianBlur(gray, (0, 0), sigmaX=max(15, min(gray.shape) / 35))
    normalized = cv2.divide(gray, background, scale=255)
    normalized = cv2.createCLAHE(clipLimit=1.6, tileGridSize=(8, 8)).apply(normalized)
    return PreparedImage(color=image, gray=normalized, perspective_corrected=corrected)


def _length(line: np.ndarray) -> float:
    x1, y1, x2, y2 = (float(value) for value in line)
    return math.hypot(x2 - x1, y2 - y1)


def _canonical(line: np.ndarray) -> np.ndarray:
    x1, y1, x2, y2 = (float(value) for value in line)
    if (x1, y1) > (x2, y2):
        return np.array((x2, y2, x1, y1), dtype=np.float64)
    return np.array((x1, y1, x2, y2), dtype=np.float64)


def _snap_orientation(line: np.ndarray, angle_tolerance: float = 8.0) -> np.ndarray:
    x1, y1, x2, y2 = _canonical(line)
    angle = abs(math.degrees(math.atan2(y2 - y1, x2 - x1))) % 180
    if angle <= angle_tolerance or angle >= 180 - angle_tolerance:
        middle_y = (y1 + y2) / 2
        return np.array((x1, middle_y, x2, middle_y))
    if abs(angle - 90) <= angle_tolerance:
        middle_x = (x1 + x2) / 2
        return np.array((middle_x, y1, middle_x, y2))
    return np.array((x1, y1, x2, y2))


def _merge_axis_aligned(lines: list[np.ndarray], axis_tolerance: float = 10) -> list[np.ndarray]:
    horizontal: list[np.ndarray] = []
    vertical: list[np.ndarray] = []
    diagonal: list[np.ndarray] = []
    for line in lines:
        x1, y1, x2, y2 = line
        if abs(y2 - y1) < 0.01:
            horizontal.append(line)
        elif abs(x2 - x1) < 0.01:
            vertical.append(line)
        else:
            diagonal.append(line)

    def merge_group(items: list[np.ndarray], horizontal_mode: bool) -> list[np.ndarray]:
        if not items:
            return []
        # Collapse thick double edges and fragmented strokes onto a common wall axis.
        items = sorted(items, key=lambda value: value[1] if horizontal_mode else value[0])
        axis_groups: list[list[np.ndarray]] = []
        for item in items:
            axis = item[1] if horizontal_mode else item[0]
            if not axis_groups:
                axis_groups.append([item])
                continue
            group_axis = float(
                np.median([value[1] if horizontal_mode else value[0] for value in axis_groups[-1]])
            )
            if abs(axis - group_axis) <= axis_tolerance:
                axis_groups[-1].append(item)
            else:
                axis_groups.append([item])

        merged: list[np.ndarray] = []
        for group in axis_groups:
            axis = float(np.median([value[1] if horizontal_mode else value[0] for value in group]))
            intervals = sorted(
                ((value[0], value[2]) if horizontal_mode else (value[1], value[3]))
                for value in group
            )
            start, end = intervals[0]
            for next_start, next_end in intervals[1:]:
                if next_start <= end + 24:
                    end = max(end, next_end)
                else:
                    coordinates = (
                        (start, axis, end, axis)
                        if horizontal_mode
                        else (axis, start, axis, end)
                    )
                    merged.append(
                        np.array(coordinates)
                    )
                    start, end = next_start, next_end
            merged.append(
                np.array((start, axis, end, axis) if horizontal_mode else (axis, start, axis, end))
            )
        return merged

    # Diagonals are quantized to remove the duplicate edges returned by Hough.
    unique_diagonal: dict[tuple[int, int, int, int], np.ndarray] = {}
    for line in sorted(diagonal, key=_length, reverse=True):
        key = tuple(round(float(value) / 12) for value in line)
        unique_diagonal.setdefault(key, line)
    return (
        merge_group(horizontal, True)
        + merge_group(vertical, False)
        + list(unique_diagonal.values())
    )


def _encode_preview(image: np.ndarray) -> str:
    ok, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 88])
    if not ok:
        return ""
    payload = base64.b64encode(encoded.tobytes()).decode("ascii")
    return f"data:image/jpeg;base64,{payload}"


def _stable_id(line: np.ndarray) -> str:
    coordinates = ":".join(str(round(float(value), 1)) for value in line)
    return "line-" + hashlib.sha1(coordinates.encode(), usedforsecurity=False).hexdigest()[:12]


def detect_lines(image_bytes: bytes, max_lines: int = 300) -> DetectionResult:
    encoded = np.frombuffer(image_bytes, dtype=np.uint8)
    decoded = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
    if decoded is None:
        raise InvalidImageError("Файл не удалось прочитать как JPEG или PNG")

    prepared = _prepare_image(decoded)
    height, width = prepared.gray.shape
    blurred = cv2.GaussianBlur(prepared.gray, (3, 3), 0)
    edges = cv2.Canny(blurred, 45, 135, apertureSize=3)
    minimum_length = max(35, round(min(height, width) * 0.045))
    detected = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 360,
        threshold=42,
        minLineLength=minimum_length,
        maxLineGap=max(14, round(min(height, width) * 0.018)),
    )

    raw_lines = [] if detected is None else list(detected.reshape(-1, 4))
    snapped = [_snap_orientation(line) for line in raw_lines]
    merged = sorted(_merge_axis_aligned(snapped), key=_length, reverse=True)[:max_lines]
    diagonal = math.hypot(width, height)
    lines = [
        LineSegment(
            id=_stable_id(line),
            start=Point(x=round(float(line[0]), 2), y=round(float(line[1]), 2)),
            end=Point(x=round(float(line[2]), 2), y=round(float(line[3]), 2)),
            confidence=round(min(0.99, 0.48 + _length(line) / diagonal), 3),
        )
        for line in merged
        if _length(line) >= minimum_length
    ]

    warnings = [
        "Проверьте найденные линии и удалите размерные/текстовые штрихи перед экспортом.",
        "Для точного масштаба выберите линию с известной длиной и выполните калибровку.",
    ]
    if not lines:
        warnings.append("Прямые линии не найдены: снимите лист без теней и бликов.")

    return DetectionResult(
        image_width_px=width,
        image_height_px=height,
        preview_image=_encode_preview(prepared.color),
        perspective_corrected=prepared.perspective_corrected,
        lines=lines,
        warnings=warnings,
    )
