import "./index.css";
import { loadRuntimeGatewayScript } from "./runtime-config";
import { startRouter } from "./router";
import { connectBasWebSocket } from "./ws";

await loadRuntimeGatewayScript();

const root = document.getElementById("root");
if (!root) throw new Error("missing #root");

connectBasWebSocket();
startRouter(root);
