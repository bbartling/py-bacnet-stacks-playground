## Day 19 – Week 3 Review Project

### Goal

Consolidate the concepts you’ve learned in Week 3 by building a small
program that reads data from a file, processes it with functions and
handles errors gracefully.  This mini project should take about
20 minutes and reinforces your understanding of modules, file I/O and
exception handling.

### Concept

In the previous days you learned how to define functions【361868988149850†L540-L624】,
import modules【583691231774654†L61-L73】, read and write files【363542897074291†L362-L378】 and
handle errors with `try`/`except`【733975047827136†L135-L166】.  Today you’ll combine
those skills.  The project asks you to read a CSV file of sensor
readings, compute statistics using functions, and gracefully handle
missing files or bad data.

### How to Use It

Follow these steps:

1. Create a file called `data.csv` containing lines like `ZoneTemp,72` and
   `ZoneHumidity,45`.  Each line has a sensor name and a numeric
   reading separated by a comma.
2. Write a Python script that defines two functions:
   
   * `read_data(filename)`: opens the file, reads each line, splits on the comma
     and returns a list of `(name, value)` tuples.  Use a `try`/`except`
     block to handle `FileNotFoundError` and print an error if the file
     doesn’t exist.
   * `compute_average(values)`: takes a list of numbers and returns their
     average.  Use a loop and your own sum rather than Python’s built‑in
     `sum`.
3. In the `main` part of your script, call `read_data('data.csv')`.  If
   data is returned, extract the numeric values, convert them to
   floats and call `compute_average()` to compute the average reading.
4. Print the result with a descriptive message.  If the file is missing
   or contains invalid numbers, handle these cases gracefully.

### Why This Matters

Programming is about combining simple building blocks into useful
applications.  This project simulates reading sensor data, a common
requirement in HVAC and building automation.  By writing functions you
create reusable components; by handling errors you make the program robust.

### Mini Examples

This project is itself the example.  Focus on breaking the problem down
into small steps—reading data, processing it and reporting results.

### Micro Exercises

1. Extend your script to compute not only the average but also the
   minimum and maximum values using loops or Python’s `min()` and
   `max()` built‑ins【329836770204326†L1277-L1294】.
2. Modify `read_data()` to skip lines that don’t contain a comma.
3. Split your script into a module with the functions and a separate
   file that imports the module and calls the functions.  Run both
   files.

### Key Takeaway

Pulling together functions, modules, file I/O and error handling lets
you build useful scripts.  Practice reading data, processing it and
handling problems gracefully to prepare for more advanced modelling tasks.