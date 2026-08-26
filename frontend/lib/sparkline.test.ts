import { describe, expect, it } from "vitest";
import { buildSparkline, type SparklinePoint } from "./sparkline";

/**
 * The sparkline sits beside a headline asserting that a metric moved, so the
 * two must not contradict each other. Most of these cases are the degenerate
 * ones, because that is where the obvious arithmetic draws something wrong
 * without failing.
 */

const W = 160;
const H = 44;

const series = (...values: number[]): SparklinePoint[] =>
  values.map((value, i) => ({ ts: `2026-01-${String(i + 1).padStart(2, "0")}`, value }));

/** Pull the coordinate pairs back out of a path string. */
const coords = (path: string) =>
  path
    .split(" ")
    .map((c) => c.slice(1).split(",").map(Number))
    .map(([x, y]) => ({ x, y }));

describe("shape of the path", () => {
  it("starts with a move and continues with lines", () => {
    const { path } = buildSparkline(series(1, 2, 3), W, H)!;
    expect(path.startsWith("M")).toBe(true);
    expect(path.split(" ").slice(1).every((c) => c.startsWith("L"))).toBe(true);
  });

  it("plots one coordinate per point", () => {
    expect(coords(buildSparkline(series(1, 2, 3, 4, 5), W, H)!.path)).toHaveLength(5);
  });

  it("spans the full width, first point to last", () => {
    const c = coords(buildSparkline(series(1, 2, 3, 4), W, H)!.path);
    expect(c[0].x).toBe(0);
    expect(c[c.length - 1].x).toBe(W);
  });

  it("spaces points evenly", () => {
    const c = coords(buildSparkline(series(1, 2, 3, 4, 5), W, H)!.path);
    const gaps = c.slice(1).map((p, i) => p.x - c[i].x);
    expect(new Set(gaps).size).toBe(1);
  });

  it("puts the highest value above the lowest", () => {
    // SVG y grows downward, so a rising metric must produce a smaller y.
    const c = coords(buildSparkline(series(10, 90), W, H)!.path);
    expect(c[1].y).toBeLessThan(c[0].y);
  });

  it("keeps every point inside the box, with room for the stroke", () => {
    const c = coords(buildSparkline(series(0, 50, 100, 25), W, H)!.path);
    for (const { y } of c) {
      expect(y).toBeGreaterThanOrEqual(2);
      expect(y).toBeLessThanOrEqual(H - 2);
    }
  });

  it("reports the last point for the end dot", () => {
    const g = buildSparkline(series(5, 1, 9), W, H)!;
    const c = coords(g.path);
    expect(g.last).toEqual(c[c.length - 1]);
  });
});

describe("a series that has not moved", () => {
  it("draws down the middle, not along the floor", () => {
    // Pinning a flat metric to the bottom reads as "collapsed to its minimum",
    // which is the opposite of what an unchanged metric means.
    const c = coords(buildSparkline(series(50, 50, 50, 50), W, H)!.path);
    expect(c.every((p) => p.y === H / 2)).toBe(true);
  });

  it("does the same at zero", () => {
    const c = coords(buildSparkline(series(0, 0, 0), W, H)!.path);
    expect(c.every((p) => p.y === H / 2)).toBe(true);
  });

  it("still draws a full-width line", () => {
    const c = coords(buildSparkline(series(7, 7), W, H)!.path);
    expect([c[0].x, c[1].x]).toEqual([0, W]);
  });
});

describe("gaps and bad data", () => {
  it("skips a point with no value rather than losing the whole chart", () => {
    // One non-finite value poisons min and max, and with them every coordinate;
    // the SVG then renders nothing at all, silently.
    const withGap = [...series(10, 20), { ts: "2026-01-03", value: NaN }, ...series(30)];
    const g = buildSparkline(withGap, W, H);
    expect(g).not.toBeNull();
    expect(coords(g!.path)).toHaveLength(3);
    expect(g!.path).not.toContain("NaN");
  });

  it("survives an infinite value", () => {
    const g = buildSparkline([...series(1, 2), { ts: "2026-01-03", value: Infinity }], W, H);
    expect(g!.path).not.toContain("Infinity");
  });

  it("treats a null coming back as JSON as a gap", () => {
    const g = buildSparkline(
      [...series(4, 8), { ts: "2026-01-03", value: null as unknown as number }],
      W,
      H
    );
    expect(coords(g!.path)).toHaveLength(2);
  });

  it("returns null for an empty series", () => {
    expect(buildSparkline([], W, H)).toBeNull();
  });

  it("returns null for a single point, which has no trend to show", () => {
    expect(buildSparkline(series(42), W, H)).toBeNull();
  });

  it("returns null when only one point survives filtering", () => {
    expect(buildSparkline([...series(5), { ts: "x", value: NaN }], W, H)).toBeNull();
  });

  it("handles negative values", () => {
    const c = coords(buildSparkline(series(-40, -10), W, H)!.path);
    expect(c[1].y).toBeLessThan(c[0].y);
  });
});

describe("the area fill", () => {
  it("closes the line down to the bottom edge", () => {
    const { areaPath } = buildSparkline(series(1, 2, 3), W, H)!;
    expect(areaPath.endsWith(`L${W},${H} L0,${H} Z`)).toBe(true);
  });

  it("keeps the stroked line as its opening", () => {
    const { path, areaPath } = buildSparkline(series(1, 5, 2), W, H)!;
    expect(areaPath.startsWith(path)).toBe(true);
  });
});

describe("rounding", () => {
  it("trims floating-point noise out of the path", () => {
    // 160/6 is 26.666…; unrounded it puts seventeen digits into the DOM.
    const { path } = buildSparkline(series(1, 2, 3, 4, 5, 6, 7), W, H)!;
    for (const n of path.match(/-?\d+\.\d+/g) ?? []) {
      expect(n.split(".")[1].length).toBeLessThanOrEqual(2);
    }
  });
});
