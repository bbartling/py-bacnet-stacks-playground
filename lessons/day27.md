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

### Course fit (CS 101 mini-track → Rust pivot)

Days **1–27** build Python intuition for BACnet scripting and basic algorithms. **Day 27** closes the Python arc with the *idea* of algorithms—you will reuse that mindset in Rust loops, graph queries, and edge polling.

Starting **Day 28**, the course **fast-tracks Rust** (Cargo, types, collections), **network programming** (UDP/TCP, tcpdump, Wireshark), **rusty-bacnet** and **rusty-haystack**, then **RDF modeled in Rust** (not Python `rdflib`). Daily **Wireshark labs** include capture scripts under [`lessons/lab-scripts/`](./lab-scripts/).

### Key takeaway

Algorithms are explicit recipes. In building systems, they show up in **control sequences**, **trend analysis**, and **fault rules**; learning to implement a few by hand builds judgment when you later use libraries or AFDD frameworks.

---

## Rust companion — Algorithms + ownership teaser (pivot)

*Same day as the Python lesson above. Work in `~/rust-lab` (create on Day 1).*

An **algorithm** is finite steps: inputs → process → outputs (same in Python and Rust).

Rust adds a rule Python hides: **every value has one owner**.

```rust
fn main() {
    let name = String::from("AHU-1");
    let also = name;          // move — name is no longer valid
    // println!("{name}");    // would not compile
    println!("{also}");

    let name2 = String::from("VAV-1");
    let borrowed = &name2;    // borrow — name2 still valid
    println!("{borrowed} and {name2}");
}
```

| Idea | Meaning |
|------|---------|
| **Owner** | Who frees the memory |
| **Move** | Ownership transfers |
| **Borrow** `&T` / `&mut T` | Temporary access without taking ownership |
| **Lifetime** | How long a borrow is allowed (compiler-checked) |

You do **not** need to master lifetimes yet — just know: prefer borrowing with `&` when a function only needs to read data.

**Takeaway:** Day 28 recaps install + ownership so Days 29–34 feel like practice, not a cliff.

