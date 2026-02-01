# Day 04 – Numbers, Booleans & Comparisons

## Goal

Dive deeper into Python’s numeric types and explore Boolean values and
comparison operators.  By the end of this lesson you’ll know how to compare
values, use Boolean logic and convert between numeric types.

## Concept

Python supports several numeric types: integers (`int`), floating point
numbers (`float`) and complex numbers.  Integers have unlimited precision and
floats support fractional values.  Python also has a `bool` type, which is a
subclass of `int` and can be either `True` or `False`.
Anything with a non‑zero length or non‑zero numeric value is considered
**truthy**; empty sequences (`''`, `[]`, `{}`, `set()`, `range(0)`) and the
value `0` are considered **false**.

Comparison operators `<`, `<=`, `>`, `>=`, `==` and `!=` compare values and
return a Boolean result.  You can chain comparisons
(e.g., `0 < x <= 5`) and combine them with Boolean operators `and`, `or` and
`not` to build complex conditions.

## How to Use It

1. **Create numbers.**  Integers and floats are created by typing them directly:

   ```python
   count = 42
   temperature = 23.5
   ```

2. **Convert types.**  Use built‑in functions to convert between types:

   ```python
   num_str = '123'
   num_int = int(num_str)  # 123
   float_value = float('3.14')  # 3.14
   ```

3. **Compare values.**  Use comparison operators to compare numbers and strings:

   ```python
   x = 5
   print(x > 3)      # True
   print(x == 5)     # True
   print('a' < 'b')  # True (lexicographic comparison)
   ```

4. **Use Boolean logic.**  Combine conditions with `and`, `or`, `not`:

   ```python
   humidity = 60
   temperature = 28
   if temperature > 25 and humidity > 50:
       print('It is hot and humid!')
   ```

5. **Check truthiness.**  Use values directly in conditions:

   ```python
   items = []
   if not items:
       print('The list is empty')
   ```

## Why This Matters

Most programs need to make decisions: for example, you might want to trigger
an alarm when a temperature exceeds a set point or only process data if
lists are non‑empty.  Understanding comparison operators and Boolean logic
enables you to write these conditions correctly.  Knowing which values are
truthy or falsey helps avoid surprises when using objects in `if` and `while`
statements.

## Mini Examples

```python
# compare two temperatures
inside = 72
outside = 85
if outside > inside:
    print('It is warmer outside')
else:
    print('It is cooler or the same outside')

# demonstrate chained comparisons
score = 75
if 0 <= score <= 100:
    print('Score is within range')

# boolean logic with strings
user = ''
print(bool(user))      # False because the string is empty
user = 'admin'
print(bool(user))      # True because non‑empty
```

## Micro Exercises

1. Write an expression that evaluates to `True` only if a number `x` is
   between 10 and 20 inclusive.
2. Convert the string `'12.34'` to a float and add 5 to it.  What is the
   result?
3. Given two variables `a` and `b`, write a condition that prints `'equal'`
   when they have the same value and `'not equal'` otherwise.
4. Evaluate the truthiness of the following values: `0`, `''`, `[1]`, `{}`.

## Key Takeaway

Python has multiple numeric types and a dedicated Boolean type.  Use
comparison operators and Boolean logic to build conditions, and remember
that empty sequences and zero values evaluate to `False`.
