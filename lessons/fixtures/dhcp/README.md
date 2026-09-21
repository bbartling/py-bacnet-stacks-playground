# Synthetic DHCPv4 Discover

[Day 94](../../day94.md)

`discover.hex` contains 300 DHCP/BOOTP payload bytes only (no UDP/IP/Ethernet). Expected fields: op 1, Ethernet htype 1, hlen 6, xid 0x12345678, broadcast flag set, client hardware address 02:00:00:00:00:01, DHCP cookie 63 82 53 63, option 53 Discover, option 55 requesting options 1/3/6, then End and padding. Zero addresses represent a not-yet-configured synthetic client. This is not a lease record or a successful DHCP exchange.
