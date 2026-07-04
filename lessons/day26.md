# Day 26 – Week 4 Review Project

*Part III: Data Structures | Week 4*

## Goal

Apply the concepts from Week 4 — built-in functions, slicing, string formatting, nested data — in a small project. Use loops only (no comprehensions). This exercise prepares you for the algorithms week.

## Concept

You have learned to use built-in functions like `sorted()`, `min()` and `max()`, slice sequences, format strings with f-strings, and process nested data with loops. The review project combines these skills to summarise sensor data and generate a simple report.

## How to Use It

Create a script that performs the following steps:

1. Define a list of dictionaries called `points`, where each dictionary has keys `name`, `reading` and `units` (e.g. `'Temp'`, `72.4`, `'°F'`).
2. Use a `for` loop to create a new list of Celsius readings by converting Fahrenheit values.
3. Compute the minimum, maximum and average of the Celsius readings using `min()`, `max()` and `sum()`/`len()`.
4. Sort the points by their readings in descending order using `sorted()` with `key` and `reverse=True`.
5. Print a formatted report using f-strings that lists each point (name, reading, units) and displays the summary statistics at the end.
6. Add docstrings to any helper functions and include comments for tricky parts.

## Why This Matters

Reviewing and consolidating your knowledge solidifies the skills you need for algorithmic thinking. Being able to transform data, compute statistics and present results is a cornerstone of data collection and BACnet CSV reports.

## Mini Examples

This project is the example — use your creativity to design your own list of points and decide how to format the report.

## Micro Exercises

1. Modify the script to handle a mixture of Fahrenheit and Celsius inputs by checking the `units` field and converting only if needed.
2. Use `any()` and `all()` to check whether any point's reading is above 25 °C and whether all points have the same units.
3. Write a function `report(points)` with a docstring that performs steps 2–5 and returns the summary statistics as a dictionary.

## Key Takeaway

Combining built-in functions, loops, slicing and nested data structures lets you process and summarise sensor data efficiently. Clear formatting and documentation make your results easy to read and maintain.

---

## Vibe Code Checkpoint 4 (Week 4)

Your **bacpypes3 discover → CSV** app should: send Who-Is, get I-Am responses, read each device's object-list, then for each object read object-name, description, present-value, units (where applicable). Write rows to a CSV with columns: device_id, object_identifier, object_type, object_instance, object_name, description, present_value, units. Reference the discover-objects-csv-only pattern — you vibe code your own version on YouTube!

---

## Rust companion — Week 4 review (Rust)

*Same day as the Python lesson above. Work in `~/rust-lab` (create on Day 1).*

Build `day26_review` that:

1. Holds a `HashMap<String, f64>` of point → PV
2. Prints all entries
3. Flags any PV outside 60..80
4. Writes a one-line summary with `format!`

**Takeaway:** Maps + loops + `if` cover a lot of commissioning scripts.

