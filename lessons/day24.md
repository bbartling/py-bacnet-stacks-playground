## Day 24 – `any()`, `all()`, Lambdas & Higher‑Order Functions

### Goal

Explore Python’s `any()` and `all()` functions and learn about
anonymous functions (lambdas) and higher‑order functions such as
`map()` and `filter()`.  These tools let you write concise code that
operates on collections.

### Concept

The built‑in functions `all()` and `any()` take an iterable and return a
Boolean.  `all()` returns `True` if *all* elements are true or if the
iterable is empty【329836770204326†L249-L260】.  `any()` returns `True` if
*any* element is true and `False` if the iterable is empty【329836770204326†L277-L288】.

A **lambda** expression creates an anonymous function.  The syntax is
`lambda arguments: expression`.  Lambdas are often used with
higher‑order functions like `map()` (which applies a function to each
element of an iterable) and `filter()` (which keeps elements for which
the function returns true).

### How to Use It

**`all()` and `any()`:**

```python
readings = [72, 71, 69, 73]

# check if all readings are above 65
print(all(r > 65 for r in readings))  # True

# check if any reading is above 72
print(any(r > 72 for r in readings))  # True
```

**Lambdas with `map()` and `filter()`:**

```python
temps_f = [72, 68, 75]

# convert each temperature to Celsius
temps_c = list(map(lambda f: (f - 32) * 5/9, temps_f))

# keep only even numbers
numbers = [1, 2, 3, 4, 5]
evens = list(filter(lambda n: n % 2 == 0, numbers))
```

Lambdas are commonly used as the `key` argument to `sorted()` or
`min()`/`max()`.  For example, sort words by length:

```python
words = ['temperature', 'flow', 'humidity']
print(sorted(words, key=lambda w: len(w)))
```

### Why This Matters

Functions like `any()` and `all()` simplify checks over collections and
improve readability.  Lambdas and higher‑order functions encourage a
functional programming style where you describe *what* to do to each
element rather than writing explicit loops.  This is helpful when
processing lists of points or filtering sensor values.

### Mini Examples

- Use `any()` to check whether any point in a list of BACnet objects is
  of type `analog-input`.
- Use `filter()` with a lambda to extract all strings longer than five
  characters from a list of names.
- Sort a list of tuples `(name, value)` by the numeric value using the
  `key` argument and a lambda.

### Micro Exercises

1. Given `values = [0, 1, 2, 3]`, use `any()` to check if any value is
   negative and use `all()` to check if all values are less than 10.
2. Use `map()` and a lambda to create a new list containing the cubes
   of the numbers 1–5.
3. Use `filter()` and a lambda to produce a list of rooms from
   `['room101', 'lab', 'office', 'room102']` that start with `'room'`.

### Key Takeaway

`all()` returns `True` only if every element of an iterable is true, while
`any()` returns `True` if at least one element is true【329836770204326†L249-L260】【329836770204326†L277-L288】.
Lambda functions allow you to define small anonymous functions inline,
which are useful with `map()`, `filter()` and as keys for sorting.