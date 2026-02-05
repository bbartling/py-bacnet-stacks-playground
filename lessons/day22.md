# Day 22 – Working with Nested Data

*Part III: Data Structures | Week 4*

## Goal

Learn how to manage **nested data structures** such as lists of dictionaries and dictionaries of lists. Practise iterating through nested structures with loops and extracting meaningful information.

## Concept

Real-world data is often hierarchical. A building may contain many rooms, each with its own set of sensors. Python allows nesting lists and dictionaries. Use nested `for` loops and `items()` to traverse and summarise nested data — no comprehensions.

## How to Use It

**List of dictionaries:**

```python
devices = [
    {'id': 1, 'name': 'VAV-1', 'points': {'temp': 72, 'flow': 450}},
    {'id': 2, 'name': 'VAV-2', 'points': {'temp': 70, 'flow': 430}},
]

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
    print(floor + ' has ' + str(len(rooms)) + ' rooms')
```

**Processing nested data with a loop:**

```python
# compute average temperature across all devices
temps = []
for d in devices:
    temps.append(d['points']['temp'])
avg = sum(temps) / len(temps)
print('Average temperature: ' + str(round(avg, 1)))
```

## Why This Matters

Building models and BACnet scans often involve nested structures: a site has buildings, buildings have floors, floors have rooms, rooms have points. Traversing nested collections with loops prepares you for CSV output from a BACnet discover script.

## Mini Examples

- Given a list of rooms, each with a dictionary of `temp` and `rh`, compute the average relative humidity using a loop.
- Transform a list of `(name, value)` tuples into a dictionary using a `for` loop.
- Flatten a dictionary of lists into a single list using nested loops.

## Micro Exercises

1. Create a list called `sensors` with three dictionaries. Each dictionary has keys `name` and `reading`. Loop over the list and print each sensor's name and reading.
2. Write a loop that produces a dictionary mapping each room in `['Room1', 'Room2', 'Room3']` to a default temperature of `72`.
3. Given `schedule = {'Mon': ['8am', '5pm'], 'Tue': ['9am', '6pm']}`, loop through the dictionary and print the day along with the start and end times.

## Key Takeaway

Nested data structures require nested loops to traverse. Use `items()` to loop over dictionaries and combine list and dictionary techniques to summarise complex data.
