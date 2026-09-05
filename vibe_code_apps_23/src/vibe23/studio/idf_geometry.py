"""Parse EnergyPlus IDF surfaces into Plotly 3D massing.

Vendored from vibe20 ``wattlab.studio.idf_geometry`` with the temperature
colormap inlined so vibe23 has no wattlab dependency.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_M_TO_FT = 3.280839895

_OBJECT_RE = re.compile(
    r"(?ms)^[ \t]*(BuildingSurface:Detailed|FenestrationSurface:Detailed)[ \t]*,[ \t]*\r?\n"
    r"(.*?);[^\r\n]*(?:\r?\n|$)"
)


@dataclass
class IdfSurface:
    name: str
    surface_type: str  # WALL, ROOF, FLOOR, CEILING, Window, …
    zone_name: str
    object_type: str  # BuildingSurface:Detailed | FenestrationSurface:Detailed
    vertices: list[tuple[float, float, float]] = field(default_factory=list)

    @property
    def is_fenestration(self) -> bool:
        return "Fenestration" in self.object_type or self.surface_type.lower() in {
            "window",
            "glassdoor",
            "door",
        }


@dataclass
class IdfGeometry:
    surfaces: list[IdfSurface]
    source: str | None = None

    @property
    def zone_names(self) -> list[str]:
        return sorted({s.zone_name for s in self.surfaces if s.zone_name})

    def bbox_m(self) -> tuple[float, float, float, float, float, float] | None:
        pts = [v for s in self.surfaces for v in s.vertices]
        if not pts:
            return None
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        zs = [p[2] for p in pts]
        return min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)

    def summary(self) -> dict[str, Any]:
        bb = self.bbox_m()
        out: dict[str, Any] = {
            "n_surfaces": len(self.surfaces),
            "n_zones": len(self.zone_names),
            "zones": self.zone_names,
            "source": self.source,
            "n_fenestration": sum(1 for s in self.surfaces if s.is_fenestration),
        }
        if bb:
            xmin, xmax, ymin, ymax, zmin, zmax = bb
            out["bbox_m"] = {
                "dx": round(xmax - xmin, 3),
                "dy": round(ymax - ymin, 3),
                "dz": round(zmax - zmin, 3),
            }
            out["bbox_ft"] = {
                "dx": round((xmax - xmin) * _M_TO_FT, 1),
                "dy": round((ymax - ymin) * _M_TO_FT, 1),
                "dz": round((zmax - zmin) * _M_TO_FT, 1),
            }
        out.update(self.envelope_ratios())
        return out

    def envelope_ratios(self) -> dict[str, Any]:
        """Gross wall / window areas (m²) and WWR from parsed surfaces."""
        wall_m2 = 0.0
        fen_m2 = 0.0
        roof_m2 = 0.0
        for s in self.surfaces:
            area = _polygon_area_m2(s.vertices)
            stype = (s.surface_type or "").strip().upper()
            if s.is_fenestration:
                fen_m2 += area
            elif stype in {"WALL"} or stype.startswith("WALL"):
                wall_m2 += area
            elif stype in {"ROOF", "CEILING"}:
                roof_m2 += area
            elif "WALL" in stype:
                wall_m2 += area
        wwr = (fen_m2 / wall_m2) if wall_m2 > 1e-6 else None
        return {
            "wall_area_m2": round(wall_m2, 2),
            "window_area_m2": round(fen_m2, 2),
            "roof_area_m2": round(roof_m2, 2),
            "wwr": round(wwr, 3) if wwr is not None else None,
            "wwr_pct": round(100.0 * wwr, 1) if wwr is not None else None,
        }


def _polygon_area_m2(verts: list[tuple[float, float, float]]) -> float:
    """3D polygon area via Newell's method (m²)."""
    if len(verts) < 3:
        return 0.0
    nx = ny = nz = 0.0
    n = len(verts)
    for i in range(n):
        x1, y1, z1 = verts[i]
        x2, y2, z2 = verts[(i + 1) % n]
        nx += (y1 - y2) * (z1 + z2)
        ny += (z1 - z2) * (x1 + x2)
        nz += (x1 - x2) * (y1 + y2)
    return 0.5 * (nx * nx + ny * ny + nz * nz) ** 0.5


