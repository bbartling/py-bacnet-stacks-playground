# Day 09 – Conditionals & While Loops

## Goal

Learn how to control the flow of your program using `if`/`elif`/`else`
statements and `while` loops.  You’ll also practise using `break` and
`continue` to fine‑tune loop behaviour.

## Concept

An `if` statement evaluates a condition and executes the corresponding block
of code if the condition is true.  You can chain multiple tests with
`elif` (short for “else if”) and end with an optional `else` for the
fall‑through case.  A `while` loop executes its body
repeatedly as long as its condition remains true.  In the Python tutorial, a
`while` loop generates the Fibonacci series until the value of the variable
`a` reaches 10.

The `break` statement immediately exits the nearest loop, and `continue`
skips the rest of the current iteration and proceeds to the next.

## How to Use It

1. **Use `if`/`elif`/`else`.**

   ```python
   temperature = 65
   if temperature < 60:
       print('Too cold')
   elif 60 <= temperature <= 75:
       print('Comfortable')
   else:
       print('Too hot')
   ```

2. **Use `while`.**  Keep looping until a condition is false:

   ```python
   count = 0
   while count < 5:
       print('count is', count)
       count += 1
   ```

3. **Infinite loops with `while True`.**  Use `break` to exit:

   ```python
   while True:
       command = input('Enter command (q to quit): ')
       if command == 'q':
           break  # exit the loop
       print('You entered', command)
   ```

4. **Skip iterations with `continue`.**

   ```python
   for n in range(10):
       if n % 2 == 0:
           continue  # skip even numbers
       print(n)      # prints only odd numbers
   ```

## Why This Matters

Conditionals let your program make decisions based on sensor values or
configuration options.  `while` loops are useful when you don’t know how
many iterations will be needed in advance—for example, reading lines from a
file until you hit the end.  Understanding `break` and `continue` helps you
control loops precisely and write efficient, readable code.

## Mini Examples

```python
# classify a BACnet priority level
priority = int(input('Enter priority (1–16): '))
if priority == 1:
    print('Manual life safety')
elif priority <= 5:
    print('Automatic high priority')
else:
    print('Normal priority')

# Fibonacci sequence with while
a, b = 0, 1
while b < 50:
    print(b, end=' ')
    a, b = b, a + b
print()

# find the first divisible number
number = 1
while True:
    if number % 7 == 0:
        print('First multiple of 7 is', number)
        break
    number += 1
```

## Micro Exercises

1. Write a program that prompts the user for a number and prints whether
   it is negative, zero or positive.
2. Use a `while` loop to compute the sum of numbers from 1 up to `n`
   (prompt the user for `n`).
3. Write a loop that prints the squares of numbers from 1 to 10 but
   skips squares greater than 50 using `continue`.
4. Prompt the user to enter a password until they type `'secret'`.

## Key Takeaway

Use `if`/`elif`/`else` to branch based on conditions,
`while` loops to repeat until a condition changes,
and `break` or `continue` to control loop execution.

---

## Rust companion — `if` / `else` and `while`

*Same day as the Python lesson above. Work in `~/rust-lab` (create on Day 1).*

```rust
fn main() {
    let pv = 85.0;
    if pv > 80.0 {
        println!("HIGH");
    } else if pv < 60.0 {
        println!("LOW");
    } else {
        println!("OK");
    }

    let mut n = 3;
    while n > 0 {
        println!("n={n}");
        n -= 1;
    }

    // if is an expression:
    let status = if pv > 80.0 { "alarm" } else { "normal" };
    println!("{status}");
}
```

**Takeaway:** No parentheses required around conditions. `if` can return a value.

