## Day 16 – Modules & the Standard Library

### Goal

Learn how to organise code into reusable **modules** and access the
Python **standard library**.  You will import functions from built‑in
modules like `math` and `random` and write your own simple module.

### Concept

A **module** is a file containing Python definitions and statements.  The
Python tutorial notes that modules allow you to split your program into
several files and reuse functions in multiple programs.
You import a module using the `import` statement.  This adds the module
name to your program’s namespace; you can then access functions and
variables with `module.name`.  A variant of the import statement allows
you to import specific attributes directly into your namespace.
The standard library provides many useful modules for mathematics, random
numbers, date/time, and more.

### How to Use It

**Importing standard modules:**

```python
import math
import random

# using functions from math
radius = 5
circumference = 2 * math.pi * radius
root = math.sqrt(16)  # 4.0

# using functions from random
coin = random.choice(['heads', 'tails'])
dice = random.randint(1, 6)
```

**Importing specific functions:**

```python
from math import sqrt, pi

print(sqrt(25))  # 5.0
print(pi)        # 3.1415926535...
```

**Writing your own module:**

Create a file named `utils.py` in the same directory as your script and
define a function:

```python
# utils.py
def celsius_to_fahrenheit(c):
    """Convert Celsius to Fahrenheit."""
    return (c * 9/5) + 32
```

Then import and use it:

```python
import utils
print(utils.celsius_to_fahrenheit(20))
```

### Why This Matters

Modules help you organise code and avoid repeating yourself.  The
standard library provides reliable tools for common tasks so you don’t
have to reinvent the wheel.  Building automation tasks often need
mathematical functions (`math.sqrt`), random selections for test data
(`random.choice`) or date/time handling; learning to import modules lets
you leverage these capabilities immediately.

### Mini Examples

- Use `math.floor()` and `math.ceil()` to round a floating‑point HVAC
  setpoint down and up, respectively.
- Generate a random sample of 3 sensor names from a list using
  `random.sample()`.
- Write a module `conversions.py` with functions to convert feet to
  metres and kilograms to pounds; import and test them.

### Micro Exercises

1. Import the `statistics` module and use `statistics.mean()` to
   calculate the average of the list `[72, 75, 68, 70]`.
2. Use `from random import randint` to generate and print ten random
   integers between 1 and 100.
3. Create a file `mytools.py` with a function `fahrenheit_to_celsius(f)`
   and then write a separate script that imports `mytools` and calls the
   function.

### Key Takeaway

Modules allow you to split your program into multiple files and reuse
code.  You import standard modules like `math` and `random` to access
additional functions, or write your own modules for your projects.

---

## Rust companion — Modules and `use`

*Same day as the Python lesson above. Work in `~/rust-lab` (create on Day 1).*

```rust
use std::f64::consts::PI;

fn main() {
    println!("pi ≈ {PI}");
    // crates = libraries; add to Cargo.toml later, e.g. serde
}
```

| Python | Rust |
|--------|------|
| `import math` | `use std::...` |
| `pip install x` | add to `Cargo.toml` `[dependencies]` |

**Takeaway:** `std` is always available; third-party crates go in `Cargo.toml`.

