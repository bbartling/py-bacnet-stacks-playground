import "./index.css";
import { startRouter } from "./router";
import { connectBasWebSocket } from "./ws";

const root = document.getElementById("root");
if (!root) throw new Error("missing #root");

connectBasWebSocket();
startRouter(root);
