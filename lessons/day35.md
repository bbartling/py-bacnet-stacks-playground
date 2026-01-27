# Day 35 – Final Project & Next Steps

## Goal

Today you will build a small **command‑line application** that ties
together everything you have learned over the past five weeks.  The
project reads a list of numeric readings from the user, stores them in a
list, and computes statistics such as the total, mean, minimum, maximum,
median and sorted order.  You will organise your code into functions and
practice working with input, loops, conditionals and built‑in functions.

## Concept

A complete program often combines many language features: reading input,
converting values, storing data in lists or dictionaries, defining helper
functions and printing formatted output.  In this exercise you will ask
the user to enter a series of numbers separated by commas, use `split()`
to convert the string into individual values, convert each to a float,
and then compute the statistics from Day 34.  The `len()` function
returns the number of items【126592705671557†L436-L442】, while `min()`,
`max()`【329836770204326†L1277-L1294】 and `sorted()`【329836770204326†L1876-L1894】 help
compute extremes and ordering.  Remember to write your own function to
compute the median (see Day 34) and use f‑strings for clean output.

## How to Use It

Here is a possible structure for your program:

```python
def parse_values(line):
    """Convert a comma‑separated string into a list of floats."""
    parts = line.split(',')
    values = []
    for p in parts:
        p = p.strip()             # remove surrounding whitespace【158729984520153†L1769-L1790】
        if p:
            values.append(float(p))
    return values

def median(data):
    n = len(data)
    sorted_data = sorted(data)   # sorted returns a new list【329836770204326†L1876-L1894】
    mid = n // 2
    if n % 2 == 1:
        return sorted_data[mid]
    else:
        return (sorted_data[mid - 1] + sorted_data[mid]) / 2

def compute_stats(values):
    total = 0
    for v in values:
        total += v
    mean = total / len(values)   # len() returns item count【126592705671557†L436-L442】
    return {
        'count': len(values),
        'total': total,
        'mean': mean,
        'min': min(values),       # built‑in functions【329836770204326†L1277-L1294】
        'max': max(values),
        'median': median(values),
        'sorted': sorted(values)  # new sorted list【329836770204326†L1876-L1894】
    }

def main():
    line = input('Enter readings separated by commas: ')
    values = parse_values(line)
    stats = compute_stats(values)
    print(f"You entered {stats['count']} values.")
    print(f"Total: {stats['total']}")
    print(f"Mean: {stats['mean']:.2f}")
    print(f"Min / Max: {stats['min']} / {stats['max']}")
    print(f"Median: {stats['median']}")
    print(f"Sorted: {stats['sorted']}")

if __name__ == '__main__':
    main()
```

Run your script from the command line using `python3 scriptname.py` and
enter a series of numbers when prompted.  The program splits the input
string, trims whitespace【158729984520153†L1769-L1790】, converts each value to a
`float`, computes the summary statistics, and prints the results.

## Why This Matters

Combining the various techniques you have learned—parsing input, loops,
data structures, functions and built‑ins—into a complete program helps
solidify your understanding.  This small project reflects many real
engineering tasks, such as analysing a set of measurements or exporting
data summaries.  By organising code into functions, you make it easier to
reuse and maintain.

## Mini Examples

```python
# Example of running the script:
# Enter readings separated by commas: 70.1, 68.9, 72.5, 69.0
# You entered 4 values.
# Total: 280.5
# Mean: 70.12
# Min / Max: 68.9 / 72.5
# Median: 69.55
# Sorted: [68.9, 69.0, 70.1, 72.5]
```

Try entering different sets of numbers and verify that the statistics are
correct.  The median should be the middle number for odd‑length lists and
the average of the two middle numbers for even‑length lists.

## Micro Exercises

1. Modify `parse_values()` so that it returns integers if the input values
   appear to be whole numbers (e.g. `'7'` becomes `7`).  Hint: use
   `value.isdigit()` on the stripped string.

2. Extend the project to compute the **range** of the values (maximum minus
   minimum).  Where would you add this calculation?

3. Change the program to also accept space‑separated values in addition
   to comma‑separated values.  Hint: replace commas with spaces and
   split on whitespace.

4. Instead of reading from user input, write a version of the script that
   reads numbers from a text file (one number per line).  Use the file
   handling techniques from Day 17【363542897074291†L362-L378】.

## Key Takeaway

A complete program integrates many individual concepts.  By writing a
command‑line application that parses input, manipulates lists, uses loops
and built‑in functions to compute statistics, and prints formatted output,
you demonstrate your mastery of the Python fundamentals learned in this
course.  This capstone project prepares you to tackle more complex tasks
in data modelling and building analytics.
