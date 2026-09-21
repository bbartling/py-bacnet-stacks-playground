# Synthetic DNS fixtures

[Day 46](../../day46.md)

`query.hex` asks IN/A for lab.example with ID 0x1234. `answer.hex` has the same question, one compressed-name IN/A answer 192.0.2.44 and TTL 60. `pointer-cycle.hex` is deliberately malformed: its question name points to itself at offset 12. A bounded decoder rejects the cycle. These fixtures do not prove a resolver exists or that example names have these public DNS records.
