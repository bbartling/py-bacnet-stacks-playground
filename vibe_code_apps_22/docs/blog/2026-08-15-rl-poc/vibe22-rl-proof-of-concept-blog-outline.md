# Developing an IoT Edge Application for Demand-Side Management — RL Proof of Concept

## Editorial position

This article can be published now as an honest **architecture and simulator proof of concept**. It cannot yet say that a valid reinforcement-learning policy learned to reduce demand. The corrected campaign has not been trained.

Use this one-sentence claim throughout:

> We built and tested the physics-to-RL experimental loop: a calibrated EnergyPlus model accepts six-zone daily controls, simulates a winter day, and returns energy, demand, and comfort consequences. Valid post-fix RL policy training is the next experiment.

Do not use “the model is 50% learned.” There is no defensible percentage behind it. A better mechanical-engineer-friendly description is:

> EnergyPlus provides a physics-informed head start. It lets the controller practice offline before touching a real BAS, but it remains an imperfect training plant. Field data must be used to test, constrain, and cautiously adapt the policy—not to assume that nightly retraining will automatically correct every modeling error.

## Working title options

1. **From a Calibrated EnergyPlus Model to a Daily HVAC Learning Environment**
2. **Teaching an HVAC Controller in a Physics Sandbox Before Connecting BACnet**
3. **A Daily Reinforcement-Learning Experiment for Winter Demand Management**

Suggested title: option 2. It tells a mechanical-engineering audience what the work is for without claiming an operational optimizer.

## Proposed article structure

### 1. The problem: the coldest morning can set the bill

Open with the Wisconsin elementary school and its geothermal heat-pump system. Explain that a short morning recovery can create the highest electrical demand of the month. The DSM goal is not simply “use less electricity.” It is to manage three competing outcomes:

- have all six building areas ready for school;
- avoid creating a new monthly peak kW;
- avoid shifting so much heating that daily kWh or cost increases excessively.

Recommended existing figure: `sp_creekside/plots/analytics/demand_vs_web_weather_scatter_peak_day.png`.

### 2. The training plant: A04, the calibrated EnergyPlus model

Introduce A04 as the pinned EnergyPlus model, not “A05” and not an anonymous best file. Record the SHA-256 pin:

`212a2835eabb8b3a316150815a61bc996bf1fda4191df655dbf74f1126132683`

Explain the six-zone simplification:

- `1F_A`, `1F_B`, `1F_C`, `1F_D`, `2F_A`, and `2F_B` follow the BAS zoning abstraction;
- this was chosen to make the control problem understandable and computationally manageable;
- it is not a room-by-room as-built replica;
- a better zone/heat-pump map could improve physical fidelity later.

Report the calibration honestly: on ten available monthly utility periods, A04 had approximately **+0.98% NMBE** and **10.45% CV(RMSE)**, passing the project’s monthly Guideline 14 screen. Immediately explain that monthly agreement does not validate 15-minute demand behavior or zone recovery dynamics.

Recommended existing figures:

- `vibe_code_apps_22/plots/rl_report/plots/a04_gl14_monthly_pct.png`, with a caption explaining that Guideline 14 is an aggregate calibration screen, not a requirement that every month fall between the guide lines;
- `vibe_code_apps_22/plots/rl_report/plots/a04_gl14_load_duration.png`, as the honesty plot showing the remaining hourly-shape mismatch.

### 3. Why wrap EnergyPlus as a Gym environment?

Use Figure 1, `figures/01-physics-to-policy.svg`.

Explain the software boundary in plain language. EnergyPlus is the training plant. The Gym wrapper is the test bench. PPO, DQN, a rule-based operator, or a random baseline can all propose the same kind of daily control plan and receive the same measurements back.

EnergyPlus returns, at 15-minute resolution:

- facility electric demand in kW;
- six aggregated zone temperatures;
- outdoor temperature;
- applied heating setpoints;
- simulation quality and provenance data.

The wrapper converts the trajectory into peak kW, daily kWh, readiness/comfort violations, and a scalar reward. Every plotted result should retain the day, policy, seed, A04 hash, EPW hash, reward version, and run ID.

### 4. One episode is one day

Use Figure 2, `figures/02-daily-episode-reward.svg`.

At midnight the controller sees one 19-element context vector:

- calendar: month, day of week, day of year;
- six compact weather statistics;
- billing floor and month-to-date peak;
- school-day flag;
- six current zone temperatures;
- live-versus-historical forecast flag.

It then chooses one daily plan. EnergyPlus stages a fixed prior-day lookback and the target day, producing 192 simulation steps; only the target day’s 96 quarter-hour steps are scored. A single reward closes the episode.

Be precise: this is **contextual-bandit-like daily control**, not a controller that observes and changes its action every 15 minutes. That is a feature of the current design, not a flaw to hide. It matches the intended midnight planning workflow, while a deterministic edge state machine can safely execute the plan during the day.

### 5. What the action space looks like

Use Figure 3, `figures/03-ppo-vs-dqn-action-space.svg`.

PPO uses 11 continuous control values:

1. occupied heating setpoint, 68–72°F;
2. unoccupied heating setpoint, 58–68°F;
3. occupancy start step, 20–40;
4. occupancy end step, 60–80;
5. recovery lead, 0–180 minutes;
6. six zone-specific setback offsets, −3 to +1°F.

DQN is deliberately smaller. It selects one of 64 predefined combinations:

`4 unoccupied setpoints × 4 recovery leads × 4 shared setbacks = 64 actions`

