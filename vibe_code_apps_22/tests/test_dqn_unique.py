"""DQN v2 unique schedule table. Silent clamp duplicates are forbidden."""
from __future__ import annotations

from eplus_gym.control_v2 import build_six_schedules_f
from eplus_gym.rl.multiday_env import schedule_fingerprint
from eplus_gym.rl.spaces_v2 import (
    DQN_V2_DECLARED_N,
    decode_discrete_v2,
    discrete_n_v2,
    unique_discrete_table_v2,
)


def test_dqn_v2_discrete_n_equals_unique_fingerprints():
    table = unique_discrete_table_v2(day="2026-01-12")
    fps = [schedule_fingerprint(build_six_schedules_f(p)) for p in table]
    assert len(fps) == len(set(fps))
    assert discrete_n_v2() == len(table)
    assert DQN_V2_DECLARED_N == 110
    assert discrete_n_v2() < DQN_V2_DECLARED_N
    assert discrete_n_v2() >= 70
    a0 = decode_discrete_v2(0)
    a1 = decode_discrete_v2(1)
    assert a0.continuous_conditioning and a0.occupied_heating_f == 68.0
    assert a1.continuous_conditioning and a1.occupied_heating_f == 70.0
    seen = set()
    for i in range(discrete_n_v2()):
        fp = schedule_fingerprint(build_six_schedules_f(decode_discrete_v2(i, day="2026-01-12")))
        assert fp not in seen
        seen.add(fp)
