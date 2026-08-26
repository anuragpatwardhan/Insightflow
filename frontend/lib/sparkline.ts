/**
 * Sparkline geometry, kept out of the component so it can be checked directly.
 *
 * The chart sits next to a headline claiming a metric moved, so the two have to
 * agree. The cases that matter are the degenerate ones — a flat series, a gap in
 * the data — where the obvious arithmetic draws something that contradicts the
 * text beside it.
 */

export type SparklinePoint = { ts: string; value: number };

export type SparklineGeometry = {
  /** The stroked line. */
  path: string;
  /** The same line closed along the bottom edge, for the gradient fill. */
  areaPath: string;
  /** Where to sit the end-of-series dot. */
  last: { x: number; y: number };
};

/** Vertical breathing room so the stroke and the end dot are not clipped. */
const PADDING = 2;

/**
 * Turn a series into SVG paths, or null when there is nothing honest to draw.
 *
 * Points whose value is not finite are dropped rather than plotted: a single
 * null from a day with no data would otherwise poison min and max, and every
 * coordinate with them, leaving a blank box where the trend should be. Dropping
 * the gap draws the rest of the series, which is both more useful and more
 * truthful than showing nothing.
 */
export function buildSparkline(
  points: SparklinePoint[],
  width: number,
  height: number
): SparklineGeometry | null {
  const values = points.map((p) => p.value).filter((v) => Number.isFinite(v));
  if (values.length < 2) return null;

  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min;
  const usable = height - PADDING * 2;

  // A metric that has not moved is drawn down the middle. Scaling by a fallback
  // span would pin every point to the floor, which reads as "collapsed to its
  // minimum" — the opposite of what a flat series means.
  const y = (v: number) =>
    span === 0 ? height / 2 : height - PADDING - ((v - min) / span) * usable;

  const stepX = width / (values.length - 1);
  const coords = values.map((v, i) => ({ x: i * stepX, y: y(v) }));

  const path = coords
    .map(({ x, y }, i) => `${i === 0 ? "M" : "L"}${round(x)},${round(y)}`)
    .join(" ");

  return {
    path,
    areaPath: `${path} L${round(width)},${height} L0,${height} Z`,
    last: coords[coords.length - 1],
  };
}

/** Trim floating-point noise so the path stays readable in the DOM. */
function round(n: number): number {
  return Math.round(n * 100) / 100;
}
