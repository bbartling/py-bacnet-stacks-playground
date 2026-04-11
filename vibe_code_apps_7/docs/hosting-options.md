# Hosting options

## Current choice

Start with **option 1**:

- serve the BAS Lite UI from a VOLTTRON web-enabled agent
- expose lightweight JSON endpoints from the same agent
- stop there and judge whether the approach feels clean enough

## Why option 1 first

- lowest moving-part count
- fastest path to a Pi-hosted MVP
- honest test of whether VOLTTRON-native web serving is good enough
- avoids prematurely building a more split deployment shape

## Bail criteria for later move to option 2

Move to separately hosted frontend/backend later if any of these become annoying enough:

- static asset packaging/redeploy friction
- path-prefix routing ugliness
- auth/session awkwardness
- poor frontend dev loop
- too much product logic pushed into VOLTTRON only because it can host pages

## Current posture

Go hard on option 1 now, then stop and evaluate.
