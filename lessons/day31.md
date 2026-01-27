## Day 31 – Sorting Lists

### Goal

Understand how to sort data in Python using the built‑in `sorted()` function and the `list.sort()` method, and implement a simple **bubble sort** algorithm by hand.

### Concept

Python’s `sorted()` function returns a new sorted list from the items in an iterable and accepts optional `key` and `reverse` arguments【329836770204326†L1876-L1894】. The `list.sort()` method sorts a list in place and has the same arguments. If you need to control the sort order (e.g., sort dictionaries by a nested value) you can pass a `key` function such as a lambda expression.

**Bubble sort** is a simple sorting algorithm that repeatedly steps through the list, compares adjacent elements and swaps them if they are in the wrong order. It continues until no swaps are needed. Bubble sort is inefficient for large lists (O(n²)), but implementing it helps you understand sorting.

### How to Use It

**Using `sorted()` and `sort()`:**

```python
numbers = [5, 2, 9, 1]

# get a new sorted list
sorted_numbers = sorted(numbers)  # [1, 2, 5, 9]

# sort in place
numbers.sort(reverse=True)
print(numbers)  # [9, 5, 2, 1]

# sort list of tuples by second element
pairs = [('a', 3), ('b', 1), ('c', 2)]
sorted_pairs = sorted(pairs, key=lambda p: p[1])  # [('b', 1), ('c', 2), ('a', 3)]
```

**Bubble sort implementation:**

```python
def bubble_sort(lst):
    """Sort a list in ascending order using bubble sort and return a new list."""
    result = lst.copy()
    n = len(result)
    # repeat passes
    for i in range(n):
        # last i elements are already sorted
        for j in range(0, n - i - 1):
            if result[j] > result[j + 1]:
                # swap
                result[j], result[j + 1] = result[j + 1], result[j]
    return result

nums = [3, 2, 5, 1, 4]
print(bubble_sort(nums))  # [1, 2, 3, 4, 5]
```

### Why This Matters

Sorting is ubiquitous in data processing: you might sort rooms by area or temperatures by value. Understanding Python’s sort functions and implementing a simple sort yourself deepens your algorithmic intuition and helps you appreciate the efficiency of built‑in tools.

### Mini Examples

- Use `sorted()` to sort a list of dictionaries by a nested value, such as sorting devices by their `points['temp']` reading.
- Adapt bubble sort to sort a list of strings alphabetically.
- Compare the number of swaps bubble sort makes on an already sorted list versus a reversed list.

### Micro Exercises

1. Write a function `selection_sort(lst)` that implements the selection sort algorithm (find the smallest element and put it at the beginning, then repeat for the remaining list).
2. Given a list of `(name, value)` tuples, use `sorted()` with a `key` to sort the list by the numeric value in descending order.
3. Modify `bubble_sort` so that it can sort in descending order when a `reverse=True` parameter is passed.

### Key Takeaway

Use `sorted()` or `list.sort()` with optional `key` and `reverse` arguments to sort sequences efficiently【329836770204326†L1876-L1894】. Implementing simple algorithms like bubble sort helps you understand the mechanics behind sorting and appreciate the efficiency of Python’s built‑ins.