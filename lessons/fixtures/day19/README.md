# Day 19 public fixtures

[Day 19 brief](../../day19.md)

`valid.csv`: three readings, count 3, minimum 68, maximum 72, mean 70. The values use the same intended unit; averaging unrelated engineering quantities is outside this exercise.

`empty.csv`: no readings; no numeric mean is defined. `malformed.csv`: only lines 1 and 7 are valid under the declared grammar. A skip-invalid implementation summarizes those two values (mean 70); a strict implementation fails according to its documented contract. `invalid_utf8.csv` must not be silently accepted as a valid UTF-8 text file. Test missing-file behavior with a path that really does not exist. Create your own over-64-KiB test file in student-work rather than adding a large tracked fixture.

These expected results specify behavior, not an implementation.
