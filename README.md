# Python Fundamentals Mini Challenge

Welcome to the **Python Fundamentals Mini Challenge** — a month‑long introduction to Python aimed at engineers and building professionals who are new to programming.

Each daily lesson is designed to take about **20 minutes** and builds upon the previous day’s work. The course begins with the absolute basics (installing Python and pip, using the interactive interpreter, and writing simple programs) and gradually introduces core language features such as strings, lists, dictionaries, loops, and functions.

After four weeks of fundamentals you will tackle a bonus week of **simple algorithms** and a **final mini project** that brings everything together. The goal is to give you the confidence to transition into more advanced topics like data modelling, BACnet scanning, and RDF graphs found in the accompanying course.

---

## What You Will Learn

By the end of this mini challenge you will be able to:

- Install Python, verify your environment, and use pip to add third‑party libraries.
- Use Python as a calculator and write simple scripts with variables, arithmetic operators, and comments.
- Manipulate text strings — create single‑ and double‑quoted strings, repeat and concatenate them, index and slice substrings, and split/join text.
- Work with lists and dictionaries:
  - index, slice, extend, and sort lists
  - map keys to values and look up entries quickly
- Control the flow of a program with `if/elif/else` statements, `for` loops, and `while` loops.
- Define your own functions, import standard modules such as `math` and `random`, read and write text files with the built‑in `open()` function, and use comprehensions to build lists and dictionaries concisely.
- Implement simple algorithms such as linear search, finding minimum and maximum values, basic sorting, and counting occurrences.
- Gain hands‑on experience with a **mini BACnet server** and **schedule device**:
  - run the provided scripts
  - write simple control algorithms against commandable points
  - read calendar and weekly schedule properties via BACnet
  - capture BACnet/IP traffic using `tcpdump` and Wireshark
- Deploy your scrapers for long‑term reliability by creating **systemd** service files and building Docker containers that restart automatically on crash or reboot.

---

## Course Structure

The course is organised into **six weeks** (five core weeks plus a bonus week). Each week contains a series of short lessons that build on each other, followed by a small review project to consolidate your knowledge.

| Week | Focus |
|---|---|
| **Week 1 — Getting Started & Basics** | Install Python and pip, explore variables, numbers, strings, and comments. |
| **Week 2 — Lists, Loops & Dictionaries** | Create and manipulate lists and dictionaries, master loops and conditionals, and work with string methods. |
| **Week 3 — Functions, Modules & Files** | Define functions, import modules, read and write files, and handle errors gracefully. |
| **Week 4 — Data Structures & Advanced Built‑ins** | Dive deeper into dictionaries, tuples, sets, and nested data structures; explore the standard library, higher‑order functions, and documentation tools. |
| **Week 5 — Simple Algorithms** | Implement basic algorithms such as searching, sorting, counting, and aggregating data, and build a small final project. |
| **Week 6 — BACnet Mini Server, Troubleshooting & Deployment (Bonus)** | Run a mini BACnet device and schedule server, write simple control algorithms, troubleshoot BACnet/IP traffic, and deploy your scrapers with systemd and Docker. |

---

## Weekly Outline

Below is a day‑by‑day outline of the mini challenge. Each lesson takes about twenty minutes and ends with **mini examples**, **micro exercises**, and a **key takeaway** to reinforce what you’ve learned.

### Week 1 — Getting Started & Basics  
*Focus: Environment setup, variables, and core data types*

- **Day 1 — Installing Python & Pip:** Set up your development environment by installing Python and pip, verify your installation, and install your first third‑party package.
- **Day 2 — Variables & Arithmetic:** Store values in variables, perform arithmetic operations, and understand operator precedence and integer vs. floating‑point division.
- **Day 3 — Working with Strings:** Create strings, repeat and concatenate them, index individual characters, and slice substrings.
- **Day 4 — Numbers, Booleans & Comparisons:** Explore numeric and Boolean types, use comparison and logical operators, and understand truthiness.
- **Day 5 — User Input & Output:** Read text from the keyboard using `input()`, convert input to numbers, and format output with f‑strings.
- **Day 6 — Introducing Lists:** Create lists, index and slice them, append new elements, and measure length with `len()`.
- **Day 7 — List Operations & Methods:** Add, remove, sort, and copy lists using methods like `append()`, `extend()`, `insert()`, `pop()`, and `sort()`.

### Week 2 — Lists, Loops & Dictionaries  
*Focus: Iteration, conditionals, and key‑value data structures*

