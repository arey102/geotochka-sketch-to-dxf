from io import StringIO

import ezdxf

from app.models import ExportRequest, LineSegment, Point
from app.services.dxf_export import build_dxf


def test_exports_scaled_line_and_flips_image_y_axis() -> None:
    request = ExportRequest(
        scale_mm_per_pixel=10,
        lines=[LineSegment(start=Point(x=2, y=3), end=Point(x=7, y=3))],
    )

    document = ezdxf.read(StringIO(build_dxf(request).decode("utf-8")))
    entities = list(document.modelspace().query("LINE"))

    assert len(entities) == 1
    assert tuple(entities[0].dxf.start) == (20.0, -30.0, 0.0)
    assert tuple(entities[0].dxf.end) == (70.0, -30.0, 0.0)
    assert entities[0].dxf.layer == "WALLS"

