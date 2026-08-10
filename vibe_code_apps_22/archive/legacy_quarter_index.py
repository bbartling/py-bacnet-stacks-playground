"""ARCHIVED — do not import. Legacy E+ farm quarter indexing (pre-interval15).

Bug: stamps 00:15 and 00:30 returned hour_ending=24; 00:00 and 24:00 both q=95.
"""


def _quarter_index(stamp: str) -> tuple[int, int, int]:
    parts = str(stamp).strip().split()
    if len(parts) < 2:
        return 0, 0, 0
    hm = parts[1].split(":")
    h = int(hm[0])
    mi = int(hm[1]) if len(hm) > 1 else 0
    if h == 24:
        return 24, 0, 95
    if mi == 0:
        he = h if h > 0 else 24
        q = (he * 4 - 1) % 96
    else:
        he = h
        q = h * 4 + (mi // 15) - 1
    return he, mi, int(q) % 96
