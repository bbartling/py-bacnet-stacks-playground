# Commissioned BACnet point lists (device addresses, object IDs, Brick tags).
#
# Layout: commissioning/{site_id}/{building_id}/points.csv
#
# Backup from edge:
#   cd ansible && ./fetch_commissioning.sh --limit bacnet_pi -v
#
# Restore to edge (during deploy):
#   ansible copies commissioning/{site}/{building}/points.csv to the Pi when present.
