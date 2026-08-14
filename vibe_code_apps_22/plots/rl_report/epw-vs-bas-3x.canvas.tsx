import {
  BarChart,
  Callout,
  Card,
  CardBody,
  CardHeader,
  Divider,
  Grid,
  H1,
  H2,
  LineChart,
  Pill,
  Row,
  Stack,
  Stat,
  Table,
  Text,
  UsageBar,
} from "cursor/canvas";

const MONTHS = ["Nov", "Dec", "Jan", "Feb", "Mar"];
const BAS_KWH = [1369, 2302, 2777, 2373, 1715];
const PPO_KWH = [1686, 2511, 2727, 2190, 1676];
const HEU_KWH = [2070, 2815, 2998, 2485, 2034];
const EPW_F = [37.4, 22.3, 16.1, 27.0, 37.1];
const WEB_F = [38.4, 24.3, 18.2, 29.4, 38.6];

/** Campaign EnergyPlus-day budget: 487 days × PPO + DQN + random + heuristic. */
const YEAR2X_DAYS = 487;
const YEAR2X_PHASES = 4;
const YEAR2X_TOTAL = YEAR2X_DAYS * YEAR2X_PHASES;
const PPO_DONE = 487;
const DQN_DONE = 246;
const RANDOM_DONE = 0;
const HEUR_DONE = 0;
const YEAR2X_DONE = PPO_DONE + DQN_DONE + RANDOM_DONE + HEUR_DONE;
const YEAR2X_PCT = Math.round((100 * YEAR2X_DONE) / YEAR2X_TOTAL);

