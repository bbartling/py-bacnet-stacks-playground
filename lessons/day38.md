## Day 38 – Thermal R–C analogy (high level, no heavy physics)

### Goal

Connect **first-order room / coil dynamics** to a **resistance–capacitance (R–C)** picture used in controls textbooks: one state variable, energy balance, **time constant** \(\tau = R \cdot C\). Stay qualitative + one discrete update—full PDEs are out of scope.

### Concept

Think of a zone air temperature \(T\) like a capacitor voltage. Heat flows proportional to driving differences (**resistors**). A crude lumped model:

\[
C \frac{dT}{dt} \approx \frac{T_{\text{amb}} - T}{R} + Q_{\text{in}}
\]

- \(C\): **thermal capacitance** (air + lightweight mass tied to the node)—bigger \(C\) ⇒ slower temperature moves.
- \(R\): **thermal resistance** to ambient (envelope + infiltration path lumped).
- \(Q_{\text{in}}\): net **HVAC + internal gains** into the node (W or BTU/h simplified as a source term for this lesson).

You are **not** solving partial differential equations for walls here; you are learning the **structure** that underlies many gray-box building models.

### Discrete intuition (preview of Day 39)

With small step \(\Delta t\):

\[
T_{n+1} \approx T_n + \frac{\Delta t}{C}\left(\frac{T_{\text{amb}} - T_n}{R} + Q_{\text{in}}\right)
\]

That is **explicit Euler**—an algorithm you can code in five lines.

### Why this matters

When you see “**time constant**” on a spec sheet or in a trend, the R–C story explains **why** PID gains and FDD windows must match process dynamics. It also links HVAC domain knowledge to **differential equations** you will discretize tomorrow.

### Mini examples

- If \(R\) doubles (better insulation), what happens to steady-state heat flow for the same \(\Delta T\)?
- If \(C\) doubles (more mass in the control volume), what happens to the speed of response after a step in \(Q_{\text{in}}\)?
- Sketch (words only) why **sensor in sun** vs **sensor in shade** looks like a **bias** on \(T\), not a change in \(C\).

### Micro exercises

1. If \(\tau = RC = 30\) minutes, roughly how long until a step response is “mostly settled” (rule of thumb: \(3\tau\) to \(5\tau\))?
2. Units check: if \(C\) is in J/K and \(R\) in K/W, what are the units of \(Q_{\text{in}}\) in the discrete formula above?
3. Give one reason a **single-node** model might miss real room behavior.

### Key takeaway

R–C language is the bridge between **mechanical intuition** (mass, insulation, gains) and **code-friendly differential equations**—the right level for this crash course.
