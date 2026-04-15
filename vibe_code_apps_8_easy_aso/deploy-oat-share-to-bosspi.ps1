param(
    [string]$SshTarget = 'ben@192.168.204.12',
    [string]$RemoteVolttronRoot = '/home/ben/volttron',
    [string]$RemoteVolttronHome = '/home/ben/.volttron',
    [string]$LocalAgentRoot = (Join-Path $PSScriptRoot 'volttron_data\ben_bacnet\oat_share_agent')
)

$ErrorActionPreference = 'Stop'

$RemoteBenBacnet = "$RemoteVolttronRoot/volttron_data/ben_bacnet"

Write-Host "Copying oat_share_agent to $SshTarget ..."
scp -r $LocalAgentRoot "${SshTarget}:${RemoteBenBacnet}/"

$remoteScript = @"
set -e
cd $RemoteVolttronRoot
export VOLTTRON_HOME=$RemoteVolttronHome
source env/bin/activate

if vctl status 2>/dev/null | grep -q 'ben-oat-share'; then
  echo 'OAT share agent exists; restarting tag ben-oat-share'
  vctl restart --tag ben-oat-share
else
  echo 'OAT share agent not present; installing + starting'
  vctl install --vip-identity ben.oat.share --tag ben-oat-share $RemoteBenBacnet/oat_share_agent --config $RemoteBenBacnet/oat_share_agent/config
  vctl start --tag ben-oat-share
fi
sleep 2
vctl status
"@

Write-Host "Installing/restarting oat_share_agent on $SshTarget ..."
ssh $SshTarget $remoteScript
