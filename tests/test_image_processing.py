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

