## Day 15 – Writing Functions

### Goal

Learn how to encapsulate code into **functions**. Functions let you organise repetitive tasks, accept parameters and return results. By the end of this lesson you’ll be able to define your own functions, call them with arguments and write docstrings for documentation.

### Concept

A function is defined using the `def` keyword followed by the function name, parentheses enclosing any parameters, and a colon. The body of the function must be indented. You can include a **docstring** (a string literal on the first line of the body) to describe what the function does. Functions return `None` by default, but you can use the `return` statement to send a value back to the caller. The Python tutorial explains that defining functions creates a new local scope and parameters are passed by assignment; if no `return` is executed, the function returns `None`.

### How to Use It

**Defining a function:**

```python
def greet(name):
    """Print a personalised greeting."""
    print(f"Hello, {name}!")

# calling the function
greet("HVAC technician")
```

**Returning a value:**

```python
def square(n):
    """Return the square of n."""
    return n * n

result = square(5)  # result is 25
```

**Default arguments:**

```python
def repeat(message, times=2):
    """Repeat the message a given number of times (default is 2)."""
    for _ in range(times):
        print(message)

repeat("Test")      # prints 'Test' twice
repeat("Echo", 3)  # prints 'Echo' three times
```

### Why This Matters

Functions let you divide a program into reusable blocks, which makes maintenance easier and prevents code duplication. For building automation scripts, you might define a function to compute the average temperature from a list of sensors, or to convert Fahrenheit to Celsius. Clear docstrings help others understand what your functions do.

### Mini Examples

- Define a function `c_to_f(celsius)` that converts Celsius to Fahrenheit.
- Write a function `is_even(n)` that returns `True` if `n` is even and `False` otherwise.
- Create a function `sum_list(numbers)` that loops over a list of numbers and returns the sum (don’t use Python’s built‑in `sum` yet!).

### Micro Exercises

1. Define a function `say_hello()` that prints “Hello!” every time it is called. Try calling it multiple times.
2. Write a function `fahrenheit_to_celsius(f)` that returns the temperature in Celsius. Use the formula `(f - 32) * 5/9`.
3. Modify the `repeat` function above so that it returns a single string containing the repeated message separated by spaces instead of printing it.

### Key Takeaway

Use `def` to define functions with optional parameters and docstrings. Return values with `return` when needed. Functions provide reusable building blocks and separate logic into manageable pieces.

---

## Rust companion — Functions `fn`

*Same day as the Python lesson above. Work in `~/rust-lab` (create on Day 1).*

```rust
fn c_to_f(c: f64) -> f64 {
    c * 9.0 / 5.0 + 32.0
}

fn greet(name: &str) {
    println!("Hello, {name}");
}

fn main() {
    greet("tech");
    println!("{}", c_to_f(22.0));
}
```

| Python | Rust |
|--------|------|
| `def f(x):` | `fn f(x: Type) -> Ret` |
| docstring | `///` doc comments |
| return optional | return type required if not `()` |

**Takeaway:** Types on parameters and return values are normal — the compiler helps you.

