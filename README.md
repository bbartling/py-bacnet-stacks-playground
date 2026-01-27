# Python Fundamentals Mini Challenge

Welcome to the **Python Fundamentals Mini Challenge**, a month‑long introduction to Python
aimed at engineers and building professionals who are new to programming.
Each daily lesson is designed to take about **20 minutes** and builds upon the
previous day’s work.  The course begins with the absolute basics—installing
Python and pip, using the interactive interpreter, and writing simple
programs—and gradually introduces core language features such as strings,
lists, dictionaries, loops and functions.  After four weeks of fundamentals
you will tackle a bonus week of **simple algorithms** such as searching,
sorting and counting values.  The goal is to give you the confidence to
transition into more advanced topics like data modelling, BACnet scanning and
RDF graphs found in the accompanying course.

## What You Will Learn

By the end of this mini challenge you will be able to:

- Install Python and verify your environment using the command line.
  Pip is the package installer for Python and allows you to install
  third‑party libraries from the Python Package Index【884625456392658†L111-L113】;
  you’ll practise using `python3 -m pip install` to add extra tools to your
  environment【588230187165224†L424-L437】.
- Use Python as a calculator and write simple scripts.  You will learn how
  arithmetic operators such as `+`, `-`, `*`, `/`, floor division `//`,
  remainder `%` and exponentiation `**` work【369182417897566†L91-L124】, and how to
  assign results to variables and write comments【369182417897566†L67-L82】.
- Manipulate text strings: creating single‑ and double‑quoted strings, using
  triple quotes for multi‑line text, concatenating with `+` and
  repeating with `*`, indexing and slicing, and using functions like
  `len()`【126592705671557†L318-L426】.  You’ll also work with raw strings for
  Windows file paths and learn to split and join text【158729984520153†L1644-L1679】【361933470286636†L2326-L2339】.
- Work with lists and dictionaries.  Lists can be indexed, sliced, extended
  and sorted【126592705671557†L471-L521】【499479381673287†L68-L156】, while
  dictionaries map keys to values and support fast lookup and membership
  testing【972561048532027†L550-L566】.
- Control the flow of a program with `if`/`elif`/`else` statements【361868988149850†L82-L101】,
  `for` loops and the `range()` function【361868988149850†L107-L124】【361868988149850†L146-L207】,
  and `while` loops that continue until a condition is false【690482164421068†L593-L633】.
- Define your own functions using `def`, supply parameters, return values and
  write docstrings【361868988149850†L540-L624】.  You will also practise
  importing standard modules such as `math` and `random`, reading and
  writing text files with the built‑in `open()` function【363542897074291†L362-L378】,
  and using comprehensions to build lists and dictionaries concisely.
- Implement simple algorithms: linear search, finding the minimum and
  maximum values, basic sorting techniques, counting occurrences and
  performing string concatenation efficiently using `str.join()`【361933470286636†L2326-L2339】.

* Gain hands‑on experience with a **mini BACnet server** and **schedule
  device**: run the provided scripts, write simple control algorithms
  against commandable points, read calendar and weekly schedule
  properties via BACnet, and capture BACnet/IP traffic using
  `tcpdump` and Wireshark.  These exercises illustrate why BACnet/IP
  uses a single UDP port【875468702266391†L28-L30】 and why only one
  BACnet process may listen on that port【829796302640208†L213-L218】.

* Deploy your scrapers for long‑term reliability: create
  **systemd** service files in `/etc/systemd/system/` to start your
  Python scripts automatically at boot and restart them if they exit【113913917272701†L105-L126】【113913917272701†L218-L252】;
  build Docker containers and use `--restart` or Compose `restart`
  policies so that your containerised scrapers survive host
  reboots and recover from crashes【596820571461369†L920-L941】.

## Course Structure

The course is organised into **six weeks** (five core weeks plus a
bonus week).  The first five weeks each contain seven short lessons
(Day 01 to Day 35) that build on each other, and the bonus week adds
three hands‑on lessons (Day 36 to Day 38) focused on BACnet devices and
troubleshooting:

| Week | Topics |
|-----|-------|
| **Week 1 – Getting Started & Basics** | Install Python and pip, explore variables, numbers, strings and comments. |
| **Week 2 – Lists, Loops & Dictionaries** | Lists and their methods, for/while loops, conditionals, string methods, and basic dictionaries. |
| **Week 3 – Functions, Modules & Files** | Defining functions, using modules, reading/writing files, list and dictionary comprehensions. |
| **Week 4 – Data Structures & Advanced Built‑ins** | Dictionaries in depth, tuples and sets, string methods, slicing, built‑in functions such as `sorted`, `min` and `max`. |
| **Week 5 – Simple Algorithms** | Linear search, min/max algorithms, sorting, string concatenation, counting and basic recursion or iteration tasks. |
| **Week 6 – BACnet mini server, troubleshooting & deployment (Bonus)** | Run a mini BACnet device and schedule server, write simple control algorithms, read schedule objects, capture BACnet/IP traffic with Wireshark, and understand why BACnet/IP uses a fixed UDP port that cannot be shared【875468702266391†L28-L30】【829796302640208†L213-L218】.  Conclude the course by deploying your scrapers with systemd and Docker so they restart automatically on crash or reboot【113913917272701†L105-L126】【113913917272701†L218-L252】【596820571461369†L920-L941】. |

## Using This Repository

All lesson files reside in the `lessons/` directory and follow the naming
convention `dayXX.md` where `XX` is a zero‑padded day number.  Each file
contains seven sections:

1. **Goal** – what you will accomplish by the end of the lesson.
2. **Concept** – an introduction to the topic with context and relevant
   citations from official Python documentation.
3. **How to Use It** – step‑by‑step instructions and code snippets.
4. **Why This Matters** – a short explanation of why the topic is important
   for building data models and solving engineering problems.
5. **Mini Examples** – small Python snippets that demonstrate the concept.
6. **Micro Exercises** – short, hands‑on tasks to reinforce learning.
7. **Key Takeaway** – the most important idea to remember.

Work through one lesson per day.  At the end of each week there is a small
review project to consolidate your knowledge.  After completing this
challenge you should feel comfortable enough to tackle the more advanced
`brick‑223P` data modelling course.
