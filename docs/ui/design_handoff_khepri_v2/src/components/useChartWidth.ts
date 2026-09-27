import * as React from "react";

/** Measures the rendered width of a chart container so SVG text stays at its real pixel size. */
export function useChartWidth(fallback = 600): [React.RefObject<HTMLDivElement>, number] {
  const ref = React.useRef<HTMLDivElement>(null);
  const [width, setWidth] = React.useState(fallback);
  React.useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const update = () => {
      const w = Math.round(el.getBoundingClientRect().width);
      if (w > 0) setWidth(w);
    };
    update();
    if (typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, width];
}
