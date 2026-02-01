# Day 05 – User Input & Output

## Goal

Learn how to interact with users by reading input from the keyboard and
displaying formatted output.  By the end of this lesson you’ll be able to
prompt the user for information, convert their input to numbers and present
results clearly using f‑strings.

## Concept

The built‑in `input()` function writes an optional prompt to standard output,
reads a line from the user, strips the trailing newline and returns it as a
string.  You can then convert the returned string
to an integer or float using `int()` or `float()`.

To display information you use the `print()` function, which prints its
arguments separated by spaces followed by a newline.  Python also supports
**formatted string literals**, or *f‑strings*.  If you prefix a string with
`f` or `F`, expressions inside braces are evaluated and formatted at runtime.  F‑strings provide a concise way to combine text
and variables.

## How to Use It

1. **Prompt for input.**  Pass a prompt string to `input()`:

   ```python
   name = input('What is your name? ')
   ```

   The user’s reply is returned as a string.  Use `int()` or `float()` to
   convert numeric input:

   ```python
   age_str = input('How old are you? ')
   age = int(age_str)
   ```

2. **Print with f‑strings.**  Prefix a string with `f` and embed variables
   inside `{}`:

   ```python
   year = 2026
   event = 'course'
   print(f'Results of the {year} {event}')
   # Outputs: Results of the 2026 course
   ```

3. **Format numbers.**  Inside an f‑string you can specify format options after
   a colon, such as `.2f` for two decimal places:

   ```python
   value = 3.14159
   print(f'Pi ≈ {value:.2f}')  # Pi ≈ 3.14
   ```

4. **Combine input and output.**  Build interactive scripts:

   ```python
   temp_f = float(input('Enter temperature in °F: '))
   temp_c = (temp_f - 32) * 5/9
   print(f'{temp_f}°F is {temp_c:.1f}°C')
   ```

## Why This Matters

Interactive programs need to collect information from users and respond
appropriately.  Reading input and printing output are fundamental building
blocks for scripts such as configuration wizards, calculators or simple
command‑line tools.  F‑strings make it easy to embed variable values in
messages without cumbersome concatenation.

## Mini Examples

```python
# ask the user for a radius and compute the area of a circle
radius = float(input('Enter the radius: '))
area = 3.14159 * radius ** 2
print(f'Area = {area:.2f}')

# greeting program
name = input('Enter your first name: ')
print(f'Hello, {name}! Welcome to the Python mini challenge.')
```

## Micro Exercises

1. Write a script that asks the user for their height in inches and prints
   their height in centimeters (1 inch = 2.54 cm).
2. Prompt the user for two numbers, convert them to floats, and display
   their sum using an f‑string.
3. Ask the user to enter their favourite colour and then print the colour
   repeated three times separated by hyphens (e.g., `blue-blue-blue`).

## Key Takeaway

Use `input()` to read a line of text from the user,
convert it to the appropriate type, and display results with f‑strings for
clear formatting.
