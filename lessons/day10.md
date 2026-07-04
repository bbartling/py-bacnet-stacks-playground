# Day 10 – String Methods: Split, Join & Case Conversion

## Goal

Learn to break strings apart, put them back together and transform their
case.  By the end of this lesson you’ll be able to use `split()`,
`join()`, `strip()` and `lower()` to process text.

## Concept

Python’s string objects provide many useful methods for common text
operations.  The `str.split()` method returns a list of words in the string,
using an optional separator to determine where to split.
If no separator is provided, runs of whitespace are treated as a single
separator and empty results are suppressed.  The
`str.join()` method performs the inverse operation: it concatenates the
strings in an iterable, inserting the string it is called on between
elements and returning the result.  The
`str.strip()` method removes leading and trailing characters (defaulting to
whitespace), and `str.lower()` returns a copy of
the string with all cased characters converted to lowercase.

## How to Use It

1. **Split strings.**  Break a sentence into words:

   ```python
   sentence = 'BACnet networks are everywhere'
   words = sentence.split()  # ['BACnet', 'networks', 'are', 'everywhere']
   data = '3456,1234,5678'
   parts = data.split(',')  # ['3456', '1234', '5678']
   ```

2. **Join strings.**  Reassemble a list into a single string:

   ```python
   csv = ','.join(parts)  # '3456,1234,5678'
   dashed = '-'.join(['a', 'b', 'c'])  # 'a-b-c'
   ```

3. **Strip whitespace.**  Remove leading/trailing characters:

   ```python
   messy = '   HVAC   '
   clean = messy.strip()  # 'HVAC'
   url = 'www.example.com'.strip('w.')  # 'example.com'
   ```

4. **Change case.**  Convert to lowercase (useful for case‑insensitive
   comparisons):

   ```python
   device = 'VaV'
   print(device.lower())  # 'vav'
   ```

5. **Chain methods.**  Combine operations:

   ```python
   raw = '  SENSOR1;SENSOR2;SENSOR3  '
   sensors = raw.strip().split(';')
   lower_sensors = []
   for s in sensors:
       lower_sensors.append(s.lower())
   result = ', '.join(lower_sensors)  # 'sensor1, sensor2, sensor3'
   ```

## Why This Matters

Many data sources represent information as text separated by commas or other
delimiters.  Being able to split strings into lists, strip unwanted
characters and join pieces back together is essential for parsing CSV files
or user input.  Converting to a consistent case simplifies comparisons and
dictionary lookups.

## Mini Examples

```python
# parse a line from a CSV file
line = 'device,instance,name'
fields = line.split(',')
print(fields)

# join parts into a path
folders = ['home', 'user', 'documents']
path = '/'.join(folders)
print(path)

# clean up and normalize
text = '  BoIlEr  '
normalized = text.strip().lower()
print(normalized)  # 'boiler'
```

## Micro Exercises

1. Given the string `'one,two,,three,'`, call `split(',')` and observe the
   empty strings in the result.  How would you remove the empties?
2. Split the sentence `'BACnet uses UDP'` into words and then join them with
   underscores to produce `'BACnet_uses_UDP'`.
3. Take a user‑entered string with extra spaces and convert it to lowercase
   after stripping whitespace.
4. Combine `split()` and `join()` to reverse the order of words in a
   sentence.

## Key Takeaway

Use `split()` to break a string into parts,
`join()` to concatenate an iterable of strings with a separator,
`strip()` to remove leading and trailing characters,
and `lower()` to normalise case.

---

## Rust companion — String split / case

*Same day as the Python lesson above. Work in `~/rust-lab` (create on Day 1).*

```rust
fn main() {
    let line = "AHU-1,SAT,72.5";
    let parts: Vec<&str> = line.split(',').collect();
    println!("{:?}", parts);
    let upper = "zone".to_uppercase();
    println!("{upper}");
    let joined = parts.join("|");
    println!("{joined}");
}
```

**Takeaway:** `.split` gives an iterator; `.collect()` builds a `Vec` when you need one.

