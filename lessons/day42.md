## Day 42 — Stacks and depth-first walks on a grid (optional hobby)

### Goal

Use a Python **`list` as a stack** (`append` to push, `pop()` to pop). Walk a tiny **maze** stored as rows of characters: from a start cell, explore **as deep as possible**, then **backtrack** when blocked—**depth-first** order. This is the same **LIFO** discipline as **recursive backtracking** (Day 43), but the stack is visible in your code.

### Concept

- **Stack:** last item in is first out. In Python: `stack.append(x)` and `y = stack.pop()`.
- **DFS on a grid:** push a start cell; while the stack is not empty, pop a cell, if it is open and not yet seen, mark seen, push its **unvisited** neighbors (pick an order, e.g. up, right, down, left).
- **Backtracking:** when a cell has no new neighbors to push, the loop naturally returns to the previous cell because it is still under the top of the stack—until that cell is popped too.

Toy maze (`#` wall, `.` open, `S` start):

```python
def dfs_reachable_count(rows, start_r, start_c):
    height = len(rows)
    width = len(rows[0])
    seen = []
    for _ in range(height):
        row_seen = []
        for _ in range(width):
            row_seen.append(False)
        seen.append(row_seen)

    stack = []
    stack.append((start_r, start_c))
    count = 0

    while len(stack) > 0:
        r, c = stack.pop()
        if r < 0 or r >= height or c < 0 or c >= width:
            continue
        ch = rows[r][c]
        if ch == "#":
            continue
        if seen[r][c]:
            continue
        seen[r][c] = True
        count = count + 1
        stack.append((r - 1, c))
        stack.append((r + 1, c))
        stack.append((r, c - 1))
        stack.append((r, c + 1))

    return count


maze = ["###", "#S#", "#.#", "###"]
print(dfs_reachable_count(maze, 1, 1))
```

(You may rename `S` to `.` after reading the start, or treat `S` as open—the count above includes only cells reached through open passages.)

### Why stacks matter in buildings work

Supervisory tools rarely ask you to hand-roll DFS. The **habit** you are building is: **explicit frontier** (stack or queue), **visited** or **closed set**, **neighbor expansion**—the same skeleton as **commissioning walk lists**, **alarm flood** diagnostics, or “**which equipment is upstream**” sketches on a **directed** graph (Brick does that without the grid).

### Tie-in to maze-algorithm-sandbox

The Lua **MazeGenerator** in `maze-algorithm-sandbox` keeps a **stack of cells**, picks a **random unvisited neighbor**, **carves** a wall, **pushes** forward, and **pops** when stuck. Today you separated **stack + DFS** from **random carving** so each idea stays small.

### Micro exercises

1. Return a **list of (r, c)** in the order cells **first become seen** (append on mark-seen; still one stack for walking).
2. Replace the stack with a **queue** (FIFO: push at end, pop from index `0` with `pop(0)`—slow but fine for tiny grids) and describe how the visit order changes.
3. Add a **max steps** counter; stop and return `"TOO_MANY_STEPS"` if a bug creates an infinite loop.

### Key takeaway

A **stack** makes **depth-first** exploration and **backtracking** concrete. **Day 43** reuses that stack to **carve** a random perfect maze.
