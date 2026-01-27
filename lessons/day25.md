## Day 25 – Documentation, Comments & `help()`

### Goal

Discover how to write clear **docstrings** and comments in your code and
use Python’s built‑in `help()` function to explore modules and
functions.  Good documentation makes your code easier to understand and
maintain.

### Concept

Documentation comes in two main forms: **comments** and **docstrings**.
Comments start with `#` and continue to the end of the line【369182417897566†L67-L82】; they
explain the *why* behind your code.  A docstring is a string literal
that appears as the first statement in a module, function, class or
method.  Python stores the docstring in the object’s `__doc__`
attribute and uses it when you call `help()`.

The `help()` function displays the documentation of an object.  You can
call `help(function)` or use it at the interactive prompt to explore
modules.  Good docstrings follow conventions described in PEP 257 and
begin with a short summary line, followed by a more detailed
explanation.

### How to Use It

**Comments and docstrings:**

```python
def fahrenheit_to_celsius(f):
    """Convert a Fahrenheit temperature to Celsius.

    Args:
        f (float): Temperature in degrees Fahrenheit.

    Returns:
        float: Temperature in degrees Celsius.
    """
    # apply the conversion formula
    return (f - 32) * 5/9

# This is a comment explaining the next line
result = fahrenheit_to_celsius(68)
```

**Using `help()`:**

```python
import math

# get help on the math module
help(math)

# get help on a specific function
help(math.sqrt)

# view a function’s docstring directly
print(fahrenheit_to_celsius.__doc__)
```

### Why This Matters

Clear documentation helps others (and your future self) understand what
your code is doing.  Comments provide context that code alone cannot
convey, and docstrings enable automatic tools and the interactive
interpreter to display usage information.  In collaborative projects,
good documentation reduces bugs and accelerates onboarding.

### Mini Examples

- Write a docstring for a function `area_of_circle(r)` that explains the
  formula and parameters.
- Use `help(random.choice)` to learn about the parameters and return
  value of `choice()`.
- Write a brief comment in a script explaining why a particular magic
  number (constant) is used.

### Micro Exercises

1. Add a docstring to your `sum_list()` function from Day 15 that
   describes what it does and its parameters.
2. Use `help(str.split)` to view documentation for the `split()` method.
3. Write a script that defines a function with an empty body using
   `pass` and a docstring explaining that the function will be
   implemented later.

### Key Takeaway

Comments and docstrings explain *why* and *how* your code works.  Use
`help()` to explore modules and functions and check your own
docstrings.  Clear documentation makes your code more maintainable and
user‑friendly【369182417897566†L67-L82】.