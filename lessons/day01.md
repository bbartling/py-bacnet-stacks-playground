# Day 01 – Installing Python & Pip

## Goal

Set up your development environment by installing Python and pip, then verify
that everything works.  By the end of this lesson you’ll be able to run
`python3 --version` on your command line and use pip to install a package from
the Python Package Index.

## Concept

Python is a high‑level programming language that is **easy to learn** and has
extensive standard and third‑party libraries【898692921316456†L48-L59】.  To run
Python code you need the interpreter installed on your computer.  The
recommended way to install Python on Windows or macOS is to download it from
the official [python.org](https://www.python.org/downloads/) page; on many
Linux distributions Python is already available via the package manager.  Once
Python is installed, **pip** provides a way to install additional libraries
from the Python Package Index (PyPI).  The pip documentation describes pip as
*“the package installer for Python”* and notes that you can install packages
with `python -m pip install`【884625456392658†L111-L113】.  The Python Packaging
User Guide recommends using pip and shows how to specify packages when
installing from PyPI【588230187165224†L424-L437】.

## How to Use It

1. **Download and install Python.**  Visit the
   [python.org/downloads](https://www.python.org/downloads/) page and choose
   the installer for your operating system.  Run the installer and allow it
   to add Python to your system path.
2. **Verify your installation.**  Open a terminal (Command Prompt on
   Windows, Terminal on macOS/Linux) and run `python --version` or
   `python3 --version`.  You should see a version number such as `3.12.1`.
3. **Check pip.**  In the same terminal run `python -m pip --version`.
   Pip is installed automatically with Python on most systems.  If it isn’t
   available, consult the packaging documentation for installation
   instructions【588230187165224†L424-L437】.
4. **Install a package.**  Use pip to install a third‑party library.  For
   example, try installing the `requests` library:

   ```bash
   python -m pip install requests
   ```

   This command downloads `requests` from PyPI and installs it into your
   environment.  You can verify the installation inside Python:

   ```python
   >>> import requests
   >>> print(requests.__version__)
   ```

## Why This Matters

Before you can experiment with Python you must have a working interpreter and
package installer.  Installing Python and pip ensures that you can run the
examples in this course and install additional libraries when needed.  Many
data modelling and building automation tools—such as BACnet scanners and RDF
libraries—are distributed on PyPI, so a proper setup is essential for
building more advanced projects.

## Mini Examples

Try the following commands in your terminal:

- **Check your Python version**:

  ```bash
  python --version
  ```

- **Install and import a package**:

  ```bash
  python -m pip install rdflib
  python -c "import rdflib; print(rdflib.__version__)"
  ```

  The `-c` flag runs a short command.  If you see a version number printed
  without an error then the installation was successful.

## Micro Exercises

1. Verify that `python` or `python3` is on your path by running the version
   command.
2. Use pip to install the `numpy` library.  After installation, open a
   Python shell and import `numpy` to verify it worked.  Print the value of
   `numpy.pi`.
3. Research how to upgrade pip to the latest version and run the upgrade
   command.  (Hint: `python -m pip install --upgrade pip`.)

## Key Takeaway

Installing Python and pip is the first step on your programming journey.  Once
Python is set up, you can use pip to add any library you need【884625456392658†L111-L113】,
ensuring that you’re ready for the hands‑on challenges in this course.
