#!/usr/bin/env bash
# Example: register a new BACnet gateway in AWS IoT Core (Path B — one Thing + cert per gateway).
# Copy to register_iot_gateway.sh locally; never commit real values or PEM output.
#
# Usage:
#   export AWS_REGION=us-east-2
#   export THING=acme-vm-bbartling-gw
#   export SITE=acme
#   export BUILDING=vm-bbartling
#   export POLICY=vibe-code-app-12-temp-sensor-Policy
#   export CERT_DIR=ansible/files/aws_iot/acme-vm-bbartling
#   ./register_iot_gateway.example.sh
#
set -euo pipefail

: "${AWS_REGION:=us-east-2}"
: "${THING:?set THING e.g. acme-vm-bbartling-gw}"
: "${SITE:?set SITE e.g. acme}"
: "${BUILDING:?set BUILDING e.g. vm-bbartling}"
: "${POLICY:?set POLICY to your IoT policy name}"
: "${CERT_DIR:?set CERT_DIR e.g. ansible/files/aws_iot/acme-vm-bbartling}"

mkdir -p "$CERT_DIR"

aws iot create-thing --thing-name "$THING" --region "$AWS_REGION" \
  --attribute-payload "attributes={site_id=$SITE,building_id=$BUILDING}"

aws iot create-keys-and-certificate --set-as-active \
  --certificate-pem-outfile "$CERT_DIR/device.pem.crt" \
  --private-key-outfile "$CERT_DIR/private.key" \
  --region "$AWS_REGION" \
  --output json > "$CERT_DIR/create-cert.json"

CERT_ARN=$(python3 -c "import json; print(json.load(open('$CERT_DIR/create-cert.json'))['certificateArn'])")
aws iot attach-policy --policy-name "$POLICY" --target "$CERT_ARN" --region "$AWS_REGION"
aws iot attach-thing-principal --thing-name "$THING" --principal "$CERT_ARN" --region "$AWS_REGION"
chmod 600 "$CERT_DIR/private.key"
curl -fsS -o "$CERT_DIR/AmazonRootCA1.pem" https://www.amazontrust.com/repository/AmazonRootCA1.pem

echo "Thing $THING ready. Cert ARN: $CERT_ARN"
echo "Next: host_vars + inventory (gitignored), then ./deploy.sh --limit <host>"
