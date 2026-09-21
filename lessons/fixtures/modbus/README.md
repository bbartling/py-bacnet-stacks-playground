# Synthetic Modbus known-answer inputs

[Day 64](../../day64.md) · [Day 68](../../day68.md)

All files contain hexadecimal bytes, not recorded device traffic.

| File | Public expected fields |
| --- | --- |
| read-request.hex | TCP transaction 1, protocol 0, length 6, unit 1, function 03, starting wire address 0, quantity 2 |
| read-response.hex | TCP transaction 1, length 7, unit 1, function 03, byte count 4, raw registers 42 and 100 |
| exception-response.hex | TCP transaction 1, length 3, unit 1, exception function 0x83, exception code 2 |
| rtu-read-request.hex | RTU unit 1, function 03, start 0, quantity 2, CRC bytes c4 0b in transmitted order |

There is no RTU CRC in the TCP files. RTU frame bytes alone cannot establish a serial silent interval. Use the official protocol/serial guides for interpretation, and an independent endpoint for live evidence. Mutations such as truncation, excessive quantity, wrong ID and bad CRC belong in your own test corpus.