Its occupied setpoint stays at 70°F, its day window is fixed, and all six zones share the same setback offset. DQN is therefore a coarse ablation, not a fair winner-take-all comparison with PPO.

Do not show a literal Q-table. The 19-dimensional state is continuous, so a tabular state-by-action matrix would be enormous and artificial. The DQN contains a neural **Q-function** that produces 64 estimated action values for the current context. The best blog visualization is a 64-bar Q-value chart for one example cold day, with the selected action highlighted. That chart does not exist yet and must come from a valid trained checkpoint.

### 6. The reward: a pretend operator paycheck

The current planned experiment is `operator_pay_2x_v1`; the completed five-run gate used `legacy_reward_v1`. Label the operator-pay graphic **DESIGN — NOT YET USED IN A VALID POST-FIX CAMPAIGN**.

For a feasible school day:

`illustrative paycheck = clip($100 + 2 × (baseline cost − candidate cost), $0, $500)`

The 3× version is a separate experiment, not a randomly changing jackpot. Candidate and baseline must be paired EnergyPlus simulations using the same day and billing floor. If the building is not ready at school start, the displayed paycheck is $0 and the bounded training reward is −10. All dollars are illustrative until an actual tariff is verified.

Explain why the training reward and displayed dollars differ: bounded numerical rewards help stable optimization; displayed dollars help a human understand the tradeoff. Neither is a utility-bill savings claim.

### 7. What has actually run

Use a prominent “experiment ledger” box:

| Evidence | Count | What it proves |
| --- | ---: | --- |
| Historical PPO training episodes | 488 | Nothing publishable about learning; pre-fix runs contained EnergyPlus Severe errors |
| Historical DQN training episodes | 488 | Same limitation |
| Valid post-fix RL training episodes | **0** | Formal corrected campaign is still `NOT_RUN` |
| Valid post-fix EnergyPlus gate runs | **5** | Simulator health and paired control sensitivity |

The old learning curves may be discussed as a debugging lesson, but they must be watermarked `INVALID_PRE_FIX_EPLUS_SEVERE — TRAIN EXPLORATION ONLY` and cannot be used to say PPO or DQN learned.

### 8. The valid proof-of-concept result

Use `figures/04-jan26-paired-physics.png`, generated from the saved post-fix trajectory Parquet files.

On January 26, the manually perturbed 68/58°F strategy changed the EnergyPlus response relative to the assumed 70/65°F incumbent:

- peak: 246.50 → 257.77 kW, **+11.27 kW**;
- daily energy: 4,257.26 → 3,736.73 kWh, **−520.53 kWh**.

This is a useful negative result. Deeper setback saved simulated daily energy but increased the recovery peak. It proves that the environment exposes the demand-versus-energy tradeoff. It does **not** prove RL discovered a superior schedule.

### 9. The uncomfortable but valuable physics check

Use `figures/05-zone-ramp-honesty.png`.

The post-fix A04 trajectories contain simulated 15-minute recovery jumps around 4.9°F and 9.3°F, while real BAS six-zone changes are normally much smaller. An optimizer can exploit unrealistic recovery speed, so this must be a gating metric before long training. This is precisely why “monthly calibrated” and “control-ready” are different engineering claims.

### 10. What would prove the RL agent learned?

List the charts required after a valid campaign. These should be generated from deterministic validation evaluation, not the reward log used during training:

1. validation return versus cumulative real EnergyPlus calls, one trace per random seed plus mean and 95% interval;
2. paired validation changes in peak kW and kWh versus the incumbent, with bootstrap confidence intervals;
3. peak-kW versus kWh Pareto plot, with infeasible comfort cases marked;
4. school-start readiness and occupied comfort violation rates;
5. action saturation: how often PPO lands on each bound;
6. action-versus-weather plots showing colder forecasts cause explainable changes;
7. PPO, DQN, heuristic, incumbent, and random baselines evaluated on the same days;
8. one DQN 64-action Q-value bar chart and one PPO action-distribution example.

A rising training reward by itself is insufficient. The article can say “learned” only if deterministic validation performance improves across multiple seeds and the improvement survives paired uncertainty estimates without violating readiness.

### 11. From sandbox to IoT edge

Close with the future architecture:

1. at midnight, fetch a 24-hour weather forecast;
2. read six zone temperatures, month-to-date demand, and schedule context;
3. have the approved policy propose a daily plan;
4. pass it through hard bounds and a deterministic BACnet executor;
5. execute `UNOCCUPIED → RECOVERY → OCCUPIED → SETBACK` states;
6. monitor comfort, equipment, communications, and manual overrides;
7. fall back to the incumbent schedule on any fault;
8. score the completed day and append it to a replay store;
9. train a challenger offline and promote it only after repeated validation—not automatically every midnight.

The existing `vibe_code_apps_4` is a useful BACpypes3 prototype, but it currently supplies current weather and static scheduling. It is not yet the safe six-zone write executor described above.

### 12. Closing language

Suggested close:

> The proof of concept is not that reinforcement learning has already solved the building. It is that the pieces now speak the same engineering language: a weather and building state goes in, a six-zone daily plan is tested in EnergyPlus, and demand, energy, and comfort consequences come back with provenance. The next milestone is deliberately less glamorous and more important—prove, across held-out winter days and multiple seeds, that a learned policy beats simple schedules without exploiting a weakness in the simulator. Only then does BACnet become the deployment story rather than the experiment.

## Publication gate

The architecture/A04/P1 article is publishable now if all captions use the limitations above. A results article claiming PPO or DQN learned should wait for a valid post-fix pilot or full campaign.
