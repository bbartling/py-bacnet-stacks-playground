# Day 32 – struct, enum & impl

## Goal

Model a **BACnet point** as a `struct` and object kinds as an **`enum`**.

## Concept

```rust
#[derive(Debug, Clone)]
struct BacnetPoint {
    device_id: u32,
    object_type: u16,
    instance: u32,
    name: String,
}

enum ObjectKind {
    Ai,
    Ao,
    Av,
    Bi,
    Bo,
}

impl BacnetPoint {
    fn object_id(&self) -> String {
        format!("{}:{}", self.object_type, self.instance)
    }
}
```

## Why This Matters

rusty-bacnet and rusty-haystack expose **typed structs** for devices, tags, and reads. You will read `impl` blocks in their docs daily.

## Mini Examples

- Add method `is_analog(&self) -> bool` using `ObjectKind`.
- Print `Debug` output with `{:?}`.

## Micro Exercises

1. Define `struct Zone { name: String, temp_c: f64 }` with a method `fahrenheit`.
2. Enum `AlarmState { Normal, Offnormal, Fault }` with `match` printer.
3. Why does `#[derive(Debug)]` help when sniffing packets and logging?

## Key Takeaway

**Structs hold data; enums restrict variants**—perfect for equipment models before RDF weeks.

---

## Python companion — dataclasses & Enum

*Same day as the Rust lesson above. Prefer a venv; keep scripts in `~/py-lab` (create if needed).*

```python
from dataclasses import dataclass
from enum import Enum, auto

class ObjectKind(Enum):
    AI = auto()
    AO = auto()
    AV = auto()

@dataclass
class BacnetPoint:
    device_id: int
    object_type: int
    instance: int
    name: str

    def object_id(self) -> str:
        return f"{self.object_type}:{self.instance}"

pt = BacnetPoint(5007, 0, 1, "OA-T")
print(pt.object_id(), ObjectKind.AI)
```

| Rust (main lesson) | Python |
|--------|--------|
| `struct` + `impl` | `@dataclass` + methods |
| `enum` variants | `enum.Enum` |
| `#[derive(Debug)]` | `__repr__` (dataclass default) |
| `&self` methods | `self` methods |

**Takeaway:** Model AHU points as small typed records—whether Rust structs or Python dataclasses—before you drown in raw dicts.
