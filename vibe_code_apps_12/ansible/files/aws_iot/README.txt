Place AWS IoT device certificate files here before running deploy.yml.

Default filenames (group_vars/pi_bcn.yml):
  vibe-code-app-12-temp-sensor.cert.pem
  vibe-code-app-12-temp-sensor.private.key

One-time copy from the connect package on your control machine:

  cd vibe_code_apps_12
  ./ansible/prepare_aws_iot_certs.sh

SHARED CERT ON ALL EDGES (recommended for lab / small fleet)
------------------------------------------------------------
You can deploy the SAME .pem + .key to every Linux BACnet gateway.
Building isolation is by MQTT topic (site_id / building_id in host_vars),
not by separate certs.

Requirements when reusing one cert:
  1. IoT policy allows iot:Publish on arn:...:topic/vibe12/*
     (and sdk/test/python only if you still use legacy GPIO topic)
  2. IoT policy allows iot:Connect for each edge client ID:
       vibe12-*   (covers vibe12-{{ inventory_hostname }} default)
       vibe12-gpio-bacnet-pi   (boss Pi GPIO service)
  3. Each edge host has a UNIQUE bacnet_edge_client_id in host_vars
     (default: vibe12-{{ inventory_hostname }} from group_vars)

Per-building gateway host_vars example: host_vars/gateway.example.yml

Optional later: one AWS IoT Thing + cert per building for tighter IAM.
Same Ansible playbook — only change cert filenames in host_vars.

These files are gitignored here and on the Pi (~/vibe_code_apps_12/aws_iot_certs/).
