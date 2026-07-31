import bpy, time
def _start():
    try:
        if hasattr(bpy.ops, "blendermcp"):
            bpy.ops.blendermcp.start_server()
            print("MCP_STARTED")
        else:
            print("MCP_OPS_MISSING")
    except Exception as e:
        print("MCP_START_FAIL", e)
bpy.app.timers.register(_start, first_interval=2.0)
