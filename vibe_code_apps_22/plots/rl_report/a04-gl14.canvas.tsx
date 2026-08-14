import {
  BarChart,
  Callout,
  Card,
  CardBody,
  CardHeader,
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

const MONTHS = [
  "Aug 25",
  "Sep 25",
  "Oct 25",
  "Nov 25",
  "Dec 25",
  "Jan 26",
  "Feb 26",
  "Mar 26",
  "Apr 26",
  "May 26",
];
const PCT = [1.71, 2.93, 8.71, 8.11, 11.7, -1.77, -14.19, -5.45, -15.46, 1.59];
const BILL_KWH = [32789, 31350, 32552, 42097, 67328, 81491, 67205, 51938, 42296, 31398];
const A04_KWH = [33349, 32268, 35386, 45512, 75205, 80050, 57669, 49108, 35757, 31897];
const DUR_H = [
  "0",
  "10",
  "20",
  "30",
  "40",
  "50",
  "60",
  "70",
  "80",
  "90",
  "100",
];
const DUR_ACT = [286.5, 137.2, 101.5, 83.0, 67.5, 55.0, 45.5, 37.5, 23.5, 19.5, 16.0];
const DUR_A04 = [267.5, 169.4, 133.1, 99.3, 61.9, 33.7, 21.2, 9.4, 9.4, 9.4, 9.4];
const BINS = ["0-20", "20-40", "40-60", "60-80", "80-100", "100-120", "120-140", "140-160", "160-180", "180-200"];
const BIN_ACT = [10.28, 23.25, 20.01, 14.56, 11.36, 6.89, 4.11, 3.44, 2.65, 1.54];
const BIN_A04 = [38.77, 13.73, 6.86, 6.43, 4.32, 6.67, 5.0, 5.89, 4.78, 3.51];

export default function A04Gl14() {
  return (
    <Stack gap={20}>
      <Stack gap={6}>
        <Row gap={8} align="center">
          <H1>A04 meets monthly Guideline 14</H1>
          <Pill tone="success" active>
            PASS
          </Pill>
        </Row>
        <Text tone="secondary">
          Frozen-baseline W2A plant twin lakeside_w2a_a04_dual_champion.idf vs billed
          kWh (Aug 2025–May 2026, n=10). Schedules and plant knobs stay as calibrated.
          Nobody is writing DualSP from PPO here.
        </Text>
      </Stack>

      <Grid columns={4} gap={12}>
        <Stat value="PASS" label="Monthly GL14 gate" tone="success" />
        <Stat value="+0.98%" label="NMBE (scorecard +0.984%)" tone="success" />
        <Stat value="10.45%" label="CVRMSE (scorecard 10.447%)" tone="success" />
        <Stat value="287 kW" label="Jan-26 design-day peak" />
      </Grid>

      <Callout tone="info" title="Two different tests">
        GL14 here is billed monthly kWh: |NMBE| ≤ 5% and CVRMSE ≤ 15%, p=1. The
        unique-100 PPO vs CS-meter overlay is a different experiment (agent-operated
        days). Passing GL14 does not mean hourly shape is GO, and failing the PPO
        overlay does not reopen this monthly gate.
      </Callout>

      <H2>Guideline 14 terms (tutorial)</H2>
      <Text tone="secondary">
        Both numbers use the same 10 billed months. They are not two different
        time series. NMBE is the whole-window bias (the “did the year of bills
        add up?” check). CVRMSE is the month-to-month scatter (the “did each
        month land?” check). A04 must pass both.
      </Text>
      <Row gap={12} align="stretch">
        <Card style={{ flex: 1 }}>
          <CardHeader>NMBE — window / year bias</CardHeader>
          <CardBody>
            <Stack gap={8}>
              <Stat value="+0.98%" label="A04 vs |NMBE| ≤ 5%" tone="success" />
              <Text>
                Normalized Mean Bias Error. Sum of (bill − sim) over all 10
                months, scaled by mean bill. Positive here: bills a bit higher
                than A04 overall (twin slightly low on the year). Over and under
                months cancel, so NMBE can look fine while February is −14%.
              </Text>
              <Text tone="secondary" size="small">
                Formula: 100 × sum(m − ŷ) / ((n−1) × mean(m)). Think “net kWh
                over the billing window,” not a per-month cap.
              </Text>
            </Stack>
          </CardBody>
        </Card>
        <Card style={{ flex: 1 }}>
          <CardHeader>CVRMSE — month-to-month scatter</CardHeader>
          <CardBody>
            <Stack gap={8}>
              <Stat value="10.45%" label="A04 vs CVRMSE ≤ 15%" tone="success" />
              <Text>
                Coefficient of Variation of RMSE. Squares every month’s miss, so
                Feb −14% and Apr −15% still count even if the year nets near
                zero. This is the check that the monthly pattern is not wild.
              </Text>
              <Text tone="secondary" size="small">
                Formula: 100 × sqrt(sum((m − ŷ)²)/(n−1)) / mean(m). Think
                “typical month error as a % of average bill.”
              </Text>
            </Stack>
          </CardBody>
        </Card>
      </Row>
      <Table
        headers={["Term", "What it answers", "Gate", "A04"]}
        rows={[
          ["NMBE", "Whole 10-month window bias (year-ish net)", "|NMBE| ≤ 5%", "+0.98% PASS"],
          ["CVRMSE", "How much individual months bounce", "≤ 15%", "10.45% PASS"],
          ["Month % diff", "Diagnostic line only — not a gate", "none", "Feb −14%, Apr −15% ok"],
          ["Hourly CVRMSE", "Different screen; not this A04 claim", "≤ 30% if you claim hourly", "not the billed-month pass"],
        ]}
      />
      <Callout tone="neutral" title="Not 15-minute GL14">
        Interval / DSM shape is a separate honesty gap (load-duration below).
        Passing monthly billed NMBE+CVRMSE does not mean hourly or 15-min GL14.
      </Callout>

      <H2>Monthly percent difference (the GL14 series)</H2>
      <Text tone="secondary" size="small">
        (A04 sim − billed kWh) / billed kWh. Source: champion sim eplusmtr.csv
        Electricity:Facility monthly vs utilities billed kWh. Reconstructed NMBE
        +0.981%, CVRMSE 10.451% — matches the 2026-08-09 scorecard within rounding.
        Individual months may exceed ±5%; the gate is on the 10-month NMBE/CVRMSE,
        not each month.
      </Text>
      <LineChart
        categories={MONTHS}
        series={[{ name: "Monthly % difference (sim vs bill)", data: PCT, tone: "info" }]}
        referenceLines={[
          { value: 0, label: "0%" },
          { value: 5, label: "+5%", tone: "warning" },
          { value: -5, label: "−5%", tone: "warning" },
        ]}
        beginAtZero={false}
        yMin={-20}
        yMax={20}
        height={240}
        valueSuffix="%"
      />

      <Card>
        <CardHeader>Monthly kWh used in the gate</CardHeader>
        <CardBody>
          <Table
            headers={["Month", "Billed kWh", "A04 kWh", "% diff"]}
            rows={MONTHS.map((label, i) => [
              label,
              BILL_KWH[i].toLocaleString(),
              A04_KWH[i].toLocaleString(),
              `${PCT[i] > 0 ? "+" : ""}${PCT[i]}%`,
            ])}
            rowTone={PCT.map((p) =>
              Math.abs(p) > 10 ? "warning" : undefined,
            )}
          />
        </CardBody>
      </Card>

      <H2>Load-duration vs actual (not a GL14 gate)</H2>
      <Text tone="secondary" size="small">
        Same 10 months, hourly. Actual = demand_interval_kw.csv resampled to hourly
        mean kW. A04 = Electricity:Facility hourly J → kW. Highest hours at 0% of
        duration. Peaks land near each other (~287 vs ~267 kW). A04 spends more hours
        at very low kW (night/weekend / setback).
      </Text>
      <LineChart
        categories={DUR_H}
        series={[
          { name: "Actual interval (hourly mean kW)", data: DUR_ACT, tone: "neutral" },
          { name: "A04 frozen (hourly kW)", data: DUR_A04, tone: "info" },
        ]}
        height={240}
        fill
      />
      <Text tone="secondary" size="small">
        X: % of hours in the 10-month window. Y: kW. Source: CS interval meter and
        A04 champion sim, Aug 2025–May 2026.
      </Text>

      <H2>Share of hours by load bin (% of profile)</H2>
      <Text tone="secondary" size="small">
        Percent of hours in each 20 kW bin. This is the old “what fraction of the
        load profile lives where” plot. Actual mass is 20–80 kW. A04 piles 39% of
        hours into 0–20 kW. Monthly energy can still pass GL14 while the interval
        mix differs — that is why monthly GL14 ≠ interval/DSM GO.
      </Text>
      <BarChart
        categories={BINS}
        series={[
          { name: "% of actual hours", data: BIN_ACT, tone: "neutral" },
          { name: "% of A04 hours", data: BIN_A04, tone: "info" },
        ]}
        height={260}
        valueSuffix="%"
        showValues={false}
      />
    </Stack>
  );
}
