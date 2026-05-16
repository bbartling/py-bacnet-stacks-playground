Place AWS IoT device certificate files here before running deploy.yml with enable_aws_iot: true.

Required filenames (match group_vars/pi_bcn.yml):
  vibe-code-app-12-temp-sensor.cert.pem
  vibe-code-app-12-temp-sensor.private.key

One-time copy from unzipped connect package on your dev machine:

  cd vibe_code_apps_12
  mkdir -p ansible/files/aws_iot
  cp aws_iot_core_test/vibe-code-app-12-temp-sensor.cert.pem ansible/files/aws_iot/
  cp aws_iot_core_test/vibe-code-app-12-temp-sensor.private.key ansible/files/aws_iot/

These files are gitignored in this folder and on the Pi (~/vibe_code_apps_12/aws_iot_certs/).
