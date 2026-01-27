## Day 29 – Finding Minimum & Maximum

### Goal

Write your own functions to find the **minimum** and **maximum** values
in a list.  Although Python provides `min()` and `max()`【329836770204326†L1277-L1294】【329836770204326†L1306-L1316】,
implementing these functions yourself reinforces your understanding of
scanning algorithms.

### Concept

To find the smallest value in a list, initialise a variable to the
first element and then iterate through the remaining elements,
updating the variable whenever a smaller value is found.  The
procedure is similar for finding the largest value.  This pattern is
commonly called an **accumulation** or **reduction** pattern.

### How to Use It

**Find the minimum:**

```python
def find_min(values):
    """Return the smallest value in the list values."""
    smallest = values[0]
    for v in values[1:]:
        if v < smallest:
            smallest = v
    return smallest

numbers = [3, 1, 4, 1, 5, 9]
print(find_min(numbers))  # 1
```

**Find the maximum:**

```python
def find_max(values):
    """Return the largest value in the list values."""
    largest = values[0]
    for v in values[1:]:
        if v > largest:
            largest = v
    return largest

print(find_max(numbers))  # 9
```

### Why This Matters

Computing minima and maxima manually teaches you how to accumulate
information while iterating over data.  In sensor networks you might
need to find the highest airflow or lowest temperature.  Knowing
how to implement the search yourself ensures you can adapt the logic
for more complex comparisons (e.g., based on multiple attributes).

### Mini Examples

- Extend `find_min` to return both the smallest value and its index.
- Modify `find_max` to handle an empty list by returning `None`.
- Create a function `find_extremes(values)` that returns a tuple
  `(min_value, max_value)` in a single pass.

### Micro Exercises

1. Write a function `find_longest_word(words)` that returns the longest
   string in a list of words.  If multiple words have the same length,
   return the first one.
2. Create a list of random integers and verify that your `find_min`
   matches Python’s built‑in `min()` for the same list.
3. Modify the `find_min` algorithm to work on a list of `(name, value)`
   tuples by comparing the numeric value.

### Key Takeaway

Manual min/max functions initialise an accumulator and update it when a
smaller or larger element is found.  Although Python’s `min()` and
`max()` functions automate this process【329836770204326†L1277-L1294】【329836770204326†L1306-L1316】,
implementing the algorithm yourself improves algorithmic thinking.