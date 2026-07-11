# Day 18 – Handling Errors Gracefully

## Goal

Learn how to use `try`/`except` blocks to handle runtime errors and
prevent your program from crashing unexpectedly.  You will practice
catching specific exceptions and using a sentinel loop that repeatedly
prompts for valid input.

## Concept

When a Python statement causes an error during execution, an **exception**
is raised.  Exceptions are not always fatal; you can handle them to
recover from errors.  The Python tutorial shows a pattern where a
`while` loop repeatedly prompts the user for input until a valid
integer is entered.  Within a `try` block you
place code that might fail.  If an exception occurs, execution jumps to
the corresponding `except` block.  The tutorial explains that the
`try` clause executes first; if an exception occurs and matches the
`except` clause, the handler runs and the loop continues.

## How to Use It

**Catching a specific exception:**

```python
while True:
    try:
        value = int(input("Enter a whole number: "))
        break
    except ValueError:
        print("Oops! That was not a valid integer. Try again...")

print(f"You entered {value}")
```

**Handling multiple exceptions:**

```python
try:
    f = open('numbers.txt')
    total = 0
    for line in f:
        total += int(line.strip())
except FileNotFoundError:
    print('numbers.txt not found.')
except ValueError:
    print('Could not convert data to an integer.')
finally:
    # the finally block runs whether or not an exception occurred
    try:
        f.close()
    except NameError:
        pass
```

## Why This Matters

Robust programs need to anticipate and handle errors gracefully.  In an
HVAC data acquisition script a sensor might return unexpected data or a
file might be missing; by catching exceptions you can log an error and
continue running rather than crashing.  This is especially important
when scripts need to run unattended on controllers or servers.

## Mini Examples

- Prompt the user for a filename, try to open it and report if it does not exist.
- Wrap a division operation in `try`/`except` to catch division by zero.
- Use a `try`/`except` block in a loop to ensure that the user enters a
  floating‑point number between 0 and 1.

## Micro Exercises

1. Write a program that asks the user for two integers and prints their
   quotient.  Use `try`/`except` to catch `ZeroDivisionError` if the
   second number is zero.
2. Modify the file summing program from Day 17 to catch
   `FileNotFoundError` and print a user‑friendly message instead of
   crashing.
3. Create a loop that asks the user to enter a positive number less
   than 100.  Use `try`/`except` and a `while True` loop to keep asking
   until a valid number is provided.

## Key Takeaway

Use `try`/`except` blocks to catch and handle exceptions.  Place code
that might fail in the `try` block and catch specific exceptions in
`except` clauses.  This allows your program to recover gracefully from
errors.

---

## Rust companion — Errors: `Result` and `Option` (preview)

*Same day as the Python lesson above. Work in `~/rust-lab` (create on Day 1).*

```rust
fn parse_pv(s: &str) -> Result<f64, std::num::ParseFloatError> {
    s.trim().parse()
}

fn main() {
    match parse_pv("72.5") {
        Ok(v) => println!("pv={v}"),
        Err(e) => println!("bad: {e}"),
    }
    let maybe: Option<f64> = None;
    println!("{:?}", maybe.unwrap_or(0.0));
}
```

| Python | Rust |
|--------|------|
| `try/except` | `Result<T, E>` + `match` |
| `None` | `Option<T>` (`Some` / `None`) |

**Takeaway:** Missing data → `Option`. Failure → `Result`. No silent `None` surprises later on the wire.

