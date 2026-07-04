# Day 06 – Introducing Lists

*Part I: Fundamentals | Week 1*

## Goal

Learn how to work with Python’s list data type.  By the end of this lesson
you’ll be able to create lists, access their elements by index, slice them to
obtain sublists and use basic methods like `append()` and `len()`.

## Concept

Lists are ordered collections of items and are created by placing comma‑
separated values inside square brackets.  Items can
be of any type and lists can even contain other lists.  Like strings, lists
support indexing and slicing; index 0 refers to the first element, negative
indices count from the end and the slice notation `[start:stop]` returns a
new list containing items from `start` up to but not including `stop`.  Lists are **mutable**: you can change, add or
remove elements after creation.  The built‑in
function `len()` returns the number of items in a list.

## How to Use It

1. **Create lists.**  Use square brackets or the `list()` constructor:

   ```python
   empty = []
   numbers = [10, 20, 30]
   mixed = ['sensor', 42, True]
   chars = list('BACnet')  # ['B','A','C','n','e','t']
   ```

2. **Index and slice.**  Access items by index and obtain sublists:

   ```python
   print(numbers[0])   # 10
   print(numbers[-1])  # 30
   sub = numbers[1:3]  # [20, 30]
   ```

3. **Modify elements.**  Assign to an index to change a value:

   ```python
   numbers[1] = 25  # numbers becomes [10, 25, 30]
   ```

4. **Append items.**  Use `append()` to add a single element to the end of
   a list:

   ```python
   sensors = ['temp', 'humidity']
   sensors.append('pressure')  # ['temp', 'humidity', 'pressure']
   ```

5. **Find the length.**  Use `len()` to count items:

   ```python
   count = len(sensors)  # 3
   ```

## Why This Matters

Lists are the workhorse of Python programming.  They allow you to store
collections of values such as sensor IDs, device instances or temperature
readings.  Being able to index, slice and modify lists lays the foundation
for data processing tasks you will encounter later in the course.

## Mini Examples

```python
# create a list of device instance numbers
devices = [3456789, 3456790, 123456]
print('First device:', devices[0])
print('Last device:', devices[-1])

# slice the list to get the first two
first_two = devices[:2]
print(first_two)

# modify an element
devices[2] = 999999
print(devices)

# build a dynamic list of discovered devices
discovered = []
discovered.append('VAV1')
discovered.append('AHU1')
print(discovered)
```

## Micro Exercises

1. Create a list called `temps` containing the values `70`, `68`, `72`, `69`.
   Print the first and last temperature.
2. Use slicing to extract the middle two values from `temps`.
3. Change the second value in `temps` to `71` and append `75` to the end.
4. Create a list from the word `'HVAC'` using `list()` and print its length.

## Key Takeaway

Lists are ordered, mutable sequences.  Use indexing and slicing to access
elements, `append()` to add items and `len()` to measure the list’s size.

---

## Rust companion — Vectors (`Vec`) — like lists

*Same day as the Python lesson above. Work in `~/rust-lab` (create on Day 1).*

```rust
fn main() {
    let mut temps = vec![70.0, 71.5, 69.0];
    temps.push(72.0);
    println!("first = {}", temps[0]);
    println!("len = {}", temps.len());
    println!("last = {:?}", temps.last());
}
```

| Python `list` | Rust `Vec<T>` |
|---------------|---------------|
| `[1, 2]` | `vec![1, 2]` |
| `.append(x)` | `.push(x)` |
| `len(a)` | `a.len()` |

**Takeaway:** `Vec` is your default growable list. Type is `Vec<f64>`, `Vec<String>`, etc.

