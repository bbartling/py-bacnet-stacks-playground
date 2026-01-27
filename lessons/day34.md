# Day 34 – Aggregating Data & Basic Statistics

## Goal

After this lesson you will be able to calculate the **sum**, **mean**
and **median** of a list of numbers using simple loops and a few built‑in
functions.  You will also practise using `min()` and `max()` to find the
smallest and largest values in a sequence and understand how to sort a
list before computing the median.  These skills let you summarise sensor
readings or other datasets with a few lines of code.

## Concept

Aggregating data means combining multiple values into a single result,
such as adding up temperatures to get a total or computing their average.
In Python you can write a loop that accumulates a running total and
divides by the length of the list to compute the **mean**.  The `len()`
function returns the number of items in a sequence【126592705671557†L436-L442】,
so you can use it to avoid hard‑coding the length.

Finding the minimum and maximum values is even easier with the
built‑in functions `min()` and `max()`, which return the smallest and
largest items from an iterable or a sequence【329836770204326†L1277-L1294】.
To compute a **median** you need to sort the list first: the `sorted()`
function returns a new list containing all the items in ascending order
and guarantees a stable sort【329836770204326†L1876-L1894】.  For an odd
number of items the median is the middle value; for an even number you
typically average the two middle values.

## How to Use It

1. **Compute the sum and mean** — Use a loop to accumulate a running
   total; divide by the length to get the mean:
   ```python
   temperatures = [70.3, 68.5, 72.1, 69.4]
   total = 0
   for t in temperatures:
       total += t
   average = total / len(temperatures)      # len() returns number of items【126592705671557†L436-L442】
   print(f"Average temperature = {average:.2f}")
   ```

   Python also provides a built‑in `sum()` function, but writing the loop
   yourself reinforces how accumulation works.

2. **Find minimum and maximum values** — Use `min()` and `max()` on
   any iterable:
   ```python
   points = [13, 7, 19, 3]
   print(min(points))   # → 3【329836770204326†L1277-L1294】
   print(max(points))   # → 19【329836770204326†L1277-L1294】
   ```

3. **Compute the median** — Sort the list then select the middle value(s):
   ```python
   def median(data):
       n = len(data)
       sorted_data = sorted(data)           # returns new sorted list【329836770204326†L1876-L1894】
       mid = n // 2
       if n % 2 == 1:
           return sorted_data[mid]
       else:
           return (sorted_data[mid - 1] + sorted_data[mid]) / 2

   values = [5, 2, 9, 1, 7]
   print(median(values))  # → 5
   ```

## Why This Matters

Engineers frequently need to summarise large sets of data, such as sensor
readings or energy consumption.  Calculating the sum, mean and median
provides insight into central tendencies and helps identify outliers.  Using
built‑in functions like `min()`, `max()`【329836770204326†L1277-L1294】 and
`sorted()`【329836770204326†L1876-L1894】 reduces the chance of errors and keeps
your code concise.

## Mini Examples

```python
# Summarise a list of pressure readings (in Pascals)
pressures = [101.2, 99.8, 100.5, 102.1, 98.9]
total = 0
for p in pressures:
    total += p
print('Total pressure:', total)
print('Mean pressure:', total / len(pressures))

# Use min, max and median
print('Minimum pressure:', min(pressures))
print('Maximum pressure:', max(pressures))
print('Median pressure:', median(pressures))

# Sorted copy without modifying original
print('Sorted pressures:', sorted(pressures))
print('Original list remains:', pressures)
```

## Micro Exercises

1. Create a list of five random humidity values (floating‑point numbers).
   Write code to compute the total and average without using `sum()`.  Then
   verify the minimum and maximum using `min()` and `max()`.

2. Write a function `compute_stats(values)` that returns a tuple
   `(min_value, max_value, average, median_value)`.  Use the helper
   `median()` function shown above.

3. Explain why it is important to sort a list before computing the
   median, and describe what happens if you try to take the middle value
   from an unsorted list.

4. For an even‑length list `[4, 2, 9, 8]`, calculate the median using the
   provided formula.  Confirm your result by sorting the list and taking
   the two middle values.

## Key Takeaway

Aggregating numeric data helps you understand the overall behaviour of a
system.  Use loops and `len()`【126592705671557†L436-L442】 to compute averages,
built‑ins `min()` and `max()` to find extremes【329836770204326†L1277-L1294】,
and `sorted()`【329836770204326†L1876-L1894】 to prepare data for median
calculations.  These patterns are the basis for more advanced statistical
analysis.
