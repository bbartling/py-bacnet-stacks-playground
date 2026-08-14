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
} from "cursor/canvas";

const POL = ["PPO", "heuristic", "DQN", "random"];
const U100_R = [-2906, -2955, -3085, -3138];
const Y2X_R = [-2526, -2540, -2536, -2625];
const U100_KWH = [2174, 2536, 2338, 2605];
const Y2X_KWH = [1708, 1947, 1944, 1968];
const U100_PK = [174, 174, 183, 170];
const Y2X_PK = [153, 151, 151, 147];
const LEGACY_PEAK_USD = [2611, 2297];
const ENERGY_ONLY_USD = [261, 205];

export default function RewardLegacyVsOperator() {
  return (
    <Stack gap={20}>
      <Stack gap={6}>
        <Row gap={8} align="center">
          <H1>legacy_reward_v1 ran; operator_pay_v1 did not</H1>
          <Pill tone="warning" active>
            screening
          </Pill>
        </Row>
        <Text tone="secondary">
          Both EnergyPlus campaigns used the old daily peak×$15 contract. unique-100
          n≈100 heating days; year2xsyn n=487 ids. Source:
          plots/rl_report_year2x/summary.json and plots/rl_report/comparison.json.
        </Text>
      </Stack>

      <Callout tone="warning" title="Not a paired operator-pay bakeoff">
        operator_pay_v1 (billing floor, school-day readiness, 2x/3x paycheck) is
        implemented in eplus_gym/rl/reward.py. No EnergyPlus day on these pools
        was rescored with it. Do not read the bars as a new-policy win.
      </Callout>

      <Grid columns={4} gap={12}>
        <Stat value="legacy_reward_v1" label="unique-100 + year2xsyn" />
        <Stat value="not run" label="operator_pay_v1 on E+" tone="warning" />
        <Stat value="−2906" label="unique-100 PPO mean" />
        <Stat value="−2526" label="year2x PPO TRAIN mean" />
      </Grid>

      <H2>Mean reward — same legacy formula, two pools</H2>
      <Text tone="secondary" size="small">
        More negative is worse. year2x PPO/DQN are TRAIN jsonl, not deterministic
        eval. Pools differ (100 unique heating vs 487 year+syn), so deltas mix
        climate mix + exploration, not a controlled A/B.
      </Text>
      <BarChart
        categories={POL}
        series={[
          { name: "unique-100 mean reward", data: U100_R, tone: "neutral" },
          { name: "year2xsyn mean reward", data: Y2X_R, tone: "info" },
        ]}
        height={240}
      />

      <H2>Mean EnergyPlus kWh / day</H2>
      <BarChart
        categories={POL}
        series={[
          { name: "unique-100 kWh/day", data: U100_KWH, tone: "neutral" },
          { name: "year2xsyn kWh/day", data: Y2X_KWH, tone: "success" },
        ]}
        height={220}
      />

      <H2>Mean peak kW</H2>
      <BarChart
        categories={POL}
        series={[
          { name: "unique-100 peak kW", data: U100_PK, tone: "neutral" },
          { name: "year2xsyn peak kW", data: Y2X_PK, tone: "warning" },
        ]}
        height={220}
      />

      <Table
        headers={["Campaign", "Reward used", "PPO mean reward", "PPO kWh", "PPO peak kW", "Eval?"]}
        rows={[
          ["unique100_rleplus", "legacy_reward_v1", "−2906", "2174", "174", "No (train+baselines)"],
          ["year2xsyn", "legacy_reward_v1", "−2526", "1708", "153", "No (TRAIN jsonl)"],
          ["operator_pay_*", "operator_pay_v1", "—", "—", "—", "Not run"],
        ]}
        rowTone={["neutral", "warning", "danger"]}
      />

      <H2>What the two rewards charge (PPO means, illustrative $)</H2>
      <Text tone="secondary" size="small">
        Reconstruct from mean kWh and mean peak only. Rates: $0.12/kWh and
        $15/kW. legacy bills the full daily peak every day. operator_pay billing
        floor would charge incremental kW above month-to-date peak — if MTD
        already equals that day’s peak, demand $ → 0. Zone readiness is not in
        these CSVs, so paycheck is not shown.
      </Text>
      <BarChart
        categories={["unique-100 PPO", "year2x PPO"]}
        series={[
          { name: "legacy demand $ (peak×15)", data: LEGACY_PEAK_USD, tone: "warning" },
          { name: "energy $ (kWh×0.12)", data: ENERGY_ONLY_USD, tone: "success" },
        ]}
        height={220}
      />
      <Text tone="secondary" size="small">
        unique-100 PPO implied energy+demand ≈ $2,872 vs logged mean reward −2906
        (comfort terms fill the gap). year2x PPO ≈ $2,502 vs −2526. Screening
        dollars, not a tariff.
      </Text>
    </Stack>
  );
}
