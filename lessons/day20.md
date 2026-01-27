## Day 20 – Built‑in Functions & Comprehensions

### Goal

Discover some of Python’s most useful **built‑in functions** for working
with iterables and practise writing **list and dictionary comprehensions**
to create collections concisely.

### Concept

The Python interpreter provides many built‑in functions that are always
available.  Among these are `min()` and `max()`, which return the
smallest and largest item from an iterable or from multiple arguments
【329836770204326†L1277-L1294】【329836770204326†L1306-L1316】.  `sorted()` returns a new sorted
list from the items in an iterable and accepts optional `key` and
`reverse` arguments【329836770204326†L1876-L1894】.  `sum()` adds together numbers,
`enumerate()` returns pairs of index and value【972561048532027†L614-L640】, and
`zip()` combines two or more sequences into tuples.  These functions
reduce the amount of code you need to write and improve readability.

**Comprehensions** are compact ways to build lists, sets or dictionaries
from iterables.  A list comprehension looks like
`[expression for item in iterable if condition]` and returns a new list.
Dictionary comprehensions use curly braces and a `key: value`
expression【972561048532027†L590-L612】.

### How to Use It

**Built‑ins:**

```python
numbers = [5, 2, 9, 1, 7]
print(min(numbers))            # 1
print(max(numbers))            # 9
print(sorted(numbers))         # [1, 2, 5, 7, 9]
print(sorted(numbers, reverse=True))  # [9, 7, 5, 2, 1]
print(sum(numbers))            # 24

for index, value in enumerate(['a', 'b', 'c']):
    print(index, value)  # 0 a, 1 b, 2 c

for name, value in zip(['Temp', 'Flow'], [72, 450]):
    print(name, value)
```

**List comprehensions:**

```python
# squares of even numbers from 0 to 9
squares = [n*n for n in range(10) if n % 2 == 0]
# ['room1', 'room2', 'room3'] from range
rooms = [f"room{n}" for n in range(1, 4)]
```

**Dictionary comprehensions:**

```python
# map each room to its square footage
sizes = {'room1': 120, 'room2': 150, 'room3': 180}
sq_meters = {room: sqft * 0.0929 for room, sqft in sizes.items()}
```

### Why This Matters

Built‑in functions encapsulate common operations such as finding
minimum/maximum values or combining sequences, making your code clearer.
Comprehensions enable you to create new collections from existing data
without writing verbose loops.  These tools are powerful when working
with building models, allowing you to transform and filter lists of
points or rooms succinctly.

### Mini Examples

- Given a dictionary of sensor names and readings, use `min()` and `max()`
  to find the lowest and highest values.
- Use `sorted()` with the `key` parameter to sort strings by length.
- Write a list comprehension that converts a list of Fahrenheit
  temperatures to Celsius.

### Micro Exercises

1. Create a list `values = [3, 1, 4, 1, 5, 9]` and use `sum()`, `min()`
   and `max()` to compute its total, minimum and maximum.
2. Use `zip()` to combine two lists—`names = ['Temp', 'Flow', 'Humidity']`
   and `readings = [72, 450, 45]`—into a dictionary of name–value
   pairs using a comprehension.
3. Write a list comprehension that generates the cubes of numbers 1–5 and
   filters out any result greater than 100.

### Key Takeaway

Python’s built‑in functions such as `min()`, `max()`, `sorted()` and
`enumerate()` simplify common tasks【329836770204326†L1277-L1294】【329836770204326†L1876-L1894】.  List and
dictionary comprehensions provide concise syntax for transforming and
filtering data【972561048532027†L590-L612】.