## Day 43 — Iterative recursive-backtracking maze (optional hobby capstone)

### Goal

Implement a tiny **perfect maze** generator: every open cell is connected, no loops—classic **recursive backtracking** implemented with an **explicit stack** (same pattern as the **MazeGenerator** module in your **maze-algorithm-sandbox** Lua project (same workspace folder): stack, unvisited neighbors, carve, backtrack on dead ends).

This is the **most “CS textbook”** piece of the algorithms arc here; it sits **after** HVAC lists, rules, and thermal capstone (**Day 40**) and **before** graph-as-data for Brick (**Day 44**).

### Concept

Each **cell** stores:

- Integer coordinates `x`, `y` (or `r`, `c`).
- **`visited`** boolean for generation.
- **Walls:** four booleans (north, east, south, west) or use `Top`/`Bottom`/`Left`/`Right` names like the Lua original.

**Algorithm (iterative):**

1. Build a full grid of cells with **all walls up** and `visited = False`.
2. `stack = []`, pick a **start cell**, mark visited, push it.
3. While stack not empty:
   - **Peek** current = top of stack.
   - Collect **unvisited** orthogonal neighbors inside bounds.
   - If any: choose one (for variety use **`random.randint`** from the `random` module), **remove the wall** between current and chosen, mark chosen visited, **push** chosen.
   - Else: **pop** (backtrack).

No `pandas`; no list comprehensions required in lesson code—loops are fine.

### Minimal Python sketch (walls as N/E/S/W strings)

```python
import random


def make_maze(width, height):
    cells = []
    for y in range(height):
        row = []
        for x in range(width):
            row.append(
                {
                    "x": x,
                    "y": y,
                    "visited": False,
                    "N": True,
                    "E": True,
                    "S": True,
                    "W": True,
                }
            )
        cells.append(row)

    def neighbors(cell):
        x = cell["x"]
        y = cell["y"]
        opts = []
        if y > 0 and not cells[y - 1][x]["visited"]:
            opts.append((cells[y - 1][x], "N", "S"))
        if y + 1 < height and not cells[y + 1][x]["visited"]:
            opts.append((cells[y + 1][x], "S", "N"))
        if x > 0 and not cells[y][x - 1]["visited"]:
            opts.append((cells[y][x - 1], "W", "E"))
        if x + 1 < width and not cells[y][x + 1]["visited"]:
            opts.append((cells[y][x + 1], "E", "W"))
        return opts

    stack = []
    start = cells[0][0]
    start["visited"] = True
    stack.append(start)

    while len(stack) > 0:
        cur = stack[len(stack) - 1]
        opts = neighbors(cur)
        if len(opts) > 0:
            nxt, wall_cur, wall_nxt = opts[random.randint(0, len(opts) - 1)]
            cur[wall_cur] = False
            nxt[wall_nxt] = False
            nxt["visited"] = True
            stack.append(nxt)
        else:
            stack.pop()

    return cells
```

Printing ASCII is optional glue: two characters wide per cell is enough for a screenshot-worthy tiny maze.

### HVAC angle (light)

**Duct or pipe runs** are sometimes modeled as **graphs on a coarse grid** for clash checks—not identical to a game maze, but the **same bookkeeping**: cells, adjacency, “**have I already routed here**?”

### Micro exercises

1. Seed **`random.seed(123)`** before `make_maze(5, 5)` so your output is **reproducible** while debugging.
2. After generation, write `wall_string(cell)` returning something like `"#" * 4` bits for closed walls and use it to **assert** every cell has at least one open wall except corners (not a formal proof—sanity checks).
3. Compare **recursive** `def carve(x, y):` that calls itself on the neighbor vs the **iterative stack** version—same tree of moves, different Python call discipline.

### Key takeaway

**Recursive backtracking** on a grid is **DFS + undo**. An **explicit stack** matches the Lua reference implementation and transfers cleanly to other **backtracking** puzzles—still optional hobby next to your **BACnet-first** path.
