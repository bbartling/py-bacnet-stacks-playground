## Day 26 – Week 4 Review Project

### Goal

Apply the concepts from Week 4—built‑in functions, slicing, string
formatting, nested data, higher‑order functions and documentation—in a
small project.  This exercise prepares you for the final week of
algorithms by ensuring you’re comfortable with Python’s expressive
features.

### Concept

In the past few days you learned to use built‑in functions like
`sorted()`, `min()` and `max()`【329836770204326†L1277-L1294】【329836770204326†L1876-L1894】, slice
sequences【126592705671557†L318-L426】, format strings with f‑strings【363542897074291†L73-L84】,
process nested data structures【972561048532027†L614-L640】 and use higher‑order
functions like `map()` and `filter()`.  You also wrote docstrings and
learned to consult documentation using `help()`.  The review project
combines these skills to summarise sensor data and generate a simple
report.

### How to Use It

Create a script that performs the following steps:

1. Define a list of dictionaries called `points`, where each dictionary
   has keys `name`, `reading` and `units` (e.g., `'Temp'`, `72.4`, `'°F'`).
2. Use a list comprehension to create a new list of Celsius readings by
   converting Fahrenheit values using a lambda function with `map()` or
   inside the comprehension.
3. Compute the minimum, maximum and average of the Celsius readings
   using `min()`, `max()` and `sum()`/`len()`.
4. Sort the points by their readings in descending order using
   `sorted()` with a `key` and `reverse=True`.
5. Print a formatted report using f‑strings that lists each point
   (name, reading and units) and displays the summary statistics at the end.
6. Add docstrings to any helper functions you create, and include
   comments explaining tricky parts of the code.

### Why This Matters

Reviewing and consolidating your knowledge solidifies the skills you
need for algorithmic thinking.  Being able to transform data, compute
statistics and present results is a cornerstone of many data science
tasks.  Good documentation ensures that others can understand your
code.

### Mini Examples

This project is the example—use your creativity to design your own list
of points and decide how to format the report.

### Micro Exercises

1. Modify the script to handle a mixture of Fahrenheit and Celsius
   inputs by checking the `units` field and converting only if needed.
2. Use `any()` and `all()` to check whether any point’s reading is
   above 25 °C and whether all points have the same units.
3. Write a function `report(points)` with a docstring that performs
   steps 2–5 above and returns the summary statistics as a dictionary.

### Key Takeaway

Combining built‑in functions, comprehensions, slicing and higher‑order
functions allows you to process and summarise nested data structures
efficiently.  Clear formatting and documentation make your results easy
to read and maintain.