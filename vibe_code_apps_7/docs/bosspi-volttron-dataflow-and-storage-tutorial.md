# bosspi VOLTTRON + BACnet + App 7 tutorial

This is the practical, human-readable, AI-friendly handoff for how the Raspberry Pi bench is put together, how data gets from BACnet into the App 7 web UI, what is currently stored locally, what is likely memory-only, how logging should be handled on a Pi without burning up the SD card, and how this bench now relates to the Open-FDD / VOLTTRON Central proof of concept.

This doc is intentionally a **working tutorial + architecture note + next-round checklist**.

---

## 1. Big picture

There are really **three** related systems in play now:

1. **bosspi (`192.168.204.12`)**
   - Raspberry Pi edge runtime
   - native VOLTTRON install in `~/volttron`
   - talks BACnet to the bench devices
   - hosts the App 7 web agent
   - now also runs a ForwardHistorian / forward agent toward Central

2. **Open-FDD / VOLTTRON Central host (`192.168.204.16`)**
   - Open-FDD repo: `~/open-fdd`
   - active repo: <https://github.com/bbartling/open-fdd>
   - branch used during the PoC: `dev/work`
   - Central is running via upstream `~/volttron-docker`
   - Open-FDD helper scripts under `./scripts/bootstrap.sh` make Central operations easier

3. **Bench BACnet devices**
   - `BensFakeAHU` → `192.168.204.13`
   - `Zone1VAV` → `192.168.204.14`

So the simple flow is:

**BACnet devices → VOLTTRON BACnet Proxy / Platform Driver on bosspi → App 7 web agent + optional forward agent → Central on .16**

---

## 2. Core online docs worth knowing

### VOLTTRON docs

- Main index: <https://volttron.readthedocs.io/en/main/index.html>
- Web framework docs: <https://volttron.readthedocs.io/en/main/agent-framework/web-framework.html>

Those are the canonical references for:
- how VOLTTRON agents register web endpoints / static files
- how the platform web service serves agent-hosted content
- how agents and the platform fit together

### Open-FDD repo

- Repo: <https://github.com/bbartling/open-fdd>

### Why these matter

The **hard parts** in this bench are usually:
1. getting BACnet up and running reliably on the Pi
2. getting the local VOLTTRON runtime healthy under systemd
3. getting App 7 served correctly through VOLTTRON’s web framework
4. getting edge forwarding / Central integration right

Once those are stable, the frontend and app behavior are much easier to iterate.

---

## 3. Current bosspi setup at a glance

### Host and paths

- Hostname: `bosspi`
- SSH: `ben@192.168.204.12`
- VOLTTRON repo: `/home/ben/volttron`
- `VOLTTRON_HOME`: `/home/ben/.volttron`
- systemd service: `volttron.service`

### Important shell setup

Use this every time before VOLTTRON commands:

```bash
cd /home/ben/volttron
export VOLTTRON_HOME=/home/ben/.volttron
source env/bin/activate
```

### Current important agents on bosspi

At the practical level, the bench has involved these agents:

- `platform.bacnet_proxy`
- `platform.driver`
- `listener.bacnet`
- `gl36...` custom bench agents
- `ben.app7.web`
- `platform.agent` (`vcp`) when Central-controlled mode is active
- `forward-to-central` (ForwardHistorian / forwarder) for Central PoC forwarding

---

## 4. How the BACnet data actually reaches the frontend

This is the most important mental model.

### Step A — BACnet proxy talks to devices

The VOLTTRON BACnet proxy agent is the low-level BACnet communications layer.

Its job is to:
- speak BACnet/IP to the bench devices
- issue Who-Is / reads / writes
- support Platform Driver access to point values

Bench devices currently used:
- `192.168.204.13` (`BensFakeAHU`)
- `192.168.204.14` (`Zone1VAV`)

### Step B — Platform Driver maps devices/points into VOLTTRON topics

