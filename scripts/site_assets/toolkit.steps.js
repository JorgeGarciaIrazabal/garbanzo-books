/* GB.steps — multi-beat sequencer. An interaction with `steps:[…]` plays each sub-game in
   turn; the parent win() fires only after the last beat. Each beat is itself a registered
   game and is itself always winnable, so a chain never dead-ends. */
(function () {
  "use strict";
  var GB = (window.GB = window.GB || {});
  var el = function (t, c, h) { return GB.el(t, c, h); };

  function run(parentCtx, steps) {
    steps = (steps || []).filter(Boolean);
    if (!steps.length) { parentCtx.win(); return; }
    var body = parentCtx.body;

    var dots = el("div", "steps-progress");
    steps.forEach(function () { dots.appendChild(el("span", "step-dot")); });
    body.appendChild(dots);
    var stage = el("div", "step-beat");
    body.appendChild(stage);

    var i = 0;
    function paintDots() {
      var ds = dots.querySelectorAll(".step-dot");
      for (var k = 0; k < ds.length; k++) { ds[k].classList.toggle("done", k < i); ds[k].classList.toggle("now", k === i); }
    }
    function makeHint(container) {
      return function (text) {
        if (!text) return;
        if (Array.isArray(text) && GB.shared && GB.shared.hintLadder) return GB.shared.hintLadder(container, text);
        if (Array.isArray(text)) text = text[0];
        var h = el("button", "btn ghost hint-btn", "💡 Hint");
        var hp = el("div", "hint"); hp.hidden = true; hp.textContent = text;
        h.onclick = function () { hp.hidden = !hp.hidden; };
        container.appendChild(h); container.appendChild(hp);
      };
    }
    function renderStep() {
      paintDots();
      stage.classList.remove("step-in"); void stage.offsetWidth; stage.classList.add("step-in");
      stage.innerHTML = "";
      var step = steps[i];
      if (step.prompt) stage.appendChild(el("p", "game-line step-prompt", GB.esc(step.prompt)));
      var sub = el("div", "step-body");
      stage.appendChild(sub);
      var stepWin = function () {
        i++;
        if (i >= steps.length) { parentCtx.win(); }
        else { if (GB.audio) GB.audio.sfx("reveal"); renderStep(); }
      };
      var subCtx = {
        box: parentCtx.box, body: sub, data: step.data || {}, it: step, page: parentCtx.page,
        win: stepWin, nope: parentCtx.nope, hintBtn: makeHint(sub), gotoNumber: parentCtx.gotoNumber,
        scene: GB.scene, dnd: GB.dnd, juice: GB.juice, audio: GB.audio, steps: GB.steps, reward: GB.reward, shared: GB.shared
      };
      var G = GB.games[step.type] || GB.games._default;
      G(subCtx);
    }
    renderStep();
  }

  GB.steps = { run: run };
})();
