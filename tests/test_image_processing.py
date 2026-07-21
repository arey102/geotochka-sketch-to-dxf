import cv2
import numpy as np

from app.services.image_processing import detect_lines


def test_detects_lines_in_synthetic_sketch() -> None:
    image = np.full((400, 500, 3), 255, dtype=np.uint8)
    cv2.rectangle(image, (80, 90), (420, 310), (0, 0, 0), thickness=5)
    ok, encoded = cv2.imencode(".png", image)

    assert ok
    result = detect_lines(encoded.tobytes())

    assert result.image_width_px == 500
    assert result.image_height_px == 400
    assert len(result.lines) >= 4
    assert result.preview_image.startswith("data:image/jpeg;base64,")
    assert len({line.id for line in result.lines}) == len(result.lines)


def test_corrects_perspective_when_sheet_boundary_is_visible() -> None:
    image = np.full((700, 900, 3), 35, dtype=np.uint8)
    sheet = np.array([[140, 90], [790, 130], [740, 620], [90, 570]], dtype=np.int32)
    cv2.fillConvexPoly(image, sheet, (250, 250, 250))
    cv2.polylines(image, [sheet], True, (0, 0, 0), 8)
    cv2.line(image, (220, 220), (690, 250), (0, 0, 0), 7)
    ok, encoded = cv2.imencode(".png", image)

    assert ok
    result = detect_lines(encoded.tobytes())

    assert result.perspective_corrected
    assert result.lines