Platform Driver sits on top of BACnet proxy and turns configured devices/points into publishable VOLTTRON data.

This is the key runtime step that makes device telemetry show up as topics like:
- `devices/BensFakeAHU/all`
- `devices/Zone1VAV/all`

That means:
- the proxy handles BACnet communication
- the driver handles device config, point polling, and topic publication

### Step C — Agents consume the published data

Once Platform Driver is publishing values, other agents can consume them.

For this bench that means things like:
- listener agents
- GL36 logic agents
- the App 7 web agent
- the ForwardHistorian / forward agent

### Step D — App 7 web agent serves the frontend and API

The App 7 web agent is not just static HTML. It is the app-specific layer that:
- serves the frontend assets through VOLTTRON’s web framework
- exposes app endpoints / routes
- reads current device/point state from the VOLTTRON side
- returns data the frontend can render

So the browser is not speaking BACnet.

The browser path is:

**browser → VOLTTRON web service → App 7 web agent → VOLTTRON data/topic/runtime layer → Platform Driver → BACnet Proxy → BACnet devices**

That separation is good because it keeps:
- BACnet complexity out of the browser
- device permissions and write behavior inside controlled agent logic
- frontend code focused on operator UX

### Step E — How the web code is served

VOLTTRON’s web framework docs are the right reference here:
- <https://volttron.readthedocs.io/en/main/agent-framework/web-framework.html>

The important practical idea is:
- an agent can register web routes / static files
- the platform web service serves that content
- App 7’s UI is therefore hosted by the running VOLTTRON platform itself

That is why the App 7 URL works as a VOLTTRON-served application instead of a separate nginx/node/etc. app stack.

---

## 5. Current local storage posture on the Pi

This section is the answer to: **is data in RAM, a DB, files, or all of the above?**

### 5.1 Current raw telemetry source of truth

The immediate source of truth for live telemetry is **not** a traditional local app database.

It is primarily:
- BACnet device reads
- Platform Driver publications
- agent runtime state

That means current values are fundamentally coming from the running VOLTTRON process and bench devices, not a big local SQL store built specifically for App 7.

### 5.2 App 7 current-state behavior

For App 7, the practical posture has been:
- current dashboard state is runtime-driven
- current values are effectively **memory/runtime-first**
- the app is not relying on a heavy always-growing local database for high-churn UI data

That is the right instinct for a Raspberry Pi.

### 5.3 Trend/history posture

The project notes already point toward:
- bounded trend handling
- a memory-first or lightweight approach
- avoiding chatty unbounded writes for dashboard/trend state

So for the next round, the safe assumption is:

- **live UI state:** runtime / in-memory first
- **short-term trend storage:** should stay bounded and intentionally designed
- **long-term durable historian:** only where really necessary, and with conscious write policy

### 5.4 VOLTTRON internal state on disk

Even when the app tries to stay memory-friendly, VOLTTRON itself still has disk-backed state under:
- `/home/ben/.volttron`

That includes things like:
- agent installation artifacts
- auth config
- keystores
- config store files
- runtime support files
- logs (depending on setup)

So “RAM only” is not literally true for the whole platform.

A better statement is:
- **high-churn app telemetry should be RAM-first / bounded**
- **platform/runtime control state still lives on disk where VOLTTRON expects it**

### 5.5 Current evidence from the Central PoC

During the edge-to-Central PoC:
- the edge used a forward agent / ForwardHistorian toward Central
- on Central, the historian agent had a `backup.sqlite`
- queue state looked empty / not backed up when auth was fixed

That suggests:
- Central side does have a durable-ish historian queue mechanism
- edge-to-Central forwarding is more historian-like than App 7’s local dashboard state

So local App 7 UI behavior and Central forwarding behavior are related, but they are not the same storage story.

---

## 6. Current logging posture and what it should be

### Current likely logging reality

The system today likely has logging in a few places:

