# Day 07 – List Operations & Methods

*Part I: Fundamentals | Week 1*

## Goal

Explore the rich set of operations available for Python lists.  By the end of
this lesson you’ll know how to add, remove, sort and copy lists using their
built‑in methods.

## Concept

Python lists provide many methods for manipulating their contents.  The
`append(x)` method adds a single item to the end; `extend(t)` concatenates
another iterable; `insert(i, x)` inserts at a given index; `remove(x)`
removes the first occurrence; `pop(i)` removes and returns the item at index
`i` (defaulting to the last item) and `clear()` removes all items.
`index(x)` returns the index of the first occurrence and `count(x)` returns
the number of times x appears.  `sort()` sorts the list in place and
`reverse()` reverses the elements.  These methods
modify the list and return `None` as a reminder that they act by side
effect.

## How to Use It

1. **Adding elements.**

   ```python
   fruits = ['apple', 'banana']
   fruits.append('cherry')      # ['apple', 'banana', 'cherry']
   fruits.extend(['date', 'fig'])  # ['apple', 'banana', 'cherry', 'date', 'fig']
   fruits.insert(1, 'blueberry')   # insert at index 1
   ```

2. **Removing elements.**

   ```python
   fruits.remove('banana')  # removes first 'banana'
   last = fruits.pop()      # removes and returns last item
   fruits.clear()           # empties the list
   ```

3. **Searching and counting.**

   ```python
   numbers = [1, 2, 3, 2, 4, 2]
   print(numbers.index(3))  # 2
   print(numbers.count(2))  # 3
   ```

4. **Sorting and reversing.**

   ```python
   values = [3, 1, 4, 1, 5]
   values.sort()       # [1, 1, 3, 4, 5]
   values.reverse()    # [5, 4, 3, 1, 1]
   ```

5. **Copying lists.**  Use `copy()` for a shallow copy or slicing `[:]`:

   ```python
   original = [1, 2, 3]
   clone = original.copy()
   clone.append(4)
   print(original, clone)  # [1, 2, 3] [1, 2, 3, 4]
   ```

## Why This Matters

Knowing list methods lets you manipulate collections efficiently.  For
example, you can build a list of discovered BACnet devices using
`append()`, remove faulty entries with `remove()`, sort the list by instance
number and create a copy for safe experimentation.  Understanding that
methods modify the list and return `None` avoids mistakes when chaining
operations.

## Mini Examples

```python
# build and update a list of points
points = ['ZoneTemp', 'ZoneCoolingSpt']
points.append('ZoneDemand')
points.insert(1, 'VAVFlow')
print(points)  # ['ZoneTemp', 'VAVFlow', 'ZoneCoolingSpt', 'ZoneDemand']

# count occurrences and remove
readings = [70, 72, 70, 73, 70]
print(readings.count(70))  # 3
readings.remove(70)        # remove first 70
print(readings)

# sort and reverse
ids = [3456790, 123456, 3456789]
ids.sort()
print(ids)          # [123456, 3456789, 3456790]
ids.reverse()
print(ids)          # [3456790, 3456789, 123456]
```

## Micro Exercises

1. Start with the list `devices = ['AHU1', 'VAV1', 'VAV2']`.  Append `'VAV3'`,
   insert `'Boiler'` at the beginning and remove `'VAV1'`.  Print the final list.
2. Create a list of numbers and write code to remove the largest number using
   `max()` and `remove()`.
3. Given a list of names, use `sort()` to order them alphabetically and then
   `reverse()` the order.
4. Create a list and a shallow copy using `copy()`.  Modify the copy and
   verify that the original remains unchanged.

## Key Takeaway

Python lists provide many methods for adding, removing, searching, sorting and
copying items.  These methods modify the list in‑place and return `None` to emphasise their side effect.

---

## Vibe Code Checkpoint 1 — Complete!

By the end of today you should have a BAC0 app that can **read**, **write**, and **write null release**. Use a list to hold multiple read requests if you like, or build your address strings with f-strings. Demo on your test bench — your Python app should match scanner results. Next week: data collection and CSV logging!
