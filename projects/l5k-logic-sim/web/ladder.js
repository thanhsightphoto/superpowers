// Task 5 fills this in with SVG ladder rendering.
const NS = "http://www.w3.org/2000/svg";
const COL_W = 120, ROW_H = 44, PAD = 12;

function el(tag, attrs = {}, text) {
  const n = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
  if (text != null) n.textContent = text;
  return n;
}

const INPUTS = new Set(["XIC", "XIO", "EQ", "NE", "GT", "GE", "LT", "LE", "LIMIT", "ONS", "OSF"]);
const COILS = {OTE: "( )", OTL: "(L)", OTU: "(U)"};

// returns {node, width} so callers can lay elements left-to-right
function drawElement(element, elid, x, y) {
  if (element.kind === "branch") return drawBranch(element, elid, x, y);
  const g = el("g", {"data-elid": elid, class: "el"});
  const cx = x + COL_W / 2;
  g.appendChild(el("line", {x1: x, y1: y, x2: x + COL_W, y2: y, class: "wire"}));
  const m = element.mnemonic;
  if (m === "XIC" || m === "XIO" || INPUTS.has(m)) {
    g.appendChild(el("line", {x1: cx - 8, y1: y - 12, x2: cx - 8, y2: y + 12, class: "bar"}));
    g.appendChild(el("line", {x1: cx + 8, y1: y - 12, x2: cx + 8, y2: y + 12, class: "bar"}));
    if (m === "XIO") g.appendChild(el("line", {x1: cx - 10, y1: y + 12, x2: cx + 10, y2: y - 12, class: "slash"}));
  } else if (COILS[m]) {
    g.appendChild(el("text", {x: cx, y: y + 4, class: "coil", "text-anchor": "middle"}, COILS[m]));
  } else {
    g.appendChild(el("rect", {x: x + 14, y: y - 14, width: COL_W - 28, height: 28, class: "box"}));
  }
  const label = m + (element.operands.length ? "(" + element.operands.join(",") + ")" : "");
  g.appendChild(el("text", {x: cx, y: y - 18, class: "lbl", "text-anchor": "middle"}, label));
  return {node: g, width: COL_W};
}

function drawBranch(branch, elid, x, y) {
  const g = el("g", {});
  let maxW = 0;
  const rowYs = [];
  branch.legs.forEach((leg, j) => {
    const ly = y + j * ROW_H;
    rowYs.push(ly);
    let lx = x;
    leg.forEach((child, k) => {
      const {node, width} = drawElement(child, `${elid}.${j}.${k}`, lx, ly);
      g.appendChild(node);
      lx += width;
    });
    maxW = Math.max(maxW, lx - x);
  });
  // vertical connectors at both ends of the branch
  const y0 = rowYs[0], y1 = rowYs[rowYs.length - 1];
  g.appendChild(el("line", {x1: x, y1: y0, x2: x, y2: y1, class: "wire"}));
  g.appendChild(el("line", {x1: x + maxW, y1: y0, x2: x + maxW, y2: y1, class: "wire"}));
  return {node: g, width: maxW};
}

function renderRungSVG(rung, prefix) {
  const svg = el("svg", {class: "rung-svg"});
  const y = PAD + 20;
  let x = PAD;
  let maxRows = 1;
  // pre-measure rows for branch height
  rung.elements.forEach((element, i) => {
    const {node, width} = drawElement(element, `${prefix}.${i}`, x, y);
    svg.appendChild(node);
    x += width;
    if (element.kind === "branch") maxRows = Math.max(maxRows, element.legs.length);
  });
  // power rails
  svg.appendChild(el("line", {x1: PAD - 6, y1: y - ROW_H, x2: PAD - 6, y2: y + maxRows * ROW_H, class: "rail"}));
  const height = y + maxRows * ROW_H + PAD;
  svg.setAttribute("width", x + PAD);
  svg.setAttribute("height", height);
  svg.setAttribute("viewBox", `0 0 ${x + PAD} ${height}`);
  return svg;
}

window.renderRungSVG = renderRungSVG;