1. **VOLTTRON logs**
   - `volttron.log`
   - `volttron.cfg.log`
   - possibly other agent/runtime logs under `VOLTTRON_HOME`

2. **systemd / journald**
   - `systemctl status volttron.service`
   - `journalctl -u volttron.service`

3. **app-level / custom agent logging**
   - custom agents may emit logs through the VOLTTRON process or to their own configured outputs

4. **possible file-based helper logging**
   - bench scripts or utility code may write CSV/debug artifacts if configured

### Current best interpretation

For the Pi, the setup is **not** “RAM only” in the strict sense.

But it **should** be treated as:
- **avoid high-rate, unbounded local file logging**
- use file logging deliberately
- keep debug verbosity off unless actively diagnosing something

### Best-practice Pi logging posture

To avoid SD-card wear / burnout:

#### Good practices

- keep high-frequency telemetry out of constantly growing flat files
- use bounded / rotating logs
- lower log verbosity during normal operation
- prefer in-memory caches for noisy UI/trend state
- only persist what is operationally useful
- ship or forward important data elsewhere rather than writing everything locally forever
- use journald retention limits intentionally if systemd/journald is part of the ops story
- periodically verify what is actually growing on disk

#### Avoid

- per-sample CSV/debug writes for every polled point forever
- giant unrotated `volttron.log` files
- multiple redundant local copies of the same telemetry
- writing every UI refresh / trend sample to disk if it is only needed for transient display

### Practical commands to inspect local logging / growth

Check service and recent logs:

```bash
systemctl status volttron.service --no-pager
journalctl -u volttron.service -n 100 --no-pager
```

Check likely VOLTTRON log files:

```bash
ls -lah /home/ben/.volttron
ls -lah /home/ben/.volttron/run
ls -lah /home/ben/.volttron | grep log
```

Find unexpectedly large files:

```bash
find /home/ben/.volttron -type f -printf '%s %p\n' | sort -nr | head -40
find /home/ben/volttron -type f -printf '%s %p\n' | sort -nr | head -40
```

That should be part of the next round: verify what is actually writing heavily before making assumptions.

---

## 7. SD-card burnout best practices for a Pi

This deserves its own blunt section.

### The goal

You do **not** want the Raspberry Pi SD card acting like a noisy historian disk.

### Strong defaults

- keep operational UI state in RAM when possible
- keep trend retention bounded
- rotate logs aggressively
- use INFO/WARN level in normal operation, not DEBUG forever
- move serious long-term telemetry retention off the Pi when possible
- use Central / another machine / a better storage medium for heavier retention

### If long-term local history becomes necessary

Prefer one of these before abusing the SD card:
- external SSD / better flash media
- remote historian / forwarded storage
- explicit downsampling / aggregation before persistence
- low-write SQLite with bounded retention, not uncontrolled append-everything patterns

### Human rule of thumb

On a Pi, ask this before adding any persistent write path:

> Does this data need to survive a reboot and be queried later, or is it only useful for a live dashboard right now?

If the answer is “live dashboard only,” favor RAM.

If the answer is “important historical evidence,” log it intentionally and with bounded retention.

---

## 8. systemd and startup posture

This matters because a lot of bench pain comes from mixing manual and service-managed starts.

### Current service

The Pi uses:
- `volttron.service`

So there are really two ways to interact with VOLTTRON:

1. **manual debugging mode**
   - stop systemd first
   - activate env
   - start manually
   - inspect logs

2. **normal service mode**
   - let systemd own startup
   - use `systemctl status` and `journalctl`

### Good systemd commands

```bash
sudo systemctl status volttron.service --no-pager
sudo systemctl stop volttron.service
sudo systemctl start volttron.service
sudo systemctl restart volttron.service
sudo systemctl enable volttron.service
journalctl -u volttron.service -n 100 --no-pager
```

### Important bench lesson from this PoC

If manual `./start-volttron` and `systemd` are both trying to manage the platform, you can end up with:
- stale VIP socket files
- startup confusion
- repeated restart loops
- misleading `vctl status` failures

