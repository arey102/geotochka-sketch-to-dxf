from __future__ import annotations

from io import StringIO

import ezdxf

from app.models import DrawingUnits, ExportRequest

DXF_UNIT_CODES = {
    DrawingUnits.MILLIMETERS: 4,
    DrawingUnits.CENTIMETERS: 5,
    DrawingUnits.METERS: 6,
}

LAYER_BY_KIND = {
    "wall": "WALLS",
    "opening": "OPENINGS",
    "dimension": "DIMENSIONS",
    "reference": "REFERENCE",
}


def _coordinate_scale(request: ExportRequest) -> float:
    millimeters_per_unit = {
        DrawingUnits.MILLIMETERS: 1.0,
        DrawingUnits.CENTIMETERS: 10.0,
        DrawingUnits.METERS: 1000.0,
    }[request.units]
    return request.scale_mm_per_pixel / millimeters_per_unit


def build_dxf(request: ExportRequest) -> bytes:
    document = ezdxf.new("R2010", setup=True)
    document.units = DXF_UNIT_CODES[request.units]
    document.layers.add("WALLS", color=7)
    document.layers.add("OPENINGS", color=1)
    document.layers.add("DIMENSIONS", color=3)
    document.layers.add("REFERENCE", color=8)

    modelspace = document.modelspace()
    scale = _coordinate_scale(request)
    for line in request.lines:
        start = (line.start.x * scale, -line.start.y * scale)
        end = (line.end.x * scale, -line.end.y * scale)
        modelspace.add_line(start, end, dxfattribs={"layer": LAYER_BY_KIND[line.kind]})

    stream = StringIO()
    document.write(stream)
    return stream.getvalue().encode("utf-8")
