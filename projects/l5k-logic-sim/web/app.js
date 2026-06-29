let IR = null, current = null, runTimer = null;

async function jget(p) { return (await fetch(p)).json(); }
async function jpost(p, body) {
  return (await fetch(p, {method: "POST", headers: {"Content-Type": "application/json"},
    body: body ? JSON.stringify(body) : null})).json();
}

function routineKey(progName, routineName) { return progName + "::" + routineName; }

async function boot() {
  IR = await jget("/api/ir");
  const sel = document.getElementById("routine");
  for (const prog of IR.programs)
    for (const r of prog.routines) {
      const o = document.createElement("option");
      o.value = routineKey(prog.name, r.name);
      o.textContent = prog.name + " / " + r.name;
      sel.appendChild(o);
    }
  sel.onchange = () => { current = sel.value; renderLadder(); paint(lastState); };
  current = sel.value;
  document.getElementById("step").onclick = async () => paint(await jpost("/api/step"));
  document.getElementById("reset").onclick = async () => paint(await jpost("/api/reset"));
  document.getElementById("run").onclick = startRun;
  document.getElementById("pause").onclick = stopRun;
  document.getElementById("forceForm").onsubmit = async (e) => {
    e.preventDefault();
    const v = document.getElementById("fVal").value;
    paint(await jpost("/api/force", {scope: document.getElementById("fScope").value,
      operand: document.getElementById("fOp").value, value: coerce(v)}));
  };
  renderLadder();
  paint(await jget("/api/state"));
}

function coerce(v) { if (v === "") return v; if (v === "true") return true; if (v === "false") return false;
  return isNaN(Number(v)) ? v : Number(v); }

function startRun() {
  document.getElementById("run").disabled = true;
  document.getElementById("pause").disabled = false;
  runTimer = setInterval(async () => paint(await jpost("/api/step")), 250);
}
function stopRun() {
  clearInterval(runTimer); runTimer = null;
  document.getElementById("run").disabled = false;
  document.getElementById("pause").disabled = true;
}

function selected() {
  const [p, r] = current.split("::", 2);
  const prog = IR.programs.find(x => x.name === p);
  return {prog, routine: prog.routines.find(x => x.name === r)};
}

function renderLadder() {
  const {prog, routine} = selected();
  if (!routine) return;
  const host = document.getElementById("ladder");
  host.innerHTML = "";
  routine.rungs.forEach(rung => {
    const div = document.createElement("div");
    div.className = "rung";
    if (rung.comment) { const c = document.createElement("div"); c.className = "cmt"; c.textContent = rung.comment; div.appendChild(c); }
    div.appendChild(window.renderRungSVG(rung, `${prog.name}/${routine.name}/${rung.number}`));
    host.appendChild(div);
  });
}

let lastState = null;
function paint(state) {
  if (!state) return;
  lastState = state;
  document.getElementById("time").textContent = "t = " + state.time_ms + " ms";
  document.querySelectorAll(".el.hot, [data-elid].hot").forEach(e => e.classList.remove("hot"));
  for (const [key, hot] of Object.entries(state.trace))
    if (hot) document.querySelectorAll(`[data-elid="${key}"]`).forEach(e => e.classList.add("hot"));
  renderTags(state.tags); renderDiags(state.diagnostics);
}

function renderTags(tags) {
  const {prog} = selected();
  const scope = tags.programs[prog.name] || {};
  const t = document.getElementById("tags"); t.innerHTML = "";
  for (const [name, val] of Object.entries(scope)) {
    if (val && typeof val === "object") continue; // skip structs in the flat table
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${name}</td><td class="${val === true ? "true" : val === false ? "false" : ""}">${val}</td>`;
    t.appendChild(tr);
  }
}
function renderDiags(diags) {
  const ul = document.getElementById("diags"); ul.innerHTML = "";
  diags.slice(0, 12).forEach(d => { const li = document.createElement("li"); li.textContent = d; ul.appendChild(li); });
}

boot();
