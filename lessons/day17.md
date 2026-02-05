# Day 17 – Reading & Writing Files

*Part II: Control Structures | Week 3*

## Goal

Learn how to **read from** and **write to** text files using Python's
`open()` function and the `with` statement. By the end of this lesson
you'll know how to process sensor logs or create simple data files.

## Concept

Python's built-in `open()` function returns a file object and is
commonly called with a filename and a mode. The mode can be `'r'` for
reading, `'w'` for writing (truncating the file), `'a'` for appending,
or `'r+'` for reading and writing. Files are opened in text mode by
default; add `'b'` to open in binary mode. Specify `encoding="utf-8"` for
text files.

When working with files, use the `with` statement so the file is
properly closed even if an error occurs. The file object provides
methods like `read()`, `readline()`, `readlines()`, and `write()`.

## How to Use It

**Writing to a file:**

```python
data = ['ZoneTemp,72', 'ZoneFlow,450', 'ZoneHumidity,45']

with open('sensors.csv', 'w', encoding='utf-8') as f:
    for line in data:
        f.write(line + '\n')
```

**Reading a file:**

```python
with open('sensors.csv', 'r', encoding='utf-8') as f:
    contents = f.read()
print(contents)

with open('sensors.csv', 'r', encoding='utf-8') as f:
    for line in f:
        print(line.strip())
```

**Appending to a file:**

```python
with open('sensors.csv', 'a', encoding='utf-8') as f:
    f.write('ZonePressure,1.2\n')
```

**Writing CSV with the csv module:**

```python
import csv
from datetime import date

filename = 'sensors_' + str(date.today()) + '.csv'
with open(filename, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['point', 'value', 'units'])
    writer.writerow(['ZoneTemp', 72.4, 'degF'])
```

## Why This Matters

Most real-world programs read or write data. In building automation you
may need to save sensor readings, write audit logs or import point
definitions from CSV files. Understanding file I/O lets you work with
text files reliably across platforms.

## Mini Examples

- Write a script that reads `site_scan.csv` (from your BACnet scan) and
  prints the first five lines.
- Create a text file `notes.txt` and append a new timestamped note each
  time the script runs.
- Read a configuration file line by line and ignore blank lines or lines
  starting with `#` (comments).

## Micro Exercises

1. Create a file `hello.txt` containing the text "Hello, Python!". Then
   write a script that reads the file and prints the content to the
   console.
2. Write a program that opens a file `numbers.txt`, reads each line as
   an integer, sums them up and prints the total.
3. Modify the script from exercise 2 to handle the case where the file
   does not exist by printing a friendly message instead of crashing.

## Key Takeaway

Use `open()` with an appropriate mode to obtain a file object. Always
wrap file operations in a `with` block so the file is closed
automatically. Use the `csv` module for CSV files: `csv.writer()` and
`csv.DictWriter()`.

---

## Vibe Code Checkpoint 2 (Week 2–3)

Your BAC0 data collection app will use the `csv` module to save readings
to a file. Use `open()` with `'w'` or `'a'` and `csv.writer()` or
`csv.DictWriter()`. Add **daily log rotation** — e.g. a new file per day
like `sensors_2026-02-05.csv`. Use `datetime.date.today()` to build the
filename. Something fancy for rotation is fine — the goal is persistent,
organised data.
