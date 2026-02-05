# Day 33 – Membership & Searching

## Goal

By the end of this lesson you will understand how to test whether an item is
present in a string or list using the **membership operator** `in` and how to
write a simple **linear search** function.  You will know when to rely on
built‑in membership tests and when to implement your own search loops.

## Concept

In Python you can quickly check if a value appears inside another sequence
using the `in` keyword.  For example, `'a' in 'plant'` returns `True`
because the substring `'a'` appears in the word `'plant'`, and `42 in
[1, 2, 3]` returns `False` because `42` is not in the list.  This
membership test is implemented under the hood by iterating through the
underlying sequence.  If you need to find the **index** of the matching
element you can write a **linear search** loop yourself.  A linear search
examines each element in turn until it finds a match or reaches the end.

For loops in Python iterate over the items of any sequence, which makes it
easy to implement a search.  The official tutorial notes that
`for` “loops can iterate over the items of any sequence”,
and you can combine this with the `range()` function, which yields a
sequence of indices from `0` to `n − 1`, to track
positions.  You will also need the `len()` function, which returns the
number of items in a sequence, to know when to stop.

Although dictionaries support membership testing on their keys,
the same `in` operator works for lists and strings as well.  Remember that
searching through a list or a long string manually takes time proportional
to the length of the sequence.  For small lists the cost is minimal, but
understanding the process helps you appreciate how algorithms work.

## How to Use It

1. **Membership tests** — To check if a value exists in a sequence, write
   `value in sequence`.  For strings the test looks for a substring;
   for lists it looks for a specific element.
   ```python
   'pump' in 'heat pump'    # True
   5 in [1, 3, 5, 7]        # True
   10 in [1, 2, 3]          # False
   ```

2. **Linear search** — When you need to find the index of a value, use a
   loop that walks through the list and returns the position of the first
   match.  Here we use `range(len(lst))` to generate indices and compare
   each element:
   ```python
   def linear_search(lst, target):
       for i in range(len(lst)):         # iterate over index positions
           if lst[i] == target:
               return i                  # return the index of the match
       return -1                         # return -1 if not found

   values = [3, 8, 2, 7]
   print(linear_search(values, 7))       # → 3
   print(linear_search(values, 9))       # → -1
   ```

3. **Breaking early** — Since linear search scans each element in order,
   it is efficient to stop as soon as you find a match.  Use the `return`
   statement or a `break` to exit the loop immediately.

## Why This Matters

Membership testing is one of the most common operations in programming.
Whether you are checking if a sensor name appears in a list of points or
validating user input, the `in` operator provides a concise way to express
the check.  Implementing a linear search manually helps you understand how
these built‑ins work under the hood and lays the groundwork for more
advanced searching and sorting algorithms.

## Mini Examples

```python
# Check membership in strings and lists
print('cool' in 'cooling coil')   # → True
print('heat' in ['cool', 'fan'])  # → False

# Find the index of an element
devices = ['AHU', 'VAV', 'Chiller']
for i in range(len(devices)):
    if devices[i] == 'VAV':
        print('Found at index', i)  # prints 'Found at index 1'
        break

# Use linear_search function
print(linear_search([10, 20, 30], 20))  # → 1
```

## Micro Exercises

1. Use the `in` operator to check if the substring `'fan'` appears in
   `'supply fan status'`.  Then check if `'T'` appears in the list
   `["OAT", "SAT", "MAT"]`.

2. Write your own `linear_search` function that returns the value rather
   than the index when it finds a match.  Test it with a list of
   temperatures.

3. Modify the `linear_search` function to search for a substring inside
   a list of strings.  For example, searching for `'pump'` should match
   `'condensate pump'`.

4. Imagine you have a list of equipment IDs.  Write a loop that prints
   "Missing" if an ID is not found in the list.  Use `in` for the
   membership test.

## Key Takeaway

The `in` operator offers a simple way to check whether a value exists in
strings, lists and other containers.  When you need more control, such as
finding the position of a match, you can implement a linear search using a
`for` loop and the `range()` function.  These
techniques form the foundation of more sophisticated search algorithms.