export default function EpwVsBas3x() {
  return (
    <Stack gap={20}>
      <Stack gap={6}>
        <Row gap={8} align="center">
          <H1>EPW vs BAS — unique-100 RL, plus EnergyPlus campaign status</H1>
          <Pill tone="warning" active>
            year2xsyn running
          </Pill>
        </Row>
        <Text tone="secondary">
          This is the RL canvas (unique-100 ranking and meter overlay). A04 GL14 is
          the other canvas. Cursor canvases cannot poll Windows processes — the
          job bar is a disk/PID snapshot. Re-run the agent to refresh.
        </Text>
      </Stack>

      <Callout tone="info" title="EnergyPlus day ≠ meter data">
        Charts that say EnergyPlus day mean one EnergyPlus run on A04 for one EPW
        date. That is not the CS meter. The gym still uses the code flag
        LIVE_ENERGYPLUS so we refuse spreadsheet surrogates. PPO/DQN already
        saved SB3 zips on the site; leftover ranking does not reload those zips
        to keep training.
      </Callout>

      <Callout tone="warning" title="Snapshot 2026-08-14 — not a live slider">
        vibe22_rl.py campaign --pool year2xsyn still had campaign PID 31216. DQN
        was on the order of day 246 / 487. PPO already finished this pool (mean
        reward −2526 on 488 log rows, 0 failed in episodes.jsonl). Random walk and
        heuristic have not started. Unrelated: an old E20 run_eplus_gym_rules.py
        job was also still on the box — not this campaign.
      </Callout>

      <H2>year2xsyn EnergyPlus-day completion</H2>
      <Text tone="secondary" size="small">
        An EnergyPlus day is one EnergyPlus process on A04 for one EPW date — not
        campus meter data. Code still flags that as LIVE_ENERGYPLUS (no surrogate).
        One campaign = four sequential E+ passes over 487 days (PPO, DQN, then
        random + heuristic). Source: site reports/eplus_gym/rl/year2xsyn.
      </Text>
      <UsageBar
        total={YEAR2X_TOTAL}
        topLeftLabel={`${YEAR2X_PCT}% of campaign EnergyPlus days`}
        topRightLabel={`${YEAR2X_DONE} / ${YEAR2X_TOTAL}`}
        segments={[
          { id: "ppo", value: PPO_DONE, color: "green" },
          { id: "dqn", value: DQN_DONE, color: "blue" },
          { id: "random", value: RANDOM_DONE, color: "orange" },
          { id: "heuristic", value: HEUR_DONE, color: "yellow" },
        ]}
      />
      <Grid columns={4} gap={12}>
        <Stat value="DONE 487/487" label="PPO" tone="success" />
        <Stat value="246/487" label="DQN (current phase)" tone="warning" />
        <Stat value="0/487" label="Random walk (queued)" />
        <Stat value="0/487" label="Heuristic (queued)" />
      </Grid>

      <H2>Audit log</H2>
      <Table
        headers={["When / run", "Job", "Status", "Detail"]}
        rows={[
          [
            "unique100_rleplus (published)",
            "PPO",
            "1 fail / 104 log rows",
            "2025-12-04 Windows EnergyPlus heap 0xC0000374; excluded from means; pre-8 = 0 on 103 ok days",
          ],
          [
            "unique100_rleplus",
            "DQN / heuristic / random",
            "0 fails / 100",
            "Means published; ranking PPO > heuristic > DQN > random",
          ],
          [
            "year2xsyn PPO (this campaign)",
            "PPO train",
            "OK — 0 failed in episodes.jsonl",
            "488 log rows; train_summary mean_reward −2526; ppo_final.zip written",
          ],
          [
            "year2xsyn DQN",
            "DQN train",
            "RUNNING",
            "~246 reward.json under dqn/episodes; campaign PID 31216; jsonl not flushed yet",
          ],
          [
            "year2xsyn report phase",
            "random + heuristic",
            "NOT STARTED",
            "Starts after DQN; then plots/rl_report_year2x (does not clobber unique-100)",
          ],
          [
            "other process on box",
            "run_eplus_gym_rules.py E20",
            "RUNNING (unrelated)",
            "lakeside_w2a_e20_l22_enhanced_champion.idf Jan–Jul 2026 — not A04 year2xsyn",
          ],
        ]}
        rowTone={[
          "warning",
          "success",
          "success",
          "warning",
          undefined,
          "danger",
        ]}
      />

      <Grid columns={4} gap={12}>
        <Stat value="Good enough to rank" label="unique-100 verdict" tone="success" />
        <Stat value="2.3 °F RMSE" label="Daily-mean OAT EPW vs web" />
        <Stat value="+45 kWh / day" label="PPO E+ vs BAS energy bias" />
        <Stat value="76%" label="PPO still wins if 3× resampled" />
      </Grid>

      <Callout tone="info" title="The EPW already is actual-year weather">
        madison_amy_202508_202608.epw is Open-Meteo AMY (not TMY). Comparing “real
        weather” to this EPW is mostly a timezone/aggregation check, not a second
        climate. The useful check is EnergyPlus kWh/peak vs the campus meter on the
        same calendar days. That overlay is not GL14.
      </Callout>

      <H2>Weather: EPW vs Open-Meteo (same unique-100 days)</H2>
      <Text tone="secondary" size="small">
        Daily mean outdoor air, °F. Source: EPW dry-bulb vs demand_vs_web oat_f. Nov
        2025–Mar 2026 campaign months.
      </Text>
      <LineChart
        categories={MONTHS}
        series={[
          { name: "EPW daily-mean OAT °F", data: EPW_F, tone: "info" },
          { name: "Web/Open-Meteo daily-mean OAT °F", data: WEB_F, tone: "neutral" },
        ]}
        height={220}
        beginAtZero={false}
      />
      <Grid columns={3} gap={12}>
        <Stat value="1.9 °F" label="MAE daily-mean OAT" />
        <Stat value="−1.8 °F" label="EPW bias vs web (cooler)" />
        <Stat value="−18 °F" label="Campaign coldest EPW hour" />
      </Grid>

      <H2>Load: EnergyPlus vs BAS meter (99 unique-100 days)</H2>
      <Text tone="secondary" size="small">
        Mean daily kWh by month. BAS = sum of hourly kw_avg. PPO / heuristic =
        EnergyPlus A04 day-MDP (not meter). Source: plots/rl_report/episodes.csv +
        demand_vs_web_weather_hourly.
      </Text>
      <BarChart
        categories={MONTHS}
        series={[
          { name: "BAS meter kWh/day", data: BAS_KWH, tone: "neutral" },
          { name: "PPO EnergyPlus kWh/day", data: PPO_KWH, tone: "success" },
          { name: "Heuristic EnergyPlus kWh/day", data: HEU_KWH, tone: "warning" },
        ]}
        height={240}
      />
      <Table
        headers={["Policy", "Mean E+ kWh", "BAS kWh", "Bias", "CVRMSE", "r (kWh)", "Peak CVRMSE"]}
        rows={[
          ["PPO", "2,209", "2,164", "+45", "30%", "0.67", "46%"],
          ["DQN", "2,328", "2,164", "+164", "31%", "0.66", "41%"],
          ["Heuristic", "2,526", "2,164", "+363", "34%", "0.67", "37%"],
          ["Random walk", "2,594", "2,164", "+430", "37%", "0.63", "40%"],
        ]}
      />
      <Text tone="secondary" size="small">
        unique-100 PPO vs meter is screening, not GL14. PPO matches mean kWh; peaks
        run high. Do not treat ΔkWh as bill savings.
      </Text>

      <Divider />

      <H2>If we ran 3× the days (100 → 300)</H2>
      <Row gap={12} align="stretch">
        <Card style={{ flex: 1 }}>
          <CardHeader>What 300 unique days actually are</CardHeader>
          <CardBody>
            <Stack gap={8}>
              <Text>
                EPW has 372 unique dates. Nov–Mar core is 151 days. Seed-0 300-day pool
                fills all of Nov–Mar plus Oct/Apr shoulders.
              </Text>
              <Text tone="secondary">
                year2xsyn is the stronger follow-up: 336 unique AMY dates + synthetic
                heating clones = 487 EnergyPlus days per policy, still EPW replay.
              </Text>
            </Stack>
          </CardBody>
        </Card>
        <Card style={{ flex: 1 }}>
          <CardHeader>Ranking if we only resampled the same 99</CardHeader>
          <CardBody>
            <Stack gap={8}>
              <BarChart
                categories={["PPO win", "Heuristic win"]}
                series={[
                  { name: "n=100 resample", data: [62.8, 37.2], tone: "info" },
                  { name: "n=300 resample", data: [75.6, 24.4], tone: "success" },
                ]}
                height={180}
              />
              <Text tone="secondary" size="small">
                Bootstrap of unique-100 common days. year2xsyn is the real extra-day
                test — wait for DQN + baselines before claiming the ranking held.
              </Text>
            </Stack>
          </CardBody>
        </Card>
      </Row>
    </Stack>
  );
}
