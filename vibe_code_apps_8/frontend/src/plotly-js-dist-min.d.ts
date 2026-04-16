declare module "plotly.js-dist-min" {
  const Plotly: {
    react: (el: HTMLDivElement, data: unknown[], layout: unknown, config: unknown) => void;
  };
  export default Plotly;
}
