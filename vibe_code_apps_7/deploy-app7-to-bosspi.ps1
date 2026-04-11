$ErrorActionPreference = 'Stop'

$PiHost = 'ben@192.168.204.12'
$LocalRoot = 'C:\Users\ben\Documents\py-bacnet-stacks-playground\vibe_code_apps_7\volttron_data\ben_bacnet\app7_web_agent'
$RemoteRoot = '/home/ben/volttron/volttron_data/ben_bacnet/app7_web_agent'

Write-Host 'Copying app7_web_agent to bosspi...'
scp -r $LocalRoot "${PiHost}:/home/ben/volttron/volttron_data/ben_bacnet/"

$remoteScript = @'
set -e
cd /home/ben/volttron
export VOLTTRON_HOME=/home/ben/.volttron
source env/bin/activate

if vctl status 2>/dev/null | grep -q 'ben-app7-web'; then
  echo 'App 7 agent exists; restarting tag ben-app7-web'
  vctl restart --tag ben-app7-web
else
  echo 'App 7 agent not present; installing + starting'
  vctl install --vip-identity ben.app7.web --tag ben-app7-web /home/ben/volttron/volttron_data/ben_bacnet/app7_web_agent --config /home/ben/volttron/volttron_data/ben_bacnet/app7_web_agent/config
  vctl start --tag ben-app7-web
fi
sleep 3
vctl status
'@

Write-Host 'Installing/restarting app7 agent on bosspi...'
ssh $PiHost $remoteScript
