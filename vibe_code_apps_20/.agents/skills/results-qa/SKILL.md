# Results Quality Assurance

## Purpose
Detect invalid, implausible, or misleading model outcomes.

## Invoke when
Before ranking or reporting savings.

## Required inputs
- Baseline and measure results
- measure mechanism
- building area
- end-use context

## Procedure
1. Verify hashes.
2. Check signs and magnitudes.
3. Compare end-use changes to causal mechanism.
4. Calculate intensity metrics.
5. Flag baseline leakage and double counting.
6. Assign disposition.

## Outputs
- QA report
- quality flags
- approved/rejected result

## Guardrails
Do not repair suspect results by editing outputs.

## Validation
Independent reviewer signs disposition; checklist passes.
