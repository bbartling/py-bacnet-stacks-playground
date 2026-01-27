## Day 21 – Slicing & String Formatting

### Goal

Improve your ability to work with sequences by practising **slicing** and reviewing Python’s string formatting options, including f‑strings.

### Concept

**Slicing** allows you to extract a contiguous portion of a list or string using the syntax `seq[start:stop:step]`. Both `start` and `stop` are optional; negative indices count from the end. The Python tutorial shows that you can slice strings to obtain substrings and that strings and lists support indexing and slicing【126592705671557†L318-L426】. For example, `s[1:3]` returns characters at positions 1 and 2.

String formatting lets you build readable output. An **f‑string** is a string literal prefixed with `f` that contains expressions in curly braces, which are evaluated at runtime. The Input/Output section of the tutorial demonstrates that prefixing a string with `f` and embedding expressions like `{year}` produces formatted results【363542897074291†L73-L84】. You can also use the `format()` method or old‑style `%` formatting, but f‑strings are the most concise.

### How to Use It

**Slicing sequences:**

```python
numbers = [0, 1, 2, 3, 4, 5]
print(numbers[1:4])    # [1, 2, 3]
print(numbers[:3])     # [0, 1, 2]
print(numbers[3:])     # [3, 4, 5]
print(numbers[-3:])    # last three elements
print(numbers[::2])    # every second element [0, 2, 4]
print(numbers[::-1])   # reversed list

s = "HVAC"
print(s[1:3])  # 'VA'
```

**String formatting with f‑strings:**

```python
year = 2026
event = 'HVAC conference'
print(f"Results of the {year} {event}")  # Results of the 2026 HVAC conference

temperature = 72.456
print(f"{temperature:.1f}°F")  # 72.5°F with one decimal place
```

### Why This Matters

Being comfortable with slicing lets you quickly extract or modify parts of sequences. Reversing lists, skipping every other element or taking substrings are common operations in data processing. F‑strings make it easy to build human‑readable output—crucial when reporting sensor values or constructing file names.

### Mini Examples

- Extract the domain from the email `info@hvac.example.com` using slicing.
- Reverse a string entered by the user using `s[::-1]`.
- Use an f‑string to display a temperature and humidity reading such as `f"Temp: {temp}°F, Humidity: {rh}%"`.

### Micro Exercises

1. Given `phrase = "BACnet Data"`, slice it to produce `"BAC"` and `"Data"`.
2. Use slicing to create a copy of a list and then modify the copy without altering the original.
3. Write a formatted string that prints the filename and size (in kilobytes) of a file using variables `name` and `size`.

### Key Takeaway

Slicing allows you to extract portions of sequences and reverse them easily【126592705671557†L318-L426】. F‑strings provide concise, readable string formatting for embedding variable values in output【363542897074291†L73-L84】.