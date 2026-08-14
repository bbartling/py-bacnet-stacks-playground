import {
  BarChart,
  Callout,
  Grid,
  H1,
  H2,
  Pill,
  Row,
  Stack,
  Stat,
  Table,
  Text,
  UsageBar,
} from "cursor/canvas";

const POLICIES = ["PPO train", "DQN train", "heuristic", "random_walk"];
const REWARD = [-2526, -2536, -2540, -2625];
const KWH = [1708, 1944, 1947, 1968];
const PEAK = [153, 151, 151, 147];

export default function Year2xTrain() {
  return (
    <Stack gap={20}>
      <Stack gap={6}>
        <Row gap={8} align="center">
          <H1>year2xsyn — TRAIN freeze, not eval</H1>
          <Pill tone="success" active>
            complete
          </Pill>
        </Row>
        <Text tone="secondary">
          487-id pool (336 AMY dates + 151 Nov–Mar synthetic clones). Reward is
          legacy_reward_v1. Source: plots/rl_report_year2x/summary.json · site
          year2xsyn · 2026-08-14.
        </Text>
      </Stack>

      <Callout tone="warning" title="Do not call a winner">
        PPO and DQN rows are model.learn() exploration (split=TRAIN,
        action_source=STOCHASTIC_TRAINING_POLICY). Saved PPO saturates lower
        bounds (68°F occupied, 58°F unoccupied, start step 20, end 60, recovery
        0). DQN Discrete(64) is an ablation. Random and heuristic are extra
        EnergyPlus days, not a locked test.
      </Callout>

      <H2>EnergyPlus-day completion (four passes)</H2>
      <Text tone="secondary" size="small">
        One EnergyPlus process per weather day on A04 DualSP. Not the CS meter.
        Code flag remains LIVE_ENERGYPLUS.
      </Text>
      <UsageBar
        total={1948}
        topLeftLabel="Attempted EnergyPlus days"
        topRightLabel="1948 / 1948 (2 heuristic heap fails scored as failed)"
        segments={[
          { id: "ppo", value: 487, color: "green" },
          { id: "dqn", value: 487, color: "blue" },
          { id: "random", value: 487, color: "orange" },
          { id: "heuristic", value: 487, color: "yellow" },
        ]}
      />
      <Grid columns={4} gap={12}>
        <Stat value="488" label="PPO jsonl rows (0 fail)" tone="success" />
        <Stat value="488" label="DQN jsonl rows (0 fail)" tone="success" />
        <Stat value="487" label="random ok" tone="success" />
        <Stat value="485 ok / 2 fail" label="heuristic" tone="warning" />
      </Grid>

      <H2>Mean TRAIN / extra-day reward (legacy_reward_v1)</H2>
      <Text tone="secondary" size="small">
        More negative is worse. Means exclude the two heuristic heap days
        (2025-09-29, 2026-02-02__syn).
      </Text>
      <BarChart
        categories={POLICIES}
        series={[{ name: "Mean reward (legacy_reward_v1)", data: REWARD, tone: "info" }]}
        height={220}
      />

      <H2>Mean EnergyPlus kWh and peak kW</H2>
      <BarChart
        categories={POLICIES}
        series={[
          { name: "Mean daily kWh", data: KWH, tone: "success" },
          { name: "Mean peak kW", data: PEAK, tone: "warning" },
        ]}
        height={240}
      />
      <Table
        headers={["Policy", "n ok", "failed", "Mean reward", "Mean peak kW", "Mean kWh", "Mean pre-8"]}
        rows={[
          ["PPO train", "488", "0", "−2526", "153", "1708", "0.006"],
          ["DQN train", "488", "0", "−2536", "151", "1944", "0.53"],
          ["heuristic", "485", "2", "−2540", "151", "1947", "0.69"],
          ["random_walk", "487", "0", "−2625", "147", "1968", "1.99"],
        ]}
        rowTone={["neutral", "neutral", "warning", "neutral"]}
      />
      <Text tone="secondary" size="small">
        Pre-8 = comfort violations near 08:00. PPO train is near zero; random is
        not. That is screening, not a bill.
      </Text>

      <Grid columns={3} gap={12}>
        <Stat value="legacy_reward_v1" label="Reward actually used" />
        <Stat value="operator_pay_v1" label="In code; not this run" tone="warning" />
        <Stat value="0.006" label="PPO mean pre-8" tone="success" />
      </Grid>
    </Stack>
  );
}
