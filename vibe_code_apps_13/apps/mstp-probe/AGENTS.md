# Phase 2 Probe Agent Rules

This is an MS/TP-only test client/master for the Phase 2 device. It owns the other tty and never opens a UDP socket. Its scripted output is test evidence, not production UI.

Correlate invoke IDs, responses and errors; bound retries/timeouts; exercise Who-Is/I-Am, RP, RPM, WP, priority/relinquish and negative cases. Do not hide a timeout by retrying forever.

