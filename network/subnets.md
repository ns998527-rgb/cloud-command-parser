# Task 5: Subnetting 10.20.0.0/16

## Method
Allocate from the largest requirement to the smallest, starting at 10.20.0.0, each subnet right after the previous one.
A subnet needs `2^(32-prefix) - 2 >= hosts`, so the smallest prefix is the largest `prefix` value that still fits.

| Subnet | Hosts needed | Smallest fit | Working |
|---|---|---|---|
| app | 1,000 | /22 | /23 gives 2^9 - 2 = 510 (too few); /22 gives 2^10 - 2 = 1,022 |
| public | 250 | /24 | /25 gives 2^7 - 2 = 126 (too few); /24 gives 2^8 - 2 = 254 |
| data | 100 | /25 | /26 gives 2^6 - 2 = 62 (too few); /25 gives 2^7 - 2 = 126 |
| management | 20 | /27 | /28 gives 2^4 - 2 = 14 (too few); /27 gives 2^5 - 2 = 30 |

## Result

| Subnet | Network address | Prefix | Usable host range | Broadcast | Usable hosts |
|---|---|---|---|---|---|
| app | 10.20.0.0 | /22 | 10.20.0.1 - 10.20.3.254 | 10.20.3.255 | 1,022 |
| public | 10.20.4.0 | /24 | 10.20.4.1 - 10.20.4.254 | 10.20.4.255 | 254 |
| data | 10.20.5.0 | /25 | 10.20.5.1 - 10.20.5.126 | 10.20.5.127 | 126 |
| management | 10.20.5.128 | /27 | 10.20.5.129 - 10.20.5.158 | 10.20.5.159 | 30 |

Each subnet starts where the previous one ended: app ends at 10.20.3.255, public starts at 10.20.4.0 and ends at 10.20.4.255,
data starts at 10.20.5.0 and ends at 10.20.5.127, and management starts at 10.20.5.128. All four are aligned to their block size,
so every network address is a multiple of its block (app 1,024 addresses, public 256, data 128, management 32).

## NACL for the public subnet (`network/nacl.json`)

| Direction | Rule | Match | Action |
|---|---|---|---|
| Inbound | 90 | all protocols, source 198.51.100.0/24 | deny |
| Inbound | 100 | TCP 443 from 0.0.0.0/0 | allow |
| Inbound | 110 | TCP 80 from 0.0.0.0/0 | allow |
| Inbound | 120 | TCP 22 from 10.20.5.128/27 (management) | allow |
| Inbound | 130 | TCP 1024-65535 from 10.20.0.0/22 (app), replies | allow |
| Outbound | 100 | TCP 8000 to 10.20.0.0/22 (app) | allow |
| Outbound | 110 | TCP 1024-65535 to 0.0.0.0/0, replies to clients | allow |

Anything that matches no rule is denied (the implicit final deny).

## Why replies need their own rules, and why rule order matters

A NACL is stateless: it does not remember that an inbound request was allowed, so it judges the reply packet on its own as a fresh packet.
A client connects to the load balancer on TCP 443 from an ephemeral port (1024-65535). The inbound rule 100 lets the request in, but the
response travels outbound to that ephemeral port, which only the outbound rule 110 allows. Without it the request arrives and the reply is
dropped. The same holds for the load balancer calling the app on TCP 8000: the outbound rule 100 sends the request, and the app's reply
comes back inbound to an ephemeral port, which is only allowed by inbound rule 130.

Rules are evaluated from the lowest number upward and the first match decides. The deny for 198.51.100.0/24 is rule 90, lower than the
allow rules for ports 443 and 80 (100 and 110). A packet from 198.51.100.9 to port 443 therefore hits rule 90 first and is denied. If the
deny were numbered above 100, the packet would match the allow-443 rule first and be let in, and the deny would never be reached.
