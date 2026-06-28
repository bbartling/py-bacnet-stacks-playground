## Day 32 – struct, enum & impl

### Goal

Model a **BACnet point** as a `struct` and object kinds as an **`enum`**.

### Concept

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

### Why This Matters

rusty-bacnet and rusty-haystack expose **typed structs** for devices, tags, and reads. You will read `impl` blocks in their docs daily.

### Mini examples

- Add method `is_analog(&self) -> bool` using `ObjectKind`.
- Print `Debug` output with `{:?}`.

### Micro exercises

1. Define `struct Zone { name: String, temp_c: f64 }` with a method `fahrenheit`.
2. Enum `AlarmState { Normal, Offnormal, Fault }` with `match` printer.
3. Why does `#[derive(Debug)]` help when sniffing packets and logging?

### Key takeaway

**Structs hold data; enums restrict variants**—perfect for equipment models before RDF weeks.
