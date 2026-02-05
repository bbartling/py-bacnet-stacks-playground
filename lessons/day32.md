## Day 32 – String Algorithms

### Goal

Practise simple algorithms on strings, including concatenation, splitting, joining, reversing and palindrome checking. These tasks illustrate how to manipulate textual data efficiently.

### Concept

Python strings support many operations: `split()` divides a string into words and returns a list; `join()` concatenates an iterable of strings using the string as a separator; `strip()` removes leading/trailing characters; and `lower()` returns a lowercase copy. You can reverse a string by slicing `s[::-1]`. A string is a **palindrome** if it reads the same forwards and backwards (ignoring case and non‑alphanumeric characters).

### How to Use It

**Concatenation and joining:**

```python
# inefficient concatenation in a loop (avoid for large lists)
words = ['HVAC', 'data', 'model']
result = ''
for w in words:
    result += w + ' '
print(result.strip())

# efficient concatenation using join
sentence = ' '.join(words)
print(sentence)
```

**Splitting and stripping:**

```python
text = "  Temperature: 72, Humidity: 45  "
parts = text.strip().split(',')  # ['Temperature: 72', ' Humidity: 45']
```

**Reversing and palindrome check:**

```python
def is_palindrome(s):
    """Return True if s is a palindrome, ignoring case and non-letters."""
    cleaned = ''.join(c.lower() for c in s if c.isalnum())
    return cleaned == cleaned[::-1]

print(is_palindrome('Radar'))           # True
print(is_palindrome('BACnet'))          # False
print(is_palindrome('A man, a plan, a canal, Panama'))  # True
```

### Why This Matters

String manipulation is fundamental to programming. You’ll often parse CSV lines, build file paths or check for patterns in sensor names. Understanding efficient concatenation and basic algorithms like palindrome checking prepares you for more complex text processing.

### Mini Examples

- Use `split()` to parse a `name=value` pair and extract the value as a float.
- Use `join()` to combine a list of device names into a comma‑separated string.
- Write a function that counts the number of vowels in a string.

### Micro Exercises

1. Implement a function `reverse_words(sentence)` that returns a sentence with the words in reverse order. Hint: use `split()` and `join()`.
2. Write a function `count_char(s, char)` that counts how many times `char` appears in `s` (case insensitive).
3. Use the palindrome function above to check if user input is a palindrome and print an appropriate message.

### Key Takeaway

String methods like `split()`, `join()`, `strip()` and `lower()` are powerful tools for manipulating text. You can reverse strings with slicing and implement simple algorithms like palindrome detection with just a few lines of code.