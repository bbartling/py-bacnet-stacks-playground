# Day 03 – Working with Strings

*Part I: Fundamentals | Week 1*

## Goal

Understand how to create, manipulate and inspect text (strings) in Python.  By
the end of this lesson you’ll know how to build strings using quotes,
concatenate and repeat them, access individual characters, slice substrings and
measure string length.

## Concept

A **string** is a sequence of Unicode characters enclosed in single (`'...'`)
or double (`"..."`) quotes.  Python lets you embed quotes inside strings by
using different quote types or escaping with backslashes.
For multi‑line text, triple quotes (`'''` or `"""`) span several lines and
preserve line breaks.  Two string literals placed
adjacent to each other are automatically concatenated.
Strings support indexing and slicing: index 0 refers to the first character,
negative indices count from the end, and slicing syntax `[start:stop]` returns
the substring from `start` up to but not including `stop`.
The built‑in function `len()` returns the number of characters in a string.

## How to Use It

1. **Create strings.**  Use single or double quotes:

   ```python
   greeting = 'Hello, world!'
   quote = "She said, \"HVAC is cool!\""
   multiline = '''This is a multi‑line
   string with line breaks.'''
   ```

2. **Concatenate and repeat.**  Use `+` to join strings and `*` to repeat:

   ```python
   full = 'HVAC' + ' systems'  # 'HVAC systems'
   separator = '-'
   print(separator * 10)  # prints ----------
   ```

3. **Index and slice.**  Access characters and slices:

   ```python
   word = 'Bacnet'
   first = word[0]       # 'B'
   last = word[-1]       # 't'
   substring = word[1:4] # 'acn'
   ```

4. **Get the length.**  Use `len()`:

   ```python
   length = len(word)  # 6
   ```

5. **Raw strings.**  Prefix with `r` to disable escape sequences (useful for
   Windows file paths):

   ```python
   path = r'C:\Users\yourname\Documents'
   ```

## Why This Matters

Text is ubiquitous—file names, sensor identifiers, descriptions and labels
throughout building automation systems are strings.  Knowing how to build and
slice strings lets you extract meaningful information, assemble user messages
and process file paths.  Raw strings are particularly useful when working
with Windows directories or regular expressions, where backslashes would
otherwise need escaping.

## Mini Examples

```python
# build a sensor description
device = 'VAV'
point = 'Temperature'
description = device + ' ' + point
print(description)  # 'VAV Temperature'

# extract a prefix and suffix
serial = 'ABCD-1234-XYZ'
prefix = serial[:4]
suffix = serial[-3:]
print(prefix, suffix)  # 'ABCD' 'XYZ'

# create a Windows path without doubling backslashes
cfg_path = r'C:\ProgramData\MyApp\config.ini'
print(cfg_path)
```

## Micro Exercises

1. Create a string containing your full name.  Print the first and last
   characters using indexing.
2. Given the string `sentence = 'BACnet networks are everywhere'`, use slicing
   to extract `'net'` and `'every'`.
3. Use the `*` operator to print a dashed line (e.g., `'-' * 20`).
4. Create a raw string containing a Windows file path and print it to verify
   that backslashes aren’t interpreted as escape characters.

## Key Takeaway

Strings are sequences of characters.  Use quotes to create them, `+` and
`*` to concatenate and repeat them, and slicing to extract substrings.
The `len()` function returns the length of a string.

---

## Vibe Code Checkpoint 1 (Week 1)

Your BAC0 app uses **f-strings** to build address requests: `f"{address} {obj_type} {point_addr} present-value"`. String concatenation and formatting are how you assemble BACnet object references in Python — BAC0 handles the rest.

---

## Rust companion — Strings: `String` vs `&str`

*Same day as the Python lesson above. Work in `~/rust-lab` (create on Day 1).*

```rust
fn main() {
    let tag: &str = "AHU-1";           // string slice (borrowed, fixed)
    let mut name = String::from("Zone "); // owned, growable
    name.push_str("Temp");
    println!("{tag} / {name}");
    println!("len = {}", name.len());
    // indexing a single char is different than Python — use chars:
    for c in name.chars().take(3) {
        print!("{c}");
    }
    println!();
}
```

| Python | Rust |
|--------|------|
| `s = "hi"` | often `&str` or `String` |
| `s + "x"` | `format!("{s}x")` or `push_str` |
| `s[0]` | not the same — use `.chars()` |

**Takeaway:** `&str` is a view; `String` owns the data. You will see both in every network API.

