"""Parse EnergyPlus IDF surfaces into Plotly 3D massing (unique per published run).

No hard-coded building footprints — geometry always comes from
``BuildingSurface:Detailed`` / ``FenestrationSurface:Detailed`` in the IDF
agents publish to ``runs/<id>/model.idf``.
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
        return out


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
    if isinstance(text_or_path, Path) or (
        isinstance(text_or_path, str)
        and len(text_or_path) < 400
        and Path(text_or_path).is_file()
    ):
        path = Path(text_or_path)
        text = path.read_text(encoding="utf-8", errors="replace")
        source = str(path)
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


def zone_mean_temps_by_name(ts: Any) -> dict[str, float]:
    """Map EnergyPlus zone name → mean °C from an EplusTimeseries."""
    if ts is None:
        return {}
    means = ts.zone_mean_temps() if hasattr(ts, "zone_mean_temps") else None
    if means is None or getattr(means, "empty", True):
        return {}
    out: dict[str, float] = {}
    for _, row in means.iterrows():
        out[str(row["zone"])] = float(row["mean_c"])
    return out


def idf_massing_figure(
    geom: IdfGeometry,
    *,
    zone_temps: dict[str, float] | None = None,
    title: str | None = None,
):
    """Plotly 3D massing from parsed IDF surfaces."""
    import plotly.graph_objects as go

    from wattlab.studio.ep_viz import rgb_from_temperature

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
        height=520,
        margin=dict(l=0, r=0, t=50, b=0),
        scene=dict(
            aspectmode="data",
            xaxis_title="X (m)",
            yaxis_title="Y (m)",
            zaxis_title="Z (m)",
        ),
    )
    return fig
