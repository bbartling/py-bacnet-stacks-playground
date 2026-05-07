timestamps = [
    "2026-01-15 05:00",
    "2026-01-15 05:15",
    "2026-01-15 05:30",
    "2026-01-15 05:45",
    "2026-01-15 06:00",
    "2026-01-15 06:15",
    "2026-01-15 06:30",
]

oat = [
    41.2,
    39.8,
    37.4,
    35.6,
    44.9,
    33.7,
    36.1,
]


def time_finder(timestamps,oat):
    matches = []
    for i, temp in zip(timestamps,oat):
        if temp < 35.0:
            matches.append(i)

    return matches


time_finder(timestamps, oat)