- **Day 8 — For Loops & Range:** Iterate over lists/strings/ranges, use `enumerate()`, and compute sums with `range()`.
- **Day 9 — Conditionals & While Loops:** Use `if/elif/else` and `while` loops to control program flow and build sentinel‑controlled loops.
- **Day 10 — String Methods: Split, Join & Case Conversion:** Split strings into lists, join lists back into strings, and apply case‑conversion methods.
- **Day 11 — Introducing Dictionaries:** Map keys to values, add and retrieve entries, test membership, and iterate over key–value pairs.
- **Day 12 — Looping over Dictionaries & Comprehensions:** Loop through dictionaries and build lists/dicts using comprehensions.
- **Day 13 — Tuples & Sets:** Work with immutable tuples, use sets for membership tests and deduplication, and convert between structures.
- **Day 14 — Advanced Loops & Sentinels:** Combine loops and conditionals, use `break`/`continue`, and practise common loop patterns.

### Week 3 — Functions, Modules & Files  
*Focus: Writing reusable code, using modules, and handling files*

- **Day 15 — Writing Functions:** Define functions, supply parameters, return values, and document with docstrings.
- **Day 16 — Modules & the Standard Library:** Import and use modules like `math` and `random`, and organise your code into modules.
- **Day 17 — Reading & Writing Files:** Open, read, and write text files using `open()` and process line‑based data.
- **Day 18 — Handling Errors Gracefully:** Use `try/except` blocks to handle exceptions and make programs robust.
- **Day 19 — Week 3 Review Project:** Build a small program that reads a CSV file of sensor readings, computes statistics using functions, and handles missing files or bad data gracefully.
- **Day 20 — Built‑in Functions & Comprehensions:** Explore `min()`, `max()`, `sorted()`, `any()`, `all()`, and practise comprehensions.
- **Day 21 — Slicing & String Formatting:** Master slicing of sequences and learn advanced string formatting with f‑strings.

### Week 4 — Data Structures & Advanced Built‑ins  
*Focus: Nested collections, standard library, and higher‑order functions*

- **Day 22 — Working with Nested Data:** Manage nested lists and dictionaries, traverse hierarchical structures, and summarise contents.
- **Day 23 — Random Numbers & Math:** Use `random` for random numbers and `math` for mathematical functions.
- **Day 24 — any(), all(), Lambdas & Higher‑Order Functions:** Use `any()`/`all()`, write lambdas, and pass functions as arguments.
- **Day 25 — Documentation, Comments & help():** Write clear comments/docstrings and explore documentation with `help()`.
- **Day 26 — Week 4 Review Project:** Apply nested data structures, modules, and higher‑order functions in a small reinforcement project.
- **Day 27 — What Is an Algorithm?:** Break problems into steps and consider efficiency.
- **Day 28 — Linear Search:** Implement and analyse a linear search.

### Week 5 — Simple Algorithms  
*Focus: Searching, sorting, counting, and aggregating data*

- **Day 29 — Finding Minimum & Maximum:** Write functions to compute smallest/largest elements in a list.
- **Day 30 — Counting Occurrences:** Count occurrences and build frequency tables using dictionaries.
- **Day 31 — Sorting Lists:** Explore ways to sort data and the basics of sorting algorithms.
- **Day 32 — String Algorithms:** Practise substring searches, prefixes, suffixes, and simple text algorithms.
- **Day 33 — Membership & Searching:** Use `in`, sets, and dictionaries for fast membership tests and lookups.
- **Day 34 — Aggregating Data & Basic Statistics:** Aggregate values, compute sums/averages, and produce simple statistics.
- **Day 35 — Final Project & Next Steps:** Combine your skills in a final mini project and get pointers on what to learn next.

### Week 6 — BACnet Mini Device & Deployment (Bonus)  
*Focus: Hands‑on BACnet exercises and deployment*

- **Day 36 — Playing with a Mini BACnet Device:** Start a mini BACnet device simulator, read/write properties, and practise simple control logic.
- **Day 37 — Scheduling with a Mini BACnet Calendar Device:** Work with BACnet calendar and schedule objects to create simple weekly schedules.
- **Day 38 — Troubleshooting BACnet with Wireshark:** Capture and inspect BACnet/IP traffic using `tcpdump` and Wireshark and learn why BACnet/IP uses a fixed UDP port.
- **Day 39 — Deploying a CSV Scraper with systemd:** Create a systemd service to run your Python script automatically at boot and restart it on failure.
- **Day 40 — Containerising Your Scraper with Docker:** Build a Docker container for your scraper and configure restart policies for reliability across reboots.

---

## Using This Repository

All lesson files reside in the `lessons/` directory and follow the naming convention `dayXX.md` where `XX` is a zero‑padded day number.

Each lesson includes:

- Goal
- Concept
- Step‑by‑step instructions
- Mini examples
- Micro exercises
- Key takeaway

Work through **one lesson per day** and complete the exercises. At the end of each week there is a small review project to consolidate your knowledge. After completing this challenge you should feel comfortable enough to tackle the more advanced Brick/223P + BACnet data modelling course.

---

## License

This project is released under the **MIT License** — free, open source, and made for the BAS community.

Use it, remix it, or improve it — just share it forward so others can benefit too. 😊🌍
