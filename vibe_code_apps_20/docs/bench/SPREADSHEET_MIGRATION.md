# Spreadsheet migration

A safe migration process is:

1. Inventory every sheet, formula count, named range, and visible input cell.
2. Group workbook tabs into algorithms such as schedule reduction, DCV,
   static-pressure reset, SAT reset, CHW/HW reset, economizer, and M&V.
3. Extract inputs and assumptions into YAML.
4. Reproduce each workbook result with a small pure function.
5. Add golden tests comparing Python outputs against known spreadsheet outputs.
6. Preserve units, rounding, and default assumptions explicitly.
7. Mark every algorithm as `screening`, `engineering`, or `calibrated`.

The CLI command `inspect-xlsx` provides a first-pass workbook inventory.
