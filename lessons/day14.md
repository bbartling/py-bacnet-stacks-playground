## Day 14 – Advanced Loops & Sentinels

### Goal

Practise using `for` and `while` loops beyond the basics.  You will learn how
to write **nested loops**, use `while True` with a sentinel to terminate
input, and control loop execution with `break` and `continue`.

### Concept

Python’s `for` statement iterates over the items of a sequence, such as a
list or string【361868988149850†L107-L124】.  You can nest loops to process
multi‑dimensional data (for example, iterating over rows and columns of a
matrix).  A `while` loop runs until its condition becomes false; in many
programs you don’t know in advance how many iterations are required.  The
Fibonacci example in the tutorial demonstrates that a `while` loop continues
as long as the condition remains true【690482164421068†L593-L633】.

Sometimes you need an *indefinite loop* that repeatedly asks the user for
input until they signal that they’re done.  Using `while True` creates an
infinite loop; you exit it by calling `break` when a sentinel value is
entered.  Python’s `break` statement exits the nearest enclosing loop and
`continue` skips to the next iteration【361868988149850†L224-L259】.

### How to Use It

**Nested loops:**

```python
# generate a multiplication table
for i in range(1, 4):
    for j in range(1, 4):
        print(f"{i} × {j} = {i*j}")
    print()  # blank line between rows
```

**Sentinel loops:**

```python
while True:
    name = input("Enter a device name (or 'quit' to stop): ")
    if name == 'quit':
        break  # exit the loop
    print(f"You entered: {name}")
```

**Break and continue:**

```python
# skip over negative numbers
numbers = [3, -1, 4, -2, 5]
for n in numbers:
    if n < 0:
        continue  # skip the rest of the loop body
    print(n)
```

### Why This Matters

Real programs often need to loop until a certain condition is met.  HVAC
monitoring scripts might read sensor values continuously until an operator
stops the program.  Understanding sentinel loops and control statements
ensures your code can handle unknown amounts of data gracefully.  Nested
loops are essential when dealing with tables of information, such as rooms
versus equipment.

### Mini Examples

- Write a loop that keeps asking the user for temperatures until they type
  `'done'`, then prints the average.
- Use nested loops to print every combination of floors (1–3) and rooms
  (1–2) in a building.
- Modify a list of numbers by replacing all negative values with `0` using
  `continue`.

### Micro Exercises

1. Create a `while True` loop that reads lines from the user until they
   enter an empty string (press Enter).  Each time, print the length of
   the string.  When the empty string is entered, exit the loop with
   `break`.
2. Use nested `for` loops to print a 4 × 4 grid of coordinates `(row,
   column)` starting from `(0,0)`.
3. Given a list `values = [10, -5, 20, -3, 7]`, use a `for` loop with
   `continue` to print only the positive numbers.

### Key Takeaway

Use nested loops to handle multi‑dimensional data and `while True` loops
with a sentinel value to process input of unknown length.  `break`
terminates a loop early, and `continue` skips to the next iteration【361868988149850†L224-L259】.