"""Line-start EnergyPlus object extraction. Ignores in-field type references."""
from __future__ import annotations


def normalize_idf(src: str) -> str:
    return src.replace("\r\n", "\n").replace("\r", "\n")


def iter_objects(src: str, object_type: str) -> list[str]:
    """Yield objects whose *line* starts with ``object_type,``."""
    text = normalize_idf(src)
    marker = f"{object_type},"
    out: list[str] = []
    i = 0
    while True:
        j = text.find(marker, i)
        if j < 0:
            break
        if j > 0 and text[j - 1] != "\n":
            i = j + 1
            continue
        end = text.find(";", j)
        if end < 0:
            break
        out.append(text[j : end + 1])
        i = end + 1
    return out


def object_fields(block: str) -> list[str]:
    body = block.split(";", 1)[0]
    return [raw.split("!")[0].strip() for raw in body.split(",")]


def field_by_comment(block: str, comment: str) -> str | None:
    needle = comment.strip().lower()
    for line in block.splitlines():
        if "!-" not in line:
            continue
        left, _, right = line.partition("!-")
        label = right.strip().split("{", 1)[0].strip().lower()
        if label == needle:
            return left.strip().rstrip(",").strip()
    return None


def find_named_object(src: str, object_type: str, name: str) -> str | None:
    for block in iter_objects(src, object_type):
        fields = object_fields(block)
        if len(fields) > 1 and fields[1] == name:
            return block
    return None


def replace_comment_field(block: str, comment: str, value: str) -> str:
    needle = comment.strip().lower()
    lines = block.splitlines(keepends=True)
    found = False
    for i, line in enumerate(lines):
        if "!-" not in line:
            continue
        left, sep, right = line.partition("!-")
        label = right.strip().split("{", 1)[0].strip().lower()
        if label != needle:
            continue
        pad = left[len(left.rstrip()) :]
        stripped = left.strip()
        terminator = ""
        if stripped.endswith(";"):
            terminator = ";"
            stripped = stripped[:-1].rstrip()
        elif stripped.endswith(","):
            terminator = ","
        indent = left[: len(left) - len(left.lstrip())]
        lines[i] = f"{indent}{value}{terminator}{pad}{sep}{right}"
        found = True
        break
    if not found:
        raise ValueError(f"IDF field comment not found: {comment}")
    return "".join(lines)