So for troubleshooting:
- first decide whether you are in **manual mode** or **systemd mode**
- do not mix them carelessly

---

## 9. How BACnet bring-up is the hard part

This is the main reality of the bench.

The frontend is not usually the hard part.
The hard part is getting:
- BACnet network reachability
- BACnet proxy behavior
- Platform Driver config
- point naming / scaling / mapping
- stable polling
- writes only on approved points

### Practical bring-up ladder

1. Pi platform healthy
2. BACnet proxy healthy
3. Platform Driver healthy
4. device topics publishing
5. App 7 endpoints return data
6. frontend renders that data correctly
7. only then add Central forwarding / historian / extra workflows

If you skip that order, you can waste time debugging the web app when the real problem is the field-bus side.

---

## 10. How VOLTTRON Central fits now

The new proof of concept established:
- Open-FDD helper scripts on `.16` can serve as the Central control surface
- the Pi can run native VOLTTRON and forward toward Central
- auth between the edge forward agent and Central was the key unlock

### Important distinction

There are **two different Central-related edge concepts** in play:

1. **VCP / Central-controlled edge**
   - the Pi can be controlled / registered to Central
   - this is the VOLTTRON Central platform relationship

2. **ForwardHistorian / forward-to-central**
   - the Pi forwards telemetry toward Central-side historian handling
   - this is the data movement path

Both matter, but they are not the same thing.

### What the PoC showed

- Central `.16` web worked
- helper scripts on `.16` could retrieve server key and add auth
- on the Pi, `forward-to-central` changed from `BAD` to `GOOD` after Central auth add and restart

That is the key recreate lesson for next time.

---

## 11. Commands worth keeping handy

### On bosspi

```bash
cd /home/ben/volttron
export VOLTTRON_HOME=/home/ben/.volttron
source env/bin/activate
vctl status
```

### Check service-managed health

```bash
systemctl status volttron.service --no-pager
journalctl -u volttron.service -n 100 --no-pager
```

### Check App 7 in browser

- `http://192.168.204.12:8080/app7/index.html`

### On Central `.16`

```bash
cd ~/open-fdd
./scripts/bootstrap.sh --volttron-docker-serverkey
./scripts/bootstrap.sh --volttron-docker-agent-status
./scripts/bootstrap.sh --print-forward-historian-cheatsheet
```

### Add edge forwarder auth on Central

```bash
cd ~/open-fdd
OFDD_VOLTTRON_AUTH_CREDENTIALS='<edge-forward-public-key>' ./scripts/bootstrap.sh --volttron-docker-auth-add
```

---

## 12. What should be improved next round

### Documentation improvements

- explicitly document where App 7 keeps trend data today
- document whether any custom CSV logging is still enabled anywhere
- document actual `volttron.service` unit contents in this folder
- record the exact VOLTTRON version / branch / packaging used on bosspi

### Technical improvements

- add a cleaner “show recent forwarded data landed on Central” helper on `.16`
- add bounded retention policy notes if trend storage becomes more durable
- audit log file growth and document the results here
- decide whether App 7 should stay memory-first or gain a lightweight bounded local DB

### Ops improvements

- keep a single source-of-truth startup mode: manual debug vs systemd service
- document BACnet driver config files used for the two bench devices
- keep the forward-historian config file in a known reproducible location

---

## 13. Bottom line

If someone opens this folder cold, the correct high-level understanding should be:

- **bosspi is the edge runtime**
- **BACnet proxy + Platform Driver are the real data-ingest core**
- **App 7 is a VOLTTRON-served web agent on top of that**
- **live UI state should stay RAM-first / bounded on a Pi**
- **logging must be intentionally limited to avoid SD-card wear**
- **Central integration is now real enough to recreate, but the hard part remains getting BACnet and the edge runtime healthy first**

That is the actual architecture story.
