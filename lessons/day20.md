# Day 20 – Built-in Functions

*Part II: Control Structures | Week 3*

## Goal

Discover Python's most useful **built-in functions** for working with iterables: `min()`, `max()`, `sorted()`, `sum()`, `enumerate()`, and `zip()`. Use loops to transform data — no comprehensions.

## Concept

Python provides many built-in functions. `min()` and `max()` return the smallest and largest item from an iterable. `sorted()` returns a new sorted list. `sum()` adds numbers. `enumerate()` returns index–value pairs. `zip()` combines two or more sequences into tuples. Use these with `for` loops to process sensor data.

## How to Use It

**Built-ins:**

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

**Transform data with loops (no comprehensions):**

```python
# squares of even numbers from 0 to 9
squares = []
for n in range(10):
    if n % 2 == 0:
        squares.append(n * n)

# build room names from range
rooms = []
for n in range(1, 4):
    rooms.append('room' + str(n))
```

**Convert units with a loop:**

```python
sizes = {'room1': 120, 'room2': 150, 'room3': 180}
sq_meters = {}
for room, sqft in sizes.items():
    sq_meters[room] = sqft * 0.0929
```

## Why This Matters

Built-in functions encapsulate common operations — finding min/max, sorting, summing. Using loops to build new lists and dictionaries keeps your code explicit and easy to follow. These tools are powerful when working with sensor readings and point lists.

## Mini Examples

- Given a dictionary of sensor names and readings, use `min()` and `max()` to find the lowest and highest values.
- Use `sorted()` with the `key` parameter to sort strings by length.
- Write a loop that converts a list of Fahrenheit temperatures to Celsius and appends each result to a new list.

## Micro Exercises

1. Create a list `values = [3, 1, 4, 1, 5, 9]` and use `sum()`, `min()` and `max()` to compute its total, minimum and maximum.
2. Use `zip()` to combine two lists — `names = ['Temp', 'Flow', 'Humidity']` and `readings = [72, 450, 45]` — into a dictionary using a `for` loop.
3. Write a loop that generates the cubes of numbers 1–5, and only appends to a new list those results that are 100 or less.

## Key Takeaway

Python's built-in functions such as `min()`, `max()`, `sorted()`, `sum()`, `enumerate()` and `zip()` simplify common tasks. Use `for` loops to build new lists and dictionaries — clear and maintainable.
