import type { DiffRow } from "../types";

// Myers diff (O((N+M)D) time/space, D = edit distance). Efficient for large,
// mostly-similar texts like consecutive request bodies in a growing conversation
// — unlike a plain O(N*M) DP table, which chokes once bodies reach thousands of lines.
const MAX_DEPTH = 4000;

type VMap = Record<number, number>;

export function diffLines(oldText: string, newText: string): DiffRow[] | null {
  const a = oldText.split("\n");
  const b = newText.split("\n");
  const n = a.length;
  const m = b.length;

  const max = Math.min(n + m, MAX_DEPTH * 2);
  const v: VMap = { 1: 0 };
  const trace: VMap[] = [];
  let solved = -1;

  outer: for (let d = 0; d <= max; d++) {
    trace.push({ ...v });
    for (let k = -d; k <= d; k += 2) {
      let x;
      if (k === -d || (k !== d && v[k - 1] < v[k + 1])) {
        x = v[k + 1];
      } else {
        x = v[k - 1] + 1;
      }
      let y = x - k;
      while (x < n && y < m && a[x] === b[y]) {
        x++;
        y++;
      }
      v[k] = x;
      if (x >= n && y >= m) {
        solved = d;
        break outer;
      }
    }
  }

  if (solved === -1) return null;

  const result: DiffRow[] = [];
  let x = n;
  let y = m;
  for (let d = solved; d > 0; d--) {
    const vd = trace[d];
    const k = x - y;
    const prevK = k === -d || (k !== d && vd[k - 1] < vd[k + 1]) ? k + 1 : k - 1;
    const prevX = vd[prevK];
    const prevY = prevX - prevK;

    while (x > prevX && y > prevY) {
      result.push({ type: "same", text: a[x - 1] });
      x--;
      y--;
    }
    if (x === prevX) {
      result.push({ type: "add", text: b[y - 1] });
    } else {
      result.push({ type: "remove", text: a[x - 1] });
    }
    x = prevX;
    y = prevY;
  }
  while (x > 0 && y > 0) {
    result.push({ type: "same", text: a[x - 1] });
    x--;
    y--;
  }

  result.reverse();
  return result;
}
