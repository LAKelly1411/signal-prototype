// Data for the sign-in page's timeline + heat-map art. A port of the data
// side of `_login_art` in dashboard/app.py: same formulas, same noise.

import { DAY_MS } from "@/lib/signals/time";

export const SCROLL = 40; // seconds for the timeline to travel one panel width

const M64 = (1n << 64n) - 1n;
const IV = [
  0x6a09e667f3bcc908n, 0xbb67ae8584caa73bn, 0x3c6ef372fe94f82bn, 0xa54ff53a5f1d36f1n,
  0x510e527fade682d1n, 0x9b05688c2b3e6c1fn, 0x1f83d9abfb41bd6bn, 0x5be0cd19137e2179n,
];
const SIGMA = [
  [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15],
  [14, 10, 4, 8, 9, 15, 13, 6, 1, 12, 0, 2, 11, 7, 5, 3],
  [11, 8, 12, 0, 5, 2, 15, 13, 10, 14, 3, 6, 7, 1, 9, 4],
  [7, 9, 3, 1, 13, 12, 11, 14, 2, 6, 5, 10, 4, 0, 15, 8],
  [9, 0, 5, 7, 2, 4, 10, 15, 14, 1, 11, 12, 6, 8, 3, 13],
  [2, 12, 6, 10, 0, 11, 8, 3, 4, 13, 7, 5, 15, 14, 1, 9],
  [12, 5, 1, 15, 14, 13, 4, 10, 0, 7, 6, 3, 9, 2, 8, 11],
  [13, 11, 7, 14, 12, 1, 3, 9, 5, 0, 15, 4, 8, 6, 2, 10],
  [6, 15, 14, 9, 11, 3, 0, 8, 12, 2, 13, 7, 1, 4, 10, 5],
  [10, 2, 8, 4, 7, 6, 1, 5, 15, 11, 9, 14, 3, 12, 13, 0],
];
const rotr = (x: bigint, n: bigint) => ((x >> n) | (x << (64n - n))) & M64;

/**
 * BLAKE2b with a 4-byte digest, for inputs under 128 bytes. Python's
 * `blake2b(digest_size=4)` bakes the digest length into the parameter block,
 * so its output is NOT a prefix of the 64-byte hash and Node's fixed
 * `blake2b512` cannot reproduce it.
 */
function blake2b4(data: Uint8Array): bigint {
  const h = [...IV];
  h[0] ^= 0x01010000n ^ 4n; // fanout 1, depth 1, no key, digest length 4
  const block = new Uint8Array(128);
  block.set(data);
  const dv = new DataView(block.buffer);
  const m = Array.from({ length: 16 }, (_, i) => dv.getBigUint64(i * 8, true));
  const v = [...h, ...IV];
  v[12] ^= BigInt(data.length);
  v[14] ^= M64; // final block
  const g = (a: number, b: number, c: number, d: number, x: bigint, y: bigint) => {
    v[a] = (v[a] + v[b] + x) & M64;
    v[d] = rotr(v[d] ^ v[a], 32n);
    v[c] = (v[c] + v[d]) & M64;
    v[b] = rotr(v[b] ^ v[c], 24n);
    v[a] = (v[a] + v[b] + y) & M64;
    v[d] = rotr(v[d] ^ v[a], 16n);
    v[c] = (v[c] + v[d]) & M64;
    v[b] = rotr(v[b] ^ v[c], 63n);
  };
  for (let r = 0; r < 12; r++) {
    const s = SIGMA[r % 10];
    g(0, 4, 8, 12, m[s[0]], m[s[1]]);
    g(1, 5, 9, 13, m[s[2]], m[s[3]]);
    g(2, 6, 10, 14, m[s[4]], m[s[5]]);
    g(3, 7, 11, 15, m[s[6]], m[s[7]]);
    g(0, 5, 10, 15, m[s[8]], m[s[9]]);
    g(1, 6, 11, 12, m[s[10]], m[s[11]]);
    g(2, 7, 8, 13, m[s[12]], m[s[13]]);
    g(3, 4, 9, 14, m[s[14]], m[s[15]]);
  }
  const first = h[0] ^ v[0] ^ v[8];
  // First 4 digest bytes, read big-endian as Python's int.from_bytes(..., "big").
  const le = Number(first & 0xffffffffn);
  return BigInt(((le & 0xff) << 24 | (le & 0xff00) << 8 | (le >>> 8) & 0xff00 | le >>> 24) >>> 0);
}

/** A repeatable 0-1 value from integers; the input is Python's `repr(tuple)`. */
export function noise(...k: number[]): number {
  const repr = k.length === 1 ? `(${k[0]},)` : `(${k.join(", ")})`;
  return Number(blake2b4(new TextEncoder().encode(repr))) / 0xffffffff;
}

export type ArtCell = { col: number; row: number; alpha: number; spark: boolean; dur: number; delay: number; sparkDur: number; sparkDelay: number };
export type ArtPick = { idx: number; value: number; label: string; count: number };
export type Art = { values: number[]; cells: ArtCell[]; picks: ArtPick[]; shift: number; cols: number; rows: number };

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export function loginArt(now: Date = new Date()): Art {
  const n = 22;
  const rows = 14;
  const values: number[] = [];
  for (let i = 0; i < n; i++) {
    const wave = 0.45 + 0.18 * Math.sin((i / n) * 4 * Math.PI);
    values.push(Math.min(0.9, Math.max(0.08, wave + (noise(7, i) - 0.5) * 0.5)));
  }

  const cells: ArtCell[] = [];
  for (let col = 0; col < 2 * n; col++) {
    const w = col % n;
    const warmth = 0.25 + 0.75 * noise(w, 8);
    for (let row = 0; row < rows; row++) {
      const fade = 1 - (row / rows) * 0.75;
      cells.push({
        col,
        row,
        alpha: 0.05 + 0.5 * warmth * fade * (0.35 + 0.65 * noise(w, row, 4)),
        spark: noise(w, row, 5) > 0.9 && row < rows * 0.7,
        dur: 3 + noise(w, row, 2) * 4,
        delay: -(noise(w, row, 3) * 6),
        sparkDur: 5 + noise(w, row, 6) * 6,
        sparkDelay: -(noise(w, row, 7) * 9),
      });
    }
  }

  // Busiest weeks, at least 5 apart (circularly), three of them.
  const order = Array.from({ length: n - 2 }, (_, i) => i + 1).sort((a, b) => values[b] - values[a]);
  const chosen: number[] = [];
  for (const i of order) {
    if (chosen.every((j) => Math.min(Math.abs(i - j), n - Math.abs(i - j)) >= 5)) chosen.push(i);
    if (chosen.length === 3) break;
  }
  const today = Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate());
  // One entry per highlighted week of the first copy; the component draws a
  // second at idx + n for the repeated half of the track.
  const picks: ArtPick[] = [...chosen]
    .sort((a, b) => a - b)
    .map((i) => {
      const d = new Date(today - ((n - i) % n) * 7 * DAY_MS);
      return {
        idx: i,
        value: values[i],
        label: `Week of ${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]}`,
        count: Math.round(6 + values[i] * 40),
      };
    });
  return { values, cells, picks, shift: n / (2 * n + 1), cols: 2 * n + 1, rows };
}
