import { Card, CardContent } from "@/components/ui/card";

const CHEAT = String.raw`VOLTTRON BACnet — Platform Driver (edge)

Assumptions: repo at ~/volttron, env activated, Python 3.10+ for current VOLTTRON 9.x / modular stacks.

1) BACnet utilities
   cd ~/volttron && source env/bin/activate && cd scripts/bacnet && ls

2) BACpypes.ini — set address to the edge NIC (not the remote device), e.g.
   [BACpypes]
   address: 192.168.1.50/24

3) Scan
   python bacnet_scan.py --range 0 4194303 --timeout 15 --csv-out devices.csv

4) Bulk configs
   python grab_multiple_configs.py devices.csv --out-directory ./scan_output --ini ./BACpypes.ini

5) Platform + proxy (examples — match your packaging: volttron-bacnet-proxy vs repo paths)
   vctl install volttron-bacnet-proxy --agent-config configs/bacnet-proxy.json \\
     --vip-identity platform.bacnet_proxy --start

   python scripts/install-agent.py -s services/core/PlatformDriverAgent \\
     -c services/core/PlatformDriverAgent/config --tag platform_driver --start

6) Driver main config (optional pacing)
   vctl config store platform.driver config configs/platform-driver.agent

7) Load BACnet device + registry
   vctl config store platform.driver registry_configs/ahu1.csv configs/ahu1.csv --csv
   vctl config store platform.driver devices/site/building/ahu1 configs/ahu1.config

8) Restart driver after edits
   vctl restart --tag platform_driver

9) Inspect
   vctl config list platform.driver
   vctl status

Notes: standalone bacnet_scan / grab scripts conflict with a running BACnet Proxy unless you use proxy_* variants. For weak devices set use_read_multiple false and tune max_per_request.
`;

export function BasDocsPage() {
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">BACnet &amp; driver cheat sheet</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Condensed operator notes. See VOLTTRON readthedocs for authoritative install and BACnet driver
          pages.
        </p>
      </div>
      <Card>
        <CardContent className="pt-6">
          <pre className="max-h-[70vh] overflow-auto whitespace-pre-wrap rounded-md bg-muted/50 p-4 font-mono text-xs leading-relaxed">
            {CHEAT}
          </pre>
        </CardContent>
      </Card>
    </div>
  );
}
