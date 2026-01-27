## Day 30 – Counting Occurrences

### Goal

Learn how to count the number of occurrences of each item in a list using a dictionary. This algorithm builds a frequency table (also called a histogram) by iterating through the data once.

### Concept

A common task is to tally how many times each value appears in a collection. You can use a dictionary where the keys are the distinct items and the values are the counts. For each element, check whether it’s already a key in the dictionary; if so, increment the count; otherwise set the count to 1. At the end you have a mapping from items to their frequencies. This technique underlies functions like `collections.Counter`.

### How to Use It

**Counting items:**

```python
def count_occurrences(items):
    """Return a dictionary mapping each item to its count."""
    counts = {}
    for item in items:
        if item in counts:
            counts[item] += 1
        else:
            counts[item] = 1
    return counts

points = ['Temp', 'Flow', 'Temp', 'Humidity', 'Flow', 'Flow']
freq = count_occurrences(points)
print(freq)  # {'Temp': 2, 'Flow': 3, 'Humidity': 1}
```

**Iterating over the result:**

```python
for name, count in freq.items():
    print(f"{name}: {count}")
```

### Why This Matters

Counting occurrences helps summarise data quickly. When analysing BACnet scan results, you might want to know how many devices of each type were discovered or how many points each device has. Using a dictionary to build a frequency table prepares you for more advanced data analysis tasks.

### Mini Examples

- Count the number of times each character appears in a string.
- Build a frequency table of word lengths in a list of sentences.
- Create a dictionary counting how many devices have each priority assignment in a CSV scan.

### Micro Exercises

1. Write a function `word_frequency(sentence)` that returns a dictionary mapping each word to the number of times it appears in a sentence (split on whitespace).
2. Given a list of tuples `(device_type, instance)`, count how many devices of each type appear in the list.
3. Modify `count_occurrences` to ignore case by converting strings to lowercase before counting.

### Key Takeaway

Building a frequency table with a dictionary involves checking whether each item has been seen before and updating a count accordingly. This pattern is widely applicable for summarising data.