## Day 23 – Random Numbers & Math

### Goal

Use Python’s `random` and `math` modules to generate random data and
perform common mathematical operations.  These modules help you test
programs and perform calculations without writing your own functions.

### Concept

The `random` module provides functions for generating pseudo‑random
numbers.  You can pick a random element from a sequence with
`random.choice()`, generate random integers with `random.randint(a, b)`
and produce random floating‑point numbers between 0 and 1 with
`random.random()`.  The `math` module includes mathematical constants
(`math.pi`, `math.e`) and functions such as square root, floor/ceil,
trigonometry and logarithms.

### How to Use It

**Random functions:**

```python
import random

# random integer between 1 and 10 inclusive
n = random.randint(1, 10)
print(f"Random integer: {n}")

# random choice from a list
device = random.choice(['VAV-1', 'VAV-2', 'AHU-1'])
print(f"Random device: {device}")

# random float between 0 and 1
value = random.random()
print(f"Random float: {value:.3f}")
```

**Math functions:**

```python
import math

radius = 2.5
area = math.pi * radius ** 2
length = 10.7
print(math.floor(length))  # 10
print(math.ceil(length))   # 11
print(math.sqrt(16))       # 4.0
```

### Why This Matters

Random numbers are useful for testing algorithms, selecting random
samples and simulating sensor data.  Math functions let you compute
areas, lengths and other quantities without needing to derive formulas
yourself.  In HVAC modelling you might generate random setpoints for
testing or compute geometric properties of spaces.

### Mini Examples

- Use `random.sample()` to pick three unique rooms from a list of ten.
- Compute the circumference of a circle with radius 5 using `math.pi`.
- Generate five random temperature readings between 65 °F and 75 °F by
  scaling `random.random()`.

### Micro Exercises

1. Write a program that simulates rolling two six‑sided dice 100 times
   and counts how many times the sum is 7.
2. Use `math.sqrt()` to compute the distance between two points `(x1, y1)`
   and `(x2, y2)` entered by the user.
3. Create a list of ten random integers between 1 and 100 and sort it
   using `sorted()`; print the result.

### Key Takeaway

The `random` module generates pseudo‑random numbers for sampling and
testing.  The `math` module provides constants and functions for common
calculations.  Together they enable quick simulations and numeric
computations.