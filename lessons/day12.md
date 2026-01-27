# Day 12 – Looping over Dictionaries & Comprehensions

## Goal

Discover how to iterate through dictionaries and build new dictionaries
efficiently.  By the end of this lesson you’ll be comfortable using
`items()`, `keys()`, `values()` and dictionary comprehensions.

## Concept

To loop over the key–value pairs in a dictionary, call its `items()` method
to return a view that can be iterated.  Similarly, `keys()` returns a view of
the keys and `values()` returns the values【972561048532027†L614-L640】.  A
dictionary comprehension creates a new dictionary from an iterable in a
concise way【972561048532027†L590-L612】.  For example, `{x: x**2 for x in
range(4)}` yields `{0: 0, 1: 1, 2: 4, 3: 9}`.

## How to Use It

1. **Iterate over items.**  Retrieve both keys and values:

   ```python
   sensors = {'ZoneTemp': 70.3, 'ZoneCoolingSpt': 72.0, 'ZoneDemand': 66.2}
   for name, value in sensors.items():
       print(name, '→', value)
   ```

2. **Iterate over keys or values.**

   ```python
   for name in sensors.keys():
       print(name)
   for value in sensors.values():
       print(value)
   ```

3. **Build a dictionary from two lists.**  Use `zip()` in a comprehension:

   ```python
   names = ['VAV1', 'VAV2', 'AHU']
   instances = [3456790, 3456789, 123456]
   devices = {name: inst for name, inst in zip(names, instances)}
   ```

4. **Invert a dictionary.**  Swap keys and values:

   ```python
   inv = {inst: name for name, inst in devices.items()}
   ```

5. **Filter entries.**  Use a comprehension with an `if` clause:

   ```python
   high_temp = {name: val for name, val in sensors.items() if val > 70}
   ```

## Why This Matters

Iterating over dictionaries and building them with comprehensions allows you
to transform data easily.  When mapping device names to instances or
filtering points based on their values, dictionary comprehensions keep your
code concise and readable.  Using `items()`, `keys()` and `values()`
provides clarity and avoids unnecessary indexing【972561048532027†L614-L640】.

## Mini Examples

```python
# count occurrences of each character in a string
text = 'BACnet'
freq = {}
for char in text:
    freq[char] = freq.get(char, 0) + 1
print(freq)  # {'B': 1, 'A': 1, 'C': 1, 'n': 1, 'e': 1, 't': 1}

# invert a mapping
points = {'ZoneTemp': 1, 'ZoneCoolingSpt': 2}
inverse = {v: k for k, v in points.items()}
print(inverse)

# build a dictionary of squares
squares = {n: n*n for n in range(1, 6)}
print(squares)
```

## Micro Exercises

1. Given `sensors = {'temp': 70, 'humidity': 45, 'pressure': 101}`, use a
   dictionary comprehension to convert the temperature to Celsius (`(F-32)*5/9`)
   and store the results in a new dictionary.
2. Create a list of tuples representing `(name, age)` for several people and
   build a dictionary mapping names to ages using a comprehension.
3. Given a dictionary mapping devices to instance numbers, invert it and
   print the result.
4. Write a loop that prints only the dictionary keys whose values are greater
   than 2.

## Key Takeaway

Use `items()`, `keys()` and `values()` to iterate through dictionaries and
dictionary comprehensions to build or transform them concisely【972561048532027†L590-L612】【972561048532027†L614-L640】.
