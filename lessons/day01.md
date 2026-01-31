# Day 01 – Installing Python & Pip (BACnet Ready)

## Goal

Set up your development environment by installing Python and pip, then verify that everything works **including installing BACnet libraries**. By the end of this lesson you’ll be able to run:

* `python --version`
* `python -m pip --version`
* install **BAC0** and **bacpypes3**
* run a quick import test for both

## Concept

Python is a high-level programming language that is **easy to learn** and has extensive standard and third-party libraries. To run Python code you need the interpreter installed on your computer.

Once Python is installed, **pip** provides a way to install additional libraries from the Python Package Index (PyPI). For this course, pip is how we install building automation tooling—especially BACnet libraries.



## How to Use It

### Install Python

Download Python from the official site latest version of `3.14.x` and install it:

* https://www.python.org/downloads/windows/

* Windows/macOS: use the installer and **check “Add Python to PATH”**
* Linux: use your package manager if needed (often already installed)

### Verify your installation

Open a terminal and run:

```bash
python --version
python -m pip --version
```

### Install BACnet libraries: BAC0 + bacpypes3

Install both in your venv:

```bash
python -m pip install bac0 bacpypes3 ifaddr
```

> If you’re on Linux and plan to do real BACnet/IP work later, you may also want:
> `python -m pip install ifaddr`
> (Some BACnet tooling uses it to find network interfaces.)

### Verify the BACnet installs

Run this one-liner:

```bash
pip show BAC0
```

### Confirm imports

```bash
pip show bacpypes3
```

If it prints version numbers without errors, you’re ready.

## Why This Matters

Before you can experiment with Python you must have a working interpreter and package installer. Installing Python and pip ensures that you can run the examples in this course and install additional libraries when needed.

For building automation, **BAC0** and **bacpypes3** are foundational:

* **BAC0** is a friendly, higher-level interface for common BACnet tasks.
* **bacpypes3** is a modern BACnet stack for building your own BACnet tools and services.

You’ll use these later to scan devices, read present values, and build repeatable data collection scripts.


## Micro Exercises

1. Create and activate a virtual environment named `env`.
2. Upgrade pip inside your venv.
3. Install **BAC0** and **bacpypes3**.
4. Run the example to print "Hello Python!"


## Key Takeaway

Installing Python and pip is the first step. Setting up a virtual environment and installing **BAC0** + **bacpypes3** makes your machine **BACnet-ready**, so you can move on to scanning and reading real building automation data in the next lessons.
