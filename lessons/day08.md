# Day 08 – For Loops & Range

## Goal

Learn how to iterate over sequences using `for` loops and generate sequences
of numbers with the `range()` function.  By the end of this lesson you’ll be
comfortable looping through lists, strings and ranges, and using `enumerate()`
to access both index and value.

## Concept

In Python the `for` statement iterates over the items of any sequence such as
a list or a string.  In the tutorial, a `for` loop prints each word and its
length from a list.  The built‑in `range()`
function returns an iterable sequence of numbers which can be used in loops.
`range(n)` produces numbers from `0` up to but not including `n`, and you can
provide a start and step to control the sequence.

## How to Use It

1. **Loop over a list.**  The `for` loop assigns each item in the sequence to
   the loop variable in turn:

   ```python
   fruits = ['apple', 'banana', 'cherry']
   for fruit in fruits:
       print(fruit)
   ```

2. **Loop over a string.**  Strings are sequences too:

   ```python
   for char in 'BACnet':
       print(char)
   ```

3. **Use `range()`.**  Generate numeric sequences:

   ```python
   for i in range(5):
       print(i)  # prints 0 1 2 3 4

   for i in range(2, 10, 2):
       print(i)  # prints 2 4 6 8
   ```

4. **Get index and value.**  Use `enumerate()` to access both:

   ```python
   for index, value in enumerate(['VAV', 'AHU', 'Boiler']):
       print(index, value)
   ```

5. **Sum a range.**  You can compute sums with loops or use `sum()`:

   ```python
   total = 0
   for n in range(1, 6):
       total += n
   print(total)  # 15
   # or
   print(sum(range(1, 6)))
   ```

## Why This Matters

Iterating over sequences lets you perform operations on each element of a
collection—vital for tasks such as printing sensor names, computing average
temperatures or generating tables.  The `range()` function gives you control
over numeric loops and is used in many algorithms.

## Mini Examples

```python
# print each BACnet device instance with its position
devices = [3456789, 3456790, 123456]
for i, dev in enumerate(devices, start=1):
    print(f'Device {i}: {dev}')

# generate a table of squares
for n in range(1, 6):
    print(n, n*n)

# loop over characters in a string
name = 'AHU'
for ch in name:
    print(ch)
```

## Micro Exercises

1. Write a loop that prints the numbers 10 down to 1 using `range()`.
2. Given a list of temperatures, use a `for` loop to compute the average.
3. Use `enumerate()` to loop over the list `['north','south','east','west']`
   and print each direction with its index starting at 1.
4. Create a list of even numbers between 2 and 20 (inclusive) using
   `range()` and print the list.

## Key Takeaway

`for` loops iterate over sequences and `range()` generates arithmetic
progressions.  These constructs let you process lists, strings and numbers
cleanly.
