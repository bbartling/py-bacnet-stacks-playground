---
name: utility-tariff
description: Establish historical electricity tariff evidence and label verified, candidate, and illustrative cost models correctly.
---

# Utility tariff evidence

## Goal
Model electricity cost without confusing an illustrative tariff with the building's actual historical billing arrangement.

## Procedure
1. Identify service territory and measured-data dates.
2. Find archived tariff sheets effective during those dates.
3. Prove the customer's actual rate assignment from a bill, account record, procurement record or equivalent evidence before calling it verified.
4. Encode seasons, TOU windows, holidays, billing demand, ratchets/floors and adjustments only when supported.
5. Preserve tariff source/version and effective dates.
6. Use the same timezone and interval convention as the measured meter.

## Required labels
- `VERIFIED`: account, meter boundary, source document, and effective period are proven.
- `CANDIDATE`: authentic schedule/scenario, but account-period binding is not proven.
- `ILLUSTRATIVE`: synthetic research scenario.

Never present candidate or illustrative cost as a reconstructed utility invoice.
