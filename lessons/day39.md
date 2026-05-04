## Day 39 – Explicit Euler for a 1-state thermal model (hands-on)

### Goal

Implement **explicit (forward) Euler** integration for a single zone temperature state—your first **differential equation algorithm** tied to Day 38’s R–C story. Still **no Pandas**: a `while` loop or `for` over timesteps.

### Concept

Given state \(T_n\) at time \(t_n\), choose step \(\Delta t\) and compute derivative \(f(T_n)\) from the model, then:

\[
T_{n+1} = T_n + \Delta t \cdot f(T_n)
\]

For the simplified balance (same signs as Day 38):

\[
f(T) = \frac{1}{C}\left(\frac{T_{\text{amb}} - T}{R} + Q_{\text{in}}\right)
\]

This is a **fixed-step algorithm**; if \(\Delta t\) is too large, the numerical solution can oscillate or blow up—an important CS + numerics lesson.

### How to use it

```python
def simulate_zone_temperature(t0, tamb, q_in, r_k_per_w, c_j_per_k, dt_s, n_steps):
    """Very small explicit-Euler demo. r_k_per_w is R in K/W; c_j_per_k is C in J/K."""
    t = t0
    series = [t]
    for _ in range(n_steps):
        dtdt = (1.0 / c_j_per_k) * ((tamb - t) / r_k_per_w + q_in)
        t = t + dt_s * dtdt
        series.append(t)
    return series


# Toy numbers: not calibrated to a real room—pedagogy only
out = simulate_zone_temperature(
    t0=22.0,
    tamb=18.0,
    q_in=800.0,
    r_k_per_w=0.02,
    c_j_per_k=5e6,
    dt_s=60.0,
    n_steps=180,
)
print(out[0], out[-1], len(out))
```

### Why this matters

Every simulation stack (Modelica exports, EnergyPlus coupling, digital twins) eventually evaluates **right-hand sides** and steps time forward. Euler is the simplest stepping rule; understanding its **stability limits** prepares you for better integrators later—without requiring a full numerical-methods course here.

### Mini examples

- Halve `dt_s` and compare final `T`—convergence toward a finer reference.
- Replace constant `q_in` with a **piecewise schedule** (list of `(t_switch, q)`).
- Log `dtdt` each step; when does it cross near zero (approaching pseudo–steady state)?

### Micro exercises

1. Wrap the simulator in a function `time_to_cross(t0, ..., threshold)` returning first step index where `T > threshold`, or `-1`.
2. What happens if `dt_s` is huge (e.g., 3600 s with the toy constants)? Experiment and describe.
3. **No recursion:** implement with a `for` loop only (course constraint).

### Key takeaway

ODEs + algorithms = **update rule in a loop**. HVAC context makes the state and parameters meaningful instead of abstract \(x\) and \(y\).
