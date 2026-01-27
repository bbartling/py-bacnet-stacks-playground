# Day 02 – Variables & Arithmetic

## Goal

Learn how to store values in variables and perform arithmetic operations.  By
the end of this lesson you’ll be able to write simple Python expressions to
calculate sums, differences, products, divisions, remainders and powers, and
assign the results to descriptive variable names.

## Concept

In Python you assign a value to a variable using the `=` operator.  Variable
names can contain letters, digits and underscores but must not start with a
digit.  Comments begin with a `#` and extend to the end of the line【369182417897566†L67-L82】,
allowing you to document your code.

Python’s arithmetic operators follow mathematical notation.  The plus (`+`),
minus (`-`), multiplication (`*`) and division (`/`) operators behave as
expected【369182417897566†L91-L105】.  Division always returns a floating‑point
result—`7/2` yields `3.5`.  Floor division (`//`) drops the fractional part and
returns the largest integer less than or equal to the result, while the
modulo operator (`%`) returns the remainder【369182417897566†L111-L124】.  The
exponentiation operator (`**`) raises the left operand to the power of the
right operand【369182417897566†L117-L133】.

## How to Use It

1. **Assign variables.**  Use `=` to bind a value to a name:

   ```python
   width = 20  # variable names are case sensitive
   height = 5.0
   area = width * height
   ```

2. **Perform arithmetic.**  Combine numbers and variables using operators:

   ```python
   total = 50 - 5*6   # multiplication happens before subtraction
   result = (50 - 5*6) / 4  # parentheses change precedence
   floor = 17 // 3  # floor division yields 5
   remainder = 17 % 3  # remainder is 2
   power = 2 ** 7  # 2 to the 7th power = 128
   ```

3. **Use comments.**  Explain what your code does:

   ```python
   # Compute the volume of a box
   volume = width * height * 3
   ```

4. **Check types.**  Use `type()` to see the data type of a value:

   ```python
   print(type(width))   # <class 'int'>
   print(type(height))  # <class 'float'>
   ```

## Why This Matters

Variables make programs readable and maintainable: instead of repeating literal
numbers everywhere, you give them meaningful names.  Basic arithmetic
operators allow you to perform everyday calculations such as computing
temperature conversions, finding averages or scaling sensor readings.  Knowing
operator precedence and the difference between `/` and `//` will prevent
subtle bugs in your scripts.

## Mini Examples

Try these examples in a Python shell:

```python
# convert Fahrenheit to Celsius
fahrenheit = 77
celsius = (fahrenheit - 32) * 5/9
print(f"{fahrenheit}°F is {celsius:.1f}°C")

# calculate the area and perimeter of a rectangle
length = 4
width = 3
area = length * width
perimeter = 2 * (length + width)
print("Area:", area)
print("Perimeter:", perimeter)
```

## Micro Exercises

1. Assign two variables `a` and `b` with numeric values and compute their
   product, quotient and remainder.  Print the results.
2. Write a small script that calculates how many seconds are in a day using
   multiplication (`24 * 60 * 60`).  Store the result in a variable named
   `seconds_per_day` and print it.
3. Compute `3**4` using the exponent operator and verify your result using
   multiplication.

## Key Takeaway

Variables store values and arithmetic operators perform calculations.  Use
parentheses to control precedence and remember that `/` returns a float while
`//` performs floor division【369182417897566†L111-L124】.
