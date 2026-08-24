# Skill — Utility Tariff Evidence

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
- `VERIFIED_HISTORICAL_TARIFF`
- `CANDIDATE_HISTORICAL_TARIFF`
- `ILLUSTRATIVE_TARIFF`

Never present candidate or illustrative cost as a reconstructed utility invoice.
