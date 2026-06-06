/* Garbanzo Books — interactive reader runtime.
   Reads the story JSON embedded in #story-data and renders one page at a time with
   full-page image, embedded text, and playable interactions. Always winnable; no dead ends. */
(function () {
  "use strict";
  const dataEl = document.getElementById("story-data");
  if (!dataEl) return;
  const story = JSON.parse(dataEl.textContent);
  const pages = story.pages || [];
  const byNumber = {};
  pages.forEach((p, i) => { byNumber[p.number] = i; });

  const stage = document.getElementById("stage");
  const interactionBox = document.getElementById("interaction");
  const pageNoEl = document.getElementById("pageno");
  const prevBtn = document.getElementById("prev");
  const nextBtn = document.getElementById("next");
  let idx = 0;

  function el(tag, cls, html) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (html != null) e.innerHTML = html;
    return e;
  }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])); }

  function render() {
    const page = pages[idx];
    if (!page) return;
    stage.innerHTML = "";

    // Image
    const figure = el("div", "page-stage");
    const img = document.createElement("img");
    img.src = page.image && page.image.file ? page.image.file : "";
    img.alt = (page.image && page.image.alt) || "";
    figure.appendChild(img);

    // Embedded text
    if (page.text) {
      const layout = page.layout || {};
      const pos = "pos-" + (layout.text_position || "lower-third");
      const align = layout.text_align ? "align-" + layout.text_align : "";
      const overlay = el("div", "page-text " + pos + " " + align);
      const inner = layout.scrim === false ? el("div", "", esc(page.text)) : el("div", "scrim", esc(page.text));
      overlay.appendChild(inner);
      figure.appendChild(overlay);
    }
    stage.appendChild(figure);

    // Glossary (vocabulary words)
    if (page.vocabulary && page.vocabulary.length) {
      const g = el("div", "glossary");
      g.appendChild(el("span", "", "New words: "));
      page.vocabulary.forEach(w => g.appendChild(el("span", "chip", esc(w))));
      stage.appendChild(g);
    }
    // Co-reader note
    if (page.reading_notes) {
      stage.appendChild(el("div", "reading-note", "Grown-up tip: " + esc(page.reading_notes)));
    }

    // Interaction
    interactionBox.innerHTML = "";
    if (page.interaction) renderInteraction(page.interaction);

    pageNoEl.textContent = (idx + 1) + " / " + pages.length;
    prevBtn.disabled = idx === 0;
    nextBtn.disabled = idx === pages.length - 1;
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function go(n) { idx = Math.max(0, Math.min(pages.length - 1, n)); render(); }
  function gotoNumber(num) { if (byNumber[num] != null) go(byNumber[num]); }

  // ---- Interactions ----
  function renderInteraction(it) {
    const box = el("div", "interaction");
    if (it.skill) box.appendChild(el("span", "skill-tag", esc(it.skill)));
    box.appendChild(el("h4", "", "🎈 " + esc(it.prompt || "Let's play!")));
    const fb = el("div", "feedback");
    const data = it.data || {};
    const good = () => { fb.className = "feedback good"; fb.textContent = (it.feedback && it.feedback.correct) || "Great job! 🎉"; };
    const tryAgain = () => { fb.className = "feedback try"; fb.textContent = (it.feedback && it.feedback.try_again) || "So close — try again!"; };

    switch (it.type) {
      case "seek-and-find": {
        const wrap = el("div");
        (data.items || []).forEach(item => {
          const c = el("span", "find-item", "🔍 " + esc(item));
          c.onclick = () => { c.classList.toggle("found"); if (wrap.querySelectorAll(".found").length === (data.items || []).length) good(); };
          wrap.appendChild(c);
        });
        box.appendChild(wrap); break;
      }
      case "sound-hunt": {
        const wrap = el("div");
        const targets = new Set((data.words || []).map(w => w.toLowerCase()));
        (data.words || []).concat(data.decoys || []).sort().forEach(w => {
          const c = el("span", "hunt-word", esc(w));
          c.onclick = () => {
            if (targets.has(w.toLowerCase())) { c.classList.add("found"); if (wrap.querySelectorAll(".found").length === targets.size) good(); }
            else { c.classList.add("wrong"); tryAgain(); }
          };
          wrap.appendChild(c);
        });
        box.appendChild(el("p", "", "Find the words with the /" + esc(data.sound || "") + "/ sound:"));
        box.appendChild(wrap); break;
      }
      case "rhyme-complete":
      case "comprehension-question":
      case "riddle": {
        const answer = it.type === "comprehension-question"
          ? (data.options || [])[data.answer_index]
          : data.answer;
        let opts = data.options || (data.distractors ? [data.answer].concat(data.distractors) : [data.answer]);
        opts = opts.slice().sort();
        const wrap = el("div", "options");
        if (it.type === "rhyme-complete" && data.sentence) box.appendChild(el("p", "", esc(data.sentence.replace("___", "______"))));
        if (it.type === "riddle" && data.hint) box.appendChild(el("p", "", "Hint: " + esc(data.hint)));
        opts.forEach(o => {
          const b = el("button", "opt", esc(o));
          b.onclick = () => { if (String(o) === String(answer)) { b.classList.add("correct"); good(); } else { b.classList.add("wrong"); tryAgain(); } };
          wrap.appendChild(b);
        });
        box.appendChild(wrap); break;
      }
      case "counting": {
        const input = el("input", "num-input"); input.type = "number";
        const b = el("button", "btn"); b.textContent = "Check";
        b.onclick = () => { Number(input.value) === Number(data.answer) ? good() : tryAgain(); };
        box.appendChild(el("p", "", "How many " + esc(data.what || "things") + "?"));
        box.appendChild(input); box.appendChild(document.createTextNode(" ")); box.appendChild(b); break;
      }
      case "word-match": {
        box.appendChild(el("p", "", "Match each word to its picture:"));
        const wrap = el("div", "options");
        (data.pairs || []).forEach(pr => wrap.appendChild(el("span", "chip", esc(pr[0]) + " → " + esc(pr[1]))));
        const b = el("button", "btn"); b.textContent = "I matched them!"; b.onclick = good;
        box.appendChild(wrap); box.appendChild(b); break;
      }
      case "choice": {
        const wrap = el("div", "options");
        (data.options || []).forEach(o => {
          const b = el("button", "opt", esc(o.label));
          b.onclick = () => gotoNumber(o.goto);
          wrap.appendChild(b);
        });
        box.appendChild(wrap); break;
      }
      case "trace-letter": {
        box.appendChild(el("div", "reveal-box", "Trace the letter <strong style='font-size:2em'>" + esc(data.letter || "") + "</strong> — as in <em>" + esc(data.word || "") + "</em>."));
        const b = el("button", "btn"); b.textContent = "I traced it!"; b.onclick = good; box.appendChild(b); break;
      }
      case "spot-the-difference": {
        box.appendChild(el("p", "", "Can you spot all " + esc(data.count || "the") + " differences?"));
        const b = el("button", "btn"); b.textContent = "Found them all!"; b.onclick = good; box.appendChild(b); break;
      }
      case "drag-order":
      case "memory": {
        box.appendChild(el("p", "", "Put these in order:"));
        const wrap = el("div", "options");
        (data.sequence || []).slice().sort().forEach(s => wrap.appendChild(el("span", "chip", esc(s))));
        const b = el("button", "btn"); b.textContent = "Done!"; b.onclick = good; box.appendChild(wrap); box.appendChild(b); break;
      }
      default: {
        const b = el("button", "btn"); b.textContent = "I did it!"; b.onclick = good; box.appendChild(b);
      }
    }
    box.appendChild(fb);
    interactionBox.appendChild(box);
  }

  prevBtn.onclick = () => go(idx - 1);
  nextBtn.onclick = () => go(idx + 1);
  document.addEventListener("keydown", e => {
    if (e.key === "ArrowRight") go(idx + 1);
    if (e.key === "ArrowLeft") go(idx - 1);
  });

  // Dyslexia-friendly + text-size toggles (shared with site).
  const dys = document.getElementById("dyslexia-toggle");
  if (dys) dys.onclick = () => document.body.classList.toggle("dyslexia");

  render();
})();
