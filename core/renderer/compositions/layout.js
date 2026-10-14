const W = 13.333;
const H = 7.5;
const M = { left: 0.65, right: 0.65, top: 0.35, bottom: 0.42 };

function contentWidth() { return W - M.left - M.right; }

function columns(count, gap = 0.22, x = M.left, width = contentWidth()) {
  const n = Math.max(1, count);
  const w = (width - gap * (n - 1)) / n;
  return Array.from({ length: n }, (_, i) => ({ x: x + i * (w + gap), w }));
}

module.exports = { W, H, M, contentWidth, columns };
