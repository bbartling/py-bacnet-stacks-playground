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
} from "cursor/canvas";

const MONTHS = ["Nov", "Dec", "Jan", "Feb", "Mar"];
const BAS_KWH = [1369, 2302, 2777, 2373, 1715];
const PPO_KWH = [1686, 2511, 2727, 2190, 1676];
const HEU_KWH = [2070, 2815, 2998, 2485, 2034];
const EPW_F = [37.4, 22.3, 16.1, 27.0, 37.1];
const WEB_F = [38.4, 24.3, 18.2, 29.4, 38.6];

export default function EpwVsBas3x() {
  return (
    <Stack gap={20}>
      <Stack gap={6}>
        <H1>EPW vs real weather vs BAS — unique-100 and 3×</H1>
        <Text tone="secondary">
          Lakeside A04 LIVE campaign unique100_rleplus (seed 0). EPW is Madison AMY from
          Open-Meteo. BAS is CS electric meter hourly kW. Web OAT is Open-Meteo in
          demand_vs_web_weather_hourly.csv. Overlap: 99 of 100 campaign days (PPO heap
          abort 2025-12-04 dropped). Screening replay, not verified savings.
        </Text>
      </Stack>

      <Grid columns={4} gap={12}>
        <Stat value="Good enough to rank" label="Verdict on this pool" tone="success" />
        <Stat value="2.3 °F RMSE" label="Daily-mean OAT EPW vs web" />
        <Stat value="+45 kWh / day" label="PPO E+ vs BAS energy bias" />
        <Stat value="76%" label="PPO still wins if 3× resampled" />
      </Grid>

      <Callout tone="info" title="The EPW already is actual-year weather">
        madison_amy_202508_202608.epw is Open-Meteo AMY (not TMY). Comparing “real
        weather” to this EPW is mostly a timezone/aggregation check, not a second
        climate. The useful check is EnergyPlus kWh/peak vs the campus meter on the
        same calendar days.
      </Callout>

      <H2>Weather: EPW vs Open-Meteo (same days)</H2>
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

      <H2>Load: EnergyPlus vs BAS meter (99 days)</H2>
      <Text tone="secondary" size="small">
        Mean daily kWh by month. BAS = sum of hourly kw_avg. PPO / heuristic = LIVE
        A04 day-MDP. Source: plots/rl_report/episodes.csv + demand_vs_web_weather_hourly.
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
        ASHRAE Guideline 14 whole-building hourly CVRMSE targets are typically ~20–30%
        for calibrated models. 30% energy CVRMSE with r≈0.67 is screening-grade: PPO
        matches mean kWh; peaks run ~35 kW high (175 vs 141 kW). Heuristic/random burn
        extra kWh. Do not treat ΔkWh as bill savings. GL14 is a twin/calibration claim,
        not an RL-vs-BAS claim.
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
                fills all of Nov–Mar plus Oct/Apr shoulders (30/31/31/28/31 in Nov–Mar).
              </Text>
              <Text tone="secondary">
                That is not 3× independent winters. It is almost the full AMY heating
                file once, plus milder shoulder days. Mean Nov–Mar OAT on the 100-day
                draw is 26.8 °F vs 28.0 °F on all 151 core days — the 100-day sample is
                already slightly colder, not cherry-warm.
              </Text>
              <Row gap={8}>
                <Pill tone="neutral">100 days: 17/22/24/19/18 by Nov–Mar</Pill>
                <Pill tone="info">300 days: 30/31/31/28/31</Pill>
              </Row>
            </Stack>
          </CardBody>
        </Card>
        <Card style={{ flex: 1 }}>
          <CardHeader>Ranking if we only had more draws of the same 99</CardHeader>
          <CardBody>
            <Stack gap={8}>
              <Text>
                Bootstrap (2,000 resamples with replacement) of the existing 99 common
                days. This is a precision check, not a new weather file.
              </Text>
              <BarChart
                categories={["PPO win", "Heuristic win"]}
                series={[
                  { name: "n=100 resample", data: [62.8, 37.2], tone: "info" },
                  { name: "n=300 resample", data: [75.6, 24.4], tone: "success" },
                ]}
                height={180}
              />
              <Text tone="secondary" size="small">
                PPO−random reward gap stays ~196. 5–95% interval tightens from 130–264
                (n=100) to 159–236 (n=300). DQN and random never win. PPO vs heuristic
                is still a coin-flip-ish at n=100 (63/37) and clearer at n=300 (76/24).
              </Text>
            </Stack>
          </CardBody>
        </Card>
      </Row>

      <Callout tone="warning" title="3× unique days would still be EPW replay">
        A real 300-day LIVE campaign would still drive EnergyPlus with the AMY EPW, not
        live BAS weather. Weather error is already small (~2 °F). Extra days buy
        ranking confidence and shoulder coverage, not a new climate. Peak CVRMSE stays
        the calibration gap. Cost is ~3× wall time (~12 hours of E+ days on this box).
      </Callout>

      <Text tone="secondary" size="small">
        Reward gap units are the day-MDP score (more positive = better). PPO mean
        reward −2906 vs random −3138 on the published unique-100 pack. Open this file
        in Cursor as a canvas (cursor/canvas). GitHub shows the source only.
      </Text>
    </Stack>
  );
}
