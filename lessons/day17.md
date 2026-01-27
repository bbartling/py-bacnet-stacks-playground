## Day 17 – Reading & Writing Files

### Goal

Learn how to **read from** and **write to** text files using Python’s
`open()` function and the `with` statement.  By the end of this lesson
you’ll know how to process sensor logs or create simple data files.

### Concept

Python’s built‑in `open()` function returns a file object and is
commonly called with a filename and a mode【363542897074291†L362-L378】.  The
mode can be `'r'` for reading, `'w'` for writing (truncating the file),
`'a'` for appending, or `'r+'` for reading and writing.  Files are
opened in text mode by default; add `'b'` to open in binary mode.
Because encoding differences matter, it’s recommended to specify
`encoding="utf-8"` for text files【363542897074291†L380-L387】.

When working with files, it is good practice to use the `with`
statement.  This ensures the file is properly closed even if an error
occurs【363542897074291†L396-L410】.  The file object provides methods
like `read()`, `readline()`, `readlines()`, and `write()` to read and
write data【363542897074291†L435-L447】【363542897074291†L451-L477】.

### How to Use It

**Writing to a file:**

```python
data = ['ZoneTemp,72', 'ZoneFlow,450', 'ZoneHumidity,45']

with open('sensors.csv', 'w', encoding='utf-8') as f:
    for line in data:
        f.write(line + '\n')
# file is automatically closed here
```

**Reading a file:**

```python
with open('sensors.csv', 'r', encoding='utf-8') as f:
    contents = f.read()  # reads entire file as one string
print(contents)

with open('sensors.csv', 'r', encoding='utf-8') as f:
    for line in f:
        print(line.strip())  # iterate over lines without trailing newline
```

**Appending to a file:**

```python
with open('sensors.csv', 'a', encoding='utf-8') as f:
    f.write('ZonePressure,1.2\n')
```

### Why This Matters

Most real‑world programs read or write data.  In building automation you
may need to save sensor readings, write audit logs or import point
definitions from CSV files.  Understanding file I/O lets you work with
text files reliably across platforms.

### Mini Examples

- Write a script that reads `site_scan.csv` (from your BACnet scan) and
  prints the first five lines.
- Create a text file `notes.txt` and append a new timestamped note each
  time the script runs.
- Read a configuration file line by line and ignore blank lines or lines
  starting with `#` (comments).

### Micro Exercises

1. Create a file `hello.txt` containing the text “Hello, Python!”.  Then
   write a script that reads the file and prints the content to the
   console.
2. Write a program that opens a file `numbers.txt`, reads each line as
   an integer, sums them up and prints the total.  (You can create
   `numbers.txt` manually with a few numbers on separate lines.)
3. Modify the script from exercise 2 to handle the case where the file
   does not exist by printing a friendly message instead of crashing.

### Key Takeaway

Use `open()` with an appropriate mode to obtain a file object【363542897074291†L362-L378】.
Always wrap file operations in a `with` block so the file is closed
automatically【363542897074291†L396-L410】.  Use methods like `read()`,
`readline()` and `write()` to process the file’s contents【363542897074291†L435-L447】.