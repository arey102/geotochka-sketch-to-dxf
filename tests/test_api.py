import cv2
import numpy as np
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _image_bytes() -> bytes:
    image = np.full((220, 300, 3), 255, dtype=np.uint8)
    cv2.rectangle(image, (40, 45), (260, 180), (0, 0, 0), 4)
    ok, encoded = cv2.imencode(".png", image)
    assert ok
    return encoded.tobytes()


def test_homepage_and_health_are_available() -> None:
    home = client.get("/")
    health = client.get("/health")

    assert home.status_code == 200
    assert "GEOточка" in home.text
    assert health.json() == {"status": "ok"}


def test_detect_endpoint_returns_editor_ready_geometry() -> None:
    response = client.post(
        "/api/v1/detect",
        files={"file": ("sketch.png", _image_bytes(), "image/png")},
    )

    assert response.status_code == 200
    result = response.json()
    assert result["lines"]
    assert result["lines"][0]["id"].startswith("line-")
    assert result["preview_image"].startswith("data:image/jpeg;base64,")


def test_detect_rejects_unsupported_file_type() -> None:
    response = client.post(
        "/api/v1/detect",
        files={"file": ("sketch.pdf", b"not a pdf", "application/pdf")},
    )

    assert response.status_code == 415


def test_export_sanitizes_download_filename() -> None:
    response = client.post(
        "/api/v1/export/dxf",
        json={
            "filename": "../my drawing.dxf",
            "lines": [{"start": {"x": 0, "y": 0}, "end": {"x": 10, "y": 0}}],
        },
    )

    assert response.status_code == 200
    assert response.headers["content-disposition"] == 'attachment; filename="my_drawing.dxf"'
