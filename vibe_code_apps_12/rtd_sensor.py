"""
Pt1000 RTD helpers for a Raspberry Pi + external ADC (2-wire sensors only).

The Raspberry Pi GPIO header does not expose true analog inputs. A practical
pattern is an ADS1115 (I2C) reading the tap of a simple bias divider formed by
a precision series resistor and the **2-wire** RTD loop (element + both leads).
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Optional

# IEC 60751 coefficients for Pt100 / Pt1000 (0 °C and above, good for ~0–150 °C typical HVAC).
PT1000_R0_OHMS = 1000.0
PT1000_A = 3.9083e-3
PT1000_B = -5.775e-7


def resistance_from_divider(v_out: float, v_supply: float, r_series_ohms: float) -> float:
    """
    Two-resistor divider: V_supply --[R_series]--*--[RTD to GND]-- GND

    v_out is measured at * (RTD top node). Solves for RTD resistance.
    """
    if v_supply <= 0:
        raise ValueError("v_supply must be positive")
    if not (0.0 < v_out < v_supply):
        raise ValueError(f"v_out must be between 0 and v_supply (got {v_out} / {v_supply})")
    # v_out = v_supply * R_rtd / (R_series + R_rtd)
    return (r_series_ohms * v_out) / (v_supply - v_out)


def celsius_from_pt1000_resistance(rtd_ohms: float) -> float:
    """
    Convert Pt1000 resistance (ohm) to temperature (°C) using IEC 60751 quadratic
    form valid for T >= 0 °C. For modest sub-zero temps this is often still usable
    for prototypes; validate with ice bath if you care about accuracy near 0 °C.
    """
    # R(T) = R0 * (1 + A*T + B*T^2)  ->  (B*R0)*T^2 + (A*R0)*T + (R0 - R) = 0
    a2 = PT1000_B * PT1000_R0_OHMS
    a1 = PT1000_A * PT1000_R0_OHMS
    a0 = PT1000_R0_OHMS - rtd_ohms

    disc = a1 * a1 - 4.0 * a2 * a0
    if disc < 0:
        raise ValueError(f"Non-physical resistance for Pt1000 model: {rtd_ohms:.3f} ohm")

    sqrt_disc = math.sqrt(disc)
    # Physical root for HVAC-positive temps is the branch that yields T near 0..200 °C
    t1 = (-a1 + sqrt_disc) / (2.0 * a2)
    t2 = (-a1 - sqrt_disc) / (2.0 * a2)
    candidates = [t for t in (t1, t2) if math.isfinite(t)]
    # Prefer plausible HVAC range first
    for lo, hi in ((-50.0, 200.0), (-80.0, 300.0)):
        in_band = [t for t in candidates if lo <= t <= hi]
        if in_band:
            return float(min(in_band, key=lambda t: abs(t)))

    raise ValueError(f"Could not resolve a physical temperature from {rtd_ohms:.3f} ohm")


@dataclass
class DividerConfig:
    r_series_ohms: float
    """Precision bias resistor from V_supply toward the divider node."""

    v_supply: float
    """Supply used by the divider (often 3.3 V from the Pi — see README caveats)."""

    ads_gain_volts: float = 4.096
    """ADS1115 programmable full-scale (+/- gain). Must match programmatic gain choice."""


class SimulatedRtdReader:
    """Deterministic sine-like temperature for laptop / CI development."""

    def __init__(self, center_c: float = 22.0, amplitude_c: float = 2.0, period_s: float = 60.0):
        self._t0 = time.monotonic()
        self._center = center_c
        self._amp = amplitude_c
        self._period = period_s

    def read_celsius(self) -> float:
        elapsed = time.monotonic() - self._t0
        phase = 2 * math.pi * (elapsed % self._period) / self._period
        return self._center + self._amp * math.sin(phase)


class Ads1115DividerReader:
    """
    Read divider midpoint with ADS1115 and convert to temperature.

    Depends on Adafruit Blinka (`board`, `busio`) + `adafruit-circuitpython-ads1x15`,
    normally installed as described in README/requirements.txt.
    """

    def __init__(
        self,
        channel: int = 0,
        divider: Optional[DividerConfig] = None,
        i2c_address: int = 0x48,
        samples_to_average: int = 8,
        sample_delay_s: float = 0.002,
    ) -> None:
        self._divider = divider or DividerConfig(r_series_ohms=3300.0, v_supply=3.300)
        self._samples = max(1, samples_to_average)
        self._sample_delay_s = sample_delay_s

        import board  # type: ignore
        import busio  # type: ignore

        from adafruit_ads1x15.ads1115 import ADS1115, P0, P1, P2, P3  # type: ignore
        from adafruit_ads1x15.analog_in import AnalogIn  # type: ignore

        pins = (P0, P1, P2, P3)
        if channel < 0 or channel >= len(pins):
            raise ValueError("channel must be 0..3 for single-ended AIN0–AIN3")

        i2c = busio.I2C(board.SCL, board.SDA)
        self._ads = ADS1115(i2c, address=i2c_address)

        # Programmable ±FS — pick the closest catalogue full-scale supported by adafruit driver.
        g = float(self._divider.ads_gain_volts)
        gain_lut = sorted(
            (
                (6.144, 2 / 3),
                (4.096, 1),
                (2.048, 2),
                (1.024, 4),
                (0.512, 8),
                (0.256, 16),
            ),
            key=lambda item: abs(item[0] - g),
        )
        self._ads.gain = gain_lut[0][1]

        self._ain = AnalogIn(self._ads, pins[channel])

    def read_raw_voltage(self) -> float:
        acc = 0.0
        for _ in range(self._samples):
            acc += float(self._ain.voltage)
            time.sleep(self._sample_delay_s)
        return acc / float(self._samples)

    def read_celsius(self) -> float:
        v = self.read_raw_voltage()
        r = resistance_from_divider(v, self._divider.v_supply, self._divider.r_series_ohms)
        return celsius_from_pt1000_resistance(r)
