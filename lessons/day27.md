## Day 27 – What Is an Algorithm? (HVAC & data)

### Goal

Define an **algorithm** in plain language and see why it matters for **HVAC data and controls**: finite steps, inputs, outputs, and no magic—just repeatable logic you could hand to an operator or a computer.

### Concept

An **algorithm** is a finite sequence of well-defined steps that transforms **input** into **output**. You can write it in English, pseudocode, or Python. Examples in this course stay in **CS 101 territory**: searching lists, comparing numbers, counting, sorting small sets, aggregating readings, and (later) simple **fault-detection style** rules and **tiny simulation** steps—not dynamic programming or advanced graph-theory proofs. **Optional hobby days (41–43)** apply the same definition to **grids**, **stacks**, and **maze carving**—still finite steps, just a different playground than HVAC lists.

**HVAC intuition:** Starting an AHU safely is an algorithm (pre-start checks → enable supply fan → wait for proof → enable heating/cooling). Finding the first zone over setpoint in an **unsorted** list of readings is another: check each value in order (**linear search**). Tallying how many VAVs report a given fault code uses the same “walk the data once” mindset you will code in the coming days.

### How to Use It

Sketch algorithms before coding:

- **Natural language:** “If supply air temp > high limit for two consecutive samples, set `fault = True`.”
- **Pseudocode:** `for each sample: update state; if condition: flag fault`.
- **Python:** small functions with clear names (`check_high_sat`, `first_over_setpoint`).

### Why This Matters

BACnet trends, CSV exports, and edge scripts give you **lists and tables** (often as parallel lists: timestamps, OAT, SAT, …). Basic algorithms let you **summarize**, **filter**, and **evaluate rules** without always depending on heavy libraries. Later lessons connect this style of thinking to **automated fault detection (AFDD)** ideas used in projects like **open-fdd**—but here we stay at the level of **plain Python loops and arithmetic** that would sit *under* tools that use Pandas or vectorized engines.

### Mini examples

- List the steps to decide if an economizer is “likely calling for cooling when it should not” using only SAT, OAT, and a return-air temperature (high-level, no code yet).
- Pseudocode: find the **index** of the first static pressure reading below 0.5 in a list (or report “none”).
- Describe how you would count occurrences of each **fault priority** in a log list.

### Micro exercises

1. In your own words: what makes a procedure an algorithm? Give one **non-HVAC** and one **HVAC** example.
2. Write pseudocode (not Python) for “return the coldest **zone temperature** in a list of floats.”
3. Why might a controls engineer prefer a **clear** 20-line loop over a one-liner nobody can audit?

### Course fit (CS 101 mini-track)

This two-week arc (Days 27–40) is designed as a **daily mini-lesson**: one main idea per day, small functions, **no recursion requirement**, **no dynamic programming**, and **no Pandas**. It is appropriate for a **first exposure to algorithms** in an HVAC analytics context—not a substitute for a full semester on data structures.

### Key takeaway

Algorithms are explicit recipes. In building systems, they show up in **control sequences**, **trend analysis**, and **fault rules**; learning to implement a few by hand builds judgment when you later use libraries or AFDD frameworks.
