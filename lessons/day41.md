## Day 41 — Grids, neighbors, and “visited” (optional hobby; maze thinking)

### Goal

Treat a **2D layout** as **nested lists** (row index, then column index). List the **four neighbors** of a cell with **bounds checks**. Track **which cells you have already seen** with a parallel grid of booleans—same pattern as marking **visited** when carving or walking a maze.

This day is **optional hobby** CS: it warms you up for **Day 42–43** (stack + maze generation). It also previews the idea that a **floor plan** or **zoning grid** can be stored as a matrix, even though BACnet data is usually **not** a perfect rectangle.

### Concept

- **Grid:** `grid[r][c]` is one cell. Common convention: `r` in `0 .. height-1`, `c` in `0 .. width-1`.
- **Four-connected neighbors:** up, down, left, right—each offset by one in a single axis. Skip neighbors that would fall **outside** the grid.
- **Visited:** a second structure `seen[r][c]` (booleans) or reuse a simple rule (“only count cells with value `0`”) so you do not double-count.

Example: count how many cells hold the character `"."` in a small list-of-strings “map” (each string is one row).

```python
def count_open_cells(rows):
    n = 0
    for r in range(len(rows)):
        row = rows[r]
        for c in range(len(row)):
            if row[c] == ".":
                n = n + 1
    return n


lab_map = ["#.#", ".#.", "..."]
print(count_open_cells(lab_map))
```

Neighbors of `(r, c)` on a list-of-strings map (same shape as nested lists):

```python
def neighbors4(r, c, height, width):
    out = []
    if r > 0:
        out.append((r - 1, c))
    if r + 1 < height:
        out.append((r + 1, c))
    if c > 0:
        out.append((r, c - 1))
    if c + 1 < width:
        out.append((r, c + 1))
    return out
```

### Same idea elsewhere

The **maze-algorithm-sandbox** repo (Lua, in your `maze-algorithm-sandbox` folder) uses a **2D table of cells** in Lua: each cell has `visited` and **walls** flags. You are learning the **grid + neighbor + visited** vocabulary in Python first; **Day 43** mirrors its **stack-based maze carve** in spirit.

### Mini examples

- Print all coordinates `(r, c)` where `rows[r][c] == "#"` (walls).
- Given a start `(r0, c0)` on open cells, **flood** open cells in four directions without leaving `.` (use a `seen` grid and a hand-written list you treat as a **queue** or **stack**—Day 42 picks one style explicitly).

### Micro exercises

1. Write `in_bounds(r, c, height, width)` returning `True` / `False`.
2. Write `count_neighbors_wall(rows, r, c)` returning how many of the four neighbors are `#` (treat out-of-bounds as wall).
3. On paper: for a 3×3 grid of dots, mark the order cells are visited if you always try **up, right, down, left** and skip visited.

### Key takeaway

**2D index discipline** plus **neighbor lists** plus a **visited** flag is the substrate for maze generation, robot motion, and many **routing** sketches—before you ever open an RDF graph (Day 44 onward).
