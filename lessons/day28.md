## Day 28 – Linear Search

### Goal

Implement the **linear search** algorithm to find an item in a list. You will write a function that scans through a sequence until it locates a target value or determines the value is not present.

### Concept

Linear search is the simplest search algorithm. Given a list and a target value, it checks each element in order until it finds the target. If it reaches the end without finding the value, it returns `None` (or another sentinel). Even though Python’s `in` operator performs a similar check under the hood, implementing linear search yourself helps you understand how membership testing works.

### How to Use It

Here is a linear search function that returns the index of the target value or `-1` if the value is not found:

```python
def linear_search(seq, target):
    """Return the index of target in seq or -1 if not found."""
    for index, item in enumerate(seq):
        if item == target:
            return index
    return -1

values = ['Temp', 'Flow', 'Humidity']
print(linear_search(values, 'Flow'))     # 1
print(linear_search(values, 'Pressure'))  # -1
```

### Why This Matters

Linear search is useful when you have an unsorted list and need to determine whether a value exists. In building automation, you might scan through a list of device instances to find a particular object. Knowing the algorithm reminds you that search time grows linearly with the size of the list, and that sorting or using a dictionary can improve performance for large datasets.

### Mini Examples

- Adapt the function to return `True` or `False` instead of an index.
- Modify the function to search a list of dictionaries for a matching `name` key.
- Use the algorithm to find the first temperature above 75 °F in a list.

### Micro Exercises

1. Write a function `find_min_index(nums)` that returns the index of the smallest number in `nums` using a linear scan.
2. Given a list of sensor names, use a loop to check whether `'ZoneTemp'` appears in the list and print an appropriate message.
3. Modify `linear_search` so that it returns a list of all indices where the target value occurs (useful if the value appears multiple times).

### Key Takeaway

Linear search scans each element in a sequence until it finds the target value or reaches the end. Understanding this algorithm illustrates how membership testing works in Python and why searching unordered data is O(n).