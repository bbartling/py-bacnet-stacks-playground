# Day 11 – Introducing Dictionaries

## Goal

Learn how to create and use dictionaries to map keys to values.  By the end
of this lesson you’ll be able to define a dictionary, access and update
entries, test for membership and handle missing keys gracefully.

## Concept

A **dictionary** (sometimes called a *dict* or *hash map*) stores key–value
pairs.  Keys must be immutable types such as strings, numbers or tuples.
You create a dictionary using braces `{}` or the `dict()` constructor.  Access
and update values using square‑bracket indexing: `d[key] = value`.  Trying
to access a non‑existent key raises a `KeyError`; to avoid this, use
`get(key, default)` which returns a default if the key is missing【972561048532027†L550-L566】.
The `in` operator tests whether a dictionary contains a given key【972561048532027†L550-L566】.  The
function `list(d)` returns a list of the dictionary’s keys【972561048532027†L550-L566】.

## How to Use It

1. **Create dictionaries.**

   ```python
   empty = {}
   person = {'name': 'Alice', 'age': 30}
   device = dict(type='sensor', instance=1)
   ```

2. **Retrieve and update.**

   ```python
   print(person['name'])  # 'Alice'
   person['age'] = 31      # update value
   device['location'] = 'Zone1'  # add new key
   ```

3. **Check for keys.**  Use `in` to test membership:

   ```python
   if 'name' in person:
       print('Name is present')
   ```

4. **Handle missing keys.**  Use `get()` with a default to avoid exceptions
   when a key isn’t present【972561048532027†L550-L566】:

   ```python
   priority = device.get('priority', 16)  # returns 16 if no priority key
   ```

5. **Delete entries.**  Use `del` to remove a key:

   ```python
   del person['age']
   ```

## Why This Matters

Dictionaries are ideal for representing structured data such as BACnet
device objects where each point has a name, instance number and value.
Unlike lists, dictionaries provide constant‑time lookups by key.  Using
`get()` instead of indexing helps avoid crashes when optional metadata is
missing【972561048532027†L550-L566】.

## Mini Examples

```python
# build a point dictionary
point = {
    'name': 'ZoneTemp',
    'instance': 1,
    'value': 70.3
}
print(point['name'])       # 'ZoneTemp'
point['value'] = 71.0
point['unit'] = '°F'
print(point)

# handle missing key
print(point.get('priority', 'not set'))  # returns 'not set'

# membership test
print('instance' in point)  # True
```

## Micro Exercises

1. Create a dictionary named `device` with keys `'type'`, `'instance'` and
   `'address'`.  Populate it with appropriate values and print the
   dictionary.
2. Update the `'address'` key and add a new key `'status'` with value
   `'online'`.
3. Use `get()` to retrieve the `'priority'` of the device, providing a default
   of `16`.
4. Test whether the key `'instance'` exists in the dictionary using the `in`
   operator.

## Key Takeaway

Dictionaries store key–value pairs and provide fast lookups.  Use `d[key]`
to get or set values, `get(key, default)` to handle missing keys and the
`in` operator to test for membership【972561048532027†L550-L566】.