def _parse_block(object_type: str, body: str) -> IdfSurface | None:
    """Parse one surface object body (fields after the type line)."""
    # Split on commas that separate fields; vertices often pack X,Y,Z on one line
    lines = []
    for line in body.splitlines():
        cleaned = line.split("!-")[0].split("!")[0].strip()
        if cleaned:
            lines.append(cleaned)
    text = " ".join(lines)
    # Field tokens: split by comma, strip
    tokens: list[str] = []
    for chunk in text.split(","):
        t = chunk.strip().rstrip(";").strip()
        if t:
            tokens.append(t)
    if len(tokens) < 5:
        return None
    name = tokens[0]
    surface_type = tokens[1]
    # Construction = tokens[2]; Zone Name = tokens[3] for both object types
    # (Fenestration: Building Surface Name is field 4; still zone is on BuildingSurface)
    zone_name = tokens[3] if object_type.startswith("BuildingSurface") else ""
    if object_type.startswith("Fenestration"):
        # FenestrationSurface:Detailed: Name, Type, Construction, Building Surface Name, …
        # Zone comes from parent — leave empty; filled later or use surface name heuristics
        zone_name = ""
        building_surface = tokens[3] if len(tokens) > 3 else ""
    else:
        building_surface = ""

    # Find "Number of Vertices" — scan for first integer >= 3 followed by 3*N floats
    n_vert = None
    vert_start = None
    for i, tok in enumerate(tokens):
        try:
            n = int(float(tok))
        except ValueError:
            continue
        if 3 <= n <= 120:
            # Peek: next 3 values look numeric?
            if i + 3 < len(tokens):
                try:
                    float(tokens[i + 1])
                    float(tokens[i + 2])
                    float(tokens[i + 3])
                    n_vert = n
                    vert_start = i + 1
                    break
                except ValueError:
                    continue
    vertices: list[tuple[float, float, float]] = []
    if n_vert is not None and vert_start is not None:
        nums: list[float] = []
        for tok in tokens[vert_start:]:
            try:
                nums.append(float(tok))
            except ValueError:
                break
        for i in range(0, min(len(nums) // 3, n_vert) * 3, 3):
            vertices.append((nums[i], nums[i + 1], nums[i + 2]))

    if len(vertices) < 3:
        return None

    surf = IdfSurface(
        name=name,
        surface_type=surface_type,
        zone_name=zone_name or building_surface,
        object_type=object_type,
        vertices=vertices,
    )
    return surf


def parse_idf_geometry(text_or_path: str | Path) -> IdfGeometry:
    """Parse IDF text or path into surfaces."""
    source: str | None = None
    if isinstance(text_or_path, Path):
        path = text_or_path
        text = path.read_text(encoding="utf-8", errors="replace")
        source = str(path)
    elif (
        isinstance(text_or_path, str)
        and "\n" not in text_or_path
        and len(text_or_path) < 400
    ):
        path = Path(text_or_path)
        try:
            is_file = path.is_file()
        except OSError:
            is_file = False
        if is_file:
            text = path.read_text(encoding="utf-8", errors="replace")
            source = str(path)
        else:
            text = text_or_path
    else:
        text = str(text_or_path)

    surfaces: list[IdfSurface] = []
    # Map fenestration → zone via building surface name
    by_name: dict[str, IdfSurface] = {}
    for m in _OBJECT_RE.finditer(text):
        obj_type = m.group(1)
        body = m.group(2)
        surf = _parse_block(obj_type, body + ";")
        if surf is None:
            continue
        surfaces.append(surf)
        by_name[surf.name] = surf

    # Resolve fenestration zones: field stored as building surface name
    for s in surfaces:
        if s.object_type.startswith("Fenestration") and s.zone_name:
            parent = by_name.get(s.zone_name)
            if parent is not None:
                s.zone_name = parent.zone_name

    return IdfGeometry(surfaces=surfaces, source=source)


def rgb_from_temperature(
    zone_temp_c: float,
    *,
    min_temp: float = 20.0,
    max_temp: float = 26.0,
) -> str:
    """Map zone °C to a cool→warm rgb() string for Mesh3d facecolor."""
    t = max(min_temp, min(max_temp, float(zone_temp_c)))
    ratio = (t - min_temp) / (max_temp - min_temp) if max_temp > min_temp else 0.5
    red = int(ratio * 255)
    blue = int(255 - red)
    return f"rgb({red},40,{blue})"


def idf_massing_figure(
    geom: IdfGeometry,
    *,
    zone_temps: dict[str, float] | None = None,
    title: str | None = None,
    height: int = 480,
):
    """Plotly 3D massing from parsed IDF surfaces.

    ``zone_temps`` maps zone name → °C (EnergyPlus native). Missing zones stay gray.
    """
    import plotly.graph_objects as go

    zone_temps = zone_temps or {}
    fig = go.Figure()
    if not geom.surfaces:
        fig.update_layout(title="No BuildingSurface:Detailed found in IDF")
        return fig

    for surf in geom.surfaces:
        temp = zone_temps.get(surf.zone_name)
        if surf.is_fenestration:
            color = "rgba(120,180,255,0.45)"
            opacity = 0.45
        elif temp is not None:
            color = rgb_from_temperature(temp)
            opacity = 0.85
        else:
            stype = surf.surface_type.upper()
            if stype in {"ROOF", "CEILING"}:
                color = "rgba(160,160,160,0.9)"
            elif stype == "FLOOR":
                color = "rgba(100,100,100,0.7)"
            else:
                color = "rgba(200,200,200,0.75)"
            opacity = 0.8

        label = surf.name
        if surf.zone_name:
            label = f"{surf.zone_name}: {surf.name}"
        if temp is not None:
            label = f"{label} ({temp:.1f} C)"

        xs = [v[0] for v in surf.vertices] + [surf.vertices[0][0]]
        ys = [v[1] for v in surf.vertices] + [surf.vertices[0][1]]
        zs = [v[2] for v in surf.vertices] + [surf.vertices[0][2]]
        fig.add_trace(
            go.Scatter3d(
                x=xs,
                y=ys,
                z=zs,
                mode="lines",
                line=dict(color="#333", width=2),
                name=label,
                hoverinfo="name",
                showlegend=False,
            )
        )
        if len(surf.vertices) >= 3:
            i_idx: list[int] = []
            j_idx: list[int] = []
            k_idx: list[int] = []
            for t in range(1, len(surf.vertices) - 1):
                i_idx.append(0)
                j_idx.append(t)
                k_idx.append(t + 1)
            vx = [v[0] for v in surf.vertices]
            vy = [v[1] for v in surf.vertices]
            vz = [v[2] for v in surf.vertices]
            mesh_kwargs: dict[str, Any] = {
                "x": vx,
                "y": vy,
                "z": vz,
                "i": i_idx,
                "j": j_idx,
                "k": k_idx,
                "opacity": opacity,
                "flatshading": True,
                "name": label,
                "hoverinfo": "name",
                "showlegend": False,
            }
            if color.startswith("rgb(") and not color.startswith("rgba"):
                mesh_kwargs["facecolor"] = [color] * len(i_idx)
            else:
                mesh_kwargs["color"] = color
            fig.add_trace(go.Mesh3d(**mesh_kwargs))

    summary = geom.summary()
    bb = summary.get("bbox_ft") or {}
    t = title or "IDF massing (published model)"
    if bb:
        t = f"{t} — ~{bb.get('dx')}x{bb.get('dy')}x{bb.get('dz')} ft bbox"
    fig.update_layout(
        title=t,
        height=height,
        margin=dict(l=0, r=0, t=50, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        scene=dict(
            aspectmode="data",
            xaxis_title="X (m)",
            yaxis_title="Y (m)",
            zaxis_title="Z (m)",
            bgcolor="rgba(15,20,25,0.2)",
        ),
    )
    return fig
