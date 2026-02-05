# Day 12 – Looping over Dictionaries

*Part II: Control Structures | Week 2*

## Goal

Discover how to iterate through dictionaries using `items()`, `keys()`, and `values()`. By the end of this lesson you'll be comfortable looping over key–value pairs to process sensor data and device mappings.

## Concept

To loop over the key–value pairs in a dictionary, call its `items()` method. Similarly, `keys()` returns a view of the keys and `values()` returns the values. Use a plain `for` loop to build new dictionaries or filter entries — no comprehensions needed.

## How to Use It

1. **Iterate over items.** Retrieve both keys and values:

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

3. **Build a dictionary from two lists.** Use `zip()` in a loop:

   ```python
   names = ['VAV1', 'VAV2', 'AHU']
   instances = [3456790, 3456789, 123456]
   devices = {}
   for name, inst in zip(names, instances):
       devices[name] = inst
   ```

4. **Invert a dictionary.** Swap keys and values with a loop:

   ```python
   inv = {}
   for name, inst in devices.items():
       inv[inst] = name
   ```

5. **Filter entries.** Use a loop with an `if` clause:

   ```python
   high_temp = {}
   for name, val in sensors.items():
       if val > 70:
           high_temp[name] = val
   ```

## Why This Matters

Iterating over dictionaries lets you transform data for BACnet scans: map device names to instances, filter points by value, or build lookup tables. Using `items()`, `keys()` and `values()` keeps your code clear and avoids unnecessary indexing.

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
inverse = {}
for k, v in points.items():
    inverse[v] = k
print(inverse)

# build a dictionary of squares using a loop
squares = {}
for n in range(1, 6):
    squares[n] = n * n
print(squares)
```

## Micro Exercises

1. Given `sensors = {'temp': 70, 'humidity': 45, 'pressure': 101}`, use a loop to convert the temperature to Celsius (`(F-32)*5/9`) and store the results in a new dictionary.
2. Create two lists — names and ages — and build a dictionary mapping names to ages using a `for` loop and `zip()`.
3. Given a dictionary mapping devices to instance numbers, invert it with a loop and print the result.
4. Write a loop that prints only the dictionary keys whose values are greater than 2.

## Key Takeaway

Use `items()`, `keys()` and `values()` to iterate through dictionaries. Use plain `for` loops to build or transform dictionaries — clear and readable for HVAC data.

---

## Vibe Code Checkpoint 2 (Week 2–3)

Your BAC0 data collection app will use dictionaries to map device IDs to addresses (from Who-Is) and to store point names and readings. Looping over `items()` is how you'll process discovered devices and write rows to CSV.
