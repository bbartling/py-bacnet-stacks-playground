param(
    [string]$SshTarget = 'ben@192.168.204.12',
    [string]$RemoteVolttronRoot = '/home/ben/volttron',
    [string]$RemoteVolttronHome = '/home/ben/.volttron',
    [string]$LocalAgentRoot = (Join-Path $PSScriptRoot 'volttron_data\ben_bacnet\app8_web_agent')
)

$ErrorActionPreference = 'Stop'

$RemoteBenBacnet = "$RemoteVolttronRoot/volttron_data/ben_bacnet"
$RemoteAgentPath = "$RemoteBenBacnet/app8_web_agent"

Write-Host "Copying app8_web_agent to $SshTarget ..."
scp -r $LocalAgentRoot "${SshTarget}:${RemoteBenBacnet}/"

$remoteScript = @"
set -e
cd $RemoteVolttronRoot
export VOLTTRON_HOME=$RemoteVolttronHome
source env/bin/activate

if vctl status 2>/dev/null | grep -q 'ben-app8-web'; then
  echo 'App 8 agent exists; restarting tag ben-app8-web'
  vctl restart --tag ben-app8-web
else
  echo 'App 8 agent not present; installing + starting'
  vctl install --vip-identity ben.app8.web --tag ben-app8-web $RemoteAgentPath --config $RemoteAgentPath/config
  vctl start --tag ben-app8-web
fi
sleep 3
vctl status
"@

Write-Host "Installing/restarting app8 agent on $SshTarget ..."
ssh $SshTarget $remoteScript
