## Day 22 – Working with Nested Data

### Goal

Learn how to manage **nested data structures** such as lists of
dictionaries and dictionaries of lists.  You will practise iterating
through nested structures and extracting meaningful information.

### Concept

Real‑world data is often hierarchical.  For example, a building may
contain many rooms, each with its own set of sensors.  Python allows
nesting lists and dictionaries arbitrarily.  You can loop over
dictionaries and use `items()` to obtain key–value pairs【972561048532027†L614-L640】.
Comprehensions can also build nested structures concisely.  When
processing nested data, nested loops and `enumerate()` are helpful for
tracking positions.

### How to Use It

**List of dictionaries:**

```python
devices = [
    {'id': 1, 'name': 'VAV-1', 'points': {'temp': 72, 'flow': 450}},
    {'id': 2, 'name': 'VAV-2', 'points': {'temp': 70, 'flow': 430}},
]

# iterate over devices
for device in devices:
    print(device['name'], device['points']['temp'])
```

**Dictionary of lists:**

```python
building = {
    'floor1': ['Room101', 'Room102'],
    'floor2': ['Room201', 'Room202'],
}

for floor, rooms in building.items():
    print(f"{floor} has {len(rooms)} rooms")
```

**Processing nested data:**

```python
# compute average temperature across all devices
temps = [d['points']['temp'] for d in devices]
avg = sum(temps) / len(temps)
print(f"Average temperature: {avg:.1f}")
```

### Why This Matters

Building models and sensor networks often involve nested structures: a
site contains buildings, buildings contain floors, floors contain rooms
and rooms contain points.  Being able to traverse and summarise nested
collections prepares you for working with complex datasets like the
`site_scan.csv` produced by a BACnet scan.  It also reinforces earlier
concepts such as loops, comprehensions and dictionaries.

### Mini Examples

- Given a list of rooms, each with a dictionary of `temp` and `rh`
  (relative humidity), compute the average relative humidity across all
  rooms.
- Transform a list of tuples `(name, value)` into a dictionary using a
  comprehension.
- Flatten a dictionary of lists into a single list of all items.

### Micro Exercises

1. Create a list called `sensors` containing three dictionaries.  Each
   dictionary should have keys `name` and `reading`.  Loop over the list
   and print each sensor’s name and reading.
2. Write a comprehension that produces a dictionary mapping each room in
   `['Room1', 'Room2', 'Room3']` to a default temperature of `72`.
3. Given `schedule = {'Mon': ['8am', '5pm'], 'Tue': ['9am', '6pm']}`,
   loop through the dictionary and print the day along with the start
   and end times.

### Key Takeaway

Nested data structures require nested loops or comprehensions to
traverse them.  Use `items()` to loop over dictionaries and combine
list and dictionary techniques to summarise complex data【972561048532027†L614-L640】.