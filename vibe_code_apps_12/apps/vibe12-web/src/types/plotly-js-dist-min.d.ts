declare module "plotly.js-dist-min" {
  import type { PlotlyHTMLElement } from "plotly.js";
  const Plotly: {
    react: (
      root: HTMLElement | string,
      data: unknown[],
      layout?: unknown,
      config?: unknown,
    ) => Promise<PlotlyHTMLElement>;
    purge: (root: HTMLElement | string) => void;
  };
  export default Plotly;
}
