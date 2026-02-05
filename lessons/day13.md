## Day 13 – Tuples & Sets

### Goal

Understand two additional built‑in container types—**tuples** and **sets**—and learn when to use them instead of lists. You’ll create tuples for fixed collections of values and sets for deduplicating items and performing basic membership tests.

### Concept

A **tuple** is an ordered, immutable sequence of values. Unlike lists, tuples cannot be modified after creation (you can’t append or assign to an index). Tuples are created by separating items with commas, and parentheses are optional in most contexts. Tuples are useful when the number and order of elements should not change—for example, representing a point in 2‑D space or a date as `(year, month, day)`. Python’s `tuple()` function can also convert other iterables into a tuple.

A **set** is an unordered collection of *unique* elements. Sets are created with curly braces `{}` or by calling `set()` with an iterable. Unlike lists, sets automatically remove duplicates and support efficient membership tests and mathematical operations like union, intersection and difference. The data structures chapter of the Python tutorial notes that *sets are unordered collections with no duplicate elements* and can be created using braces or the `set()` constructor.

### How to Use It

**Creating tuples:**

```python
# a 3‑element tuple representing a coordinate
coord = (10, 20, 30)

# parentheses are optional when the context is unambiguous
version = 3, 10, 2

# converting a list to a tuple
values = [1, 2, 3]
t = tuple(values)
```

Tuples support indexing and slicing like lists, but you cannot assign to them since they are immutable. Attempting `coord[0] = 5` will raise a `TypeError`.

**Creating sets:**

```python
# from a literal (duplicates are removed)
fruit_set = {"apple", "banana", "apple", "orange"}

# from an iterable
letters = set("hello")

# deduplicating a list
numbers = [1, 2, 2, 3, 3, 3]
unique = set(numbers)
```

Use set operations to combine or compare sets:

```python
a = {"red", "green"}
b = {"green", "blue"}
a.union(b)        # {'red', 'green', 'blue'}
a.intersection(b) # {'green'}
a.difference(b)   # {'red'}
```

### Why This Matters

Tuples and sets are lightweight alternatives to lists and dictionaries for simple data. Tuples help you group related values without worrying about accidental changes; sets make it trivial to remove duplicates, test membership and combine collections. In building automation, you might use a tuple to represent an HVAC zone’s coordinates or a set to collect all unique device identifiers discovered from a scan.

### Mini Examples

- Represent the dimensions of a room as a tuple: `dimensions = (12, 10)`.
- Convert a list of sensor names into a set to find unique sensors.
- Use set intersection to find which rooms are served by both Air Handler A and B.

### Micro Exercises

1. Create a tuple called `date` containing three numbers: year, month and day. Try printing `date[1]` (the month).
2. Convert the list `['hi', 'hi', 'hello', 'hello', 'hola']` into a set and print the result.
3. Make two sets `x = {1, 2, 3, 4}` and `y = {3, 4, 5}`. Compute and print `x.union(y)`, `x.intersection(y)` and `x.difference(y)`.

### Key Takeaway

Tuples group a fixed number of values in order and cannot be changed, while sets hold unordered unique elements and support fast membership tests and set operations.