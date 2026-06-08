/* GB.audio — Web Audio kit for the games. Pure oscillator synthesis (no audio files),
   so it works offline from a static deploy. The AudioContext is created lazily on the
   first user gesture (browser autoplay policy). */
(function () {
  "use strict";
  var GB = (window.GB = window.GB || {});

  var _audio = null;
  function ctx() {
    if (_audio == null) { try { _audio = new (window.AudioContext || window.webkitAudioContext)(); } catch (e) { _audio = false; } }
    if (_audio && _audio.state === "suspended") _audio.resume();
    return _audio || null;
  }

  var NOTE_FREQ = {
    C: 261.6, "C#": 277.2, D: 293.7, "D#": 311.1, E: 329.6, F: 349.2, "F#": 370.0,
    G: 392.0, "G#": 415.3, A: 440.0, "A#": 466.2, B: 493.9,
    C2: 523.3, D2: 587.3, E2: 659.3, F2: 698.5, G2: 784.0
  };
  function freqOf(note) {
    if (typeof note === "number") return note;
    var n = String(note).trim();
    return NOTE_FREQ[n] || NOTE_FREQ[n.toUpperCase()] || 440;
  }
  function tone(freq, dur, when, type) {
    var c = ctx(); if (!c) return;
    var t0 = c.currentTime + (when || 0);
    var osc = c.createOscillator(), gain = c.createGain();
    osc.type = type || "sine"; osc.frequency.value = freq;
    gain.gain.setValueAtTime(0.0001, t0);
    gain.gain.exponentialRampToValueAtTime(0.25, t0 + 0.02);
    gain.gain.exponentialRampToValueAtTime(0.0001, t0 + (dur || 0.4));
    osc.connect(gain); gain.connect(c.destination);
    osc.start(t0); osc.stop(t0 + (dur || 0.4) + 0.05);
  }
  function chime(ok) {
    if (ok) { tone(523.3, 0.16, 0); tone(659.3, 0.16, 0.12); tone(784.0, 0.30, 0.24); }
    else { tone(311.1, 0.18, 0); tone(247.0, 0.22, 0.12); }
  }

  // Named one-shot effects built from tones — used by drag/reveal/find games.
  function sfx(name) {
    switch (name) {
      case "pickup": tone(523.3, 0.08, 0, "triangle"); break;
      case "drop": tone(392.0, 0.10, 0, "triangle"); break;
      case "reveal": tone(659.3, 0.12, 0, "sine"); tone(880.0, 0.14, 0.08, "sine"); break;
      case "tick": tone(880.0, 0.05, 0, "square"); break;
      case "win": chime(true); break;
      case "nope": chime(false); break;
      case "pop": tone(740.0, 0.07, 0, "triangle"); break;
      default: tone(523.3, 0.10, 0); break;
    }
  }

  // Play a sequence of notes at a tempo; onNote(i) fires as each plays (to light a pad).
  function playSequence(notes, opts) {
    opts = opts || {};
    var tempo = opts.tempo || 0.5; // seconds per note
    var dur = opts.dur || tempo * 0.85;
    var t = 0;
    (notes || []).forEach(function (n, i) {
      tone(freqOf(n), dur, t, opts.type);
      if (opts.onNote) setTimeout(function () { opts.onNote(i, n); }, t * 1000);
      t += tempo;
    });
    if (opts.onDone) setTimeout(opts.onDone, t * 1000 + 120);
    return t; // total seconds
  }

  GB.audio = {
    ctx: ctx, tone: tone, chime: chime, freqOf: freqOf, sfx: sfx,
    playSequence: playSequence, NOTE_FREQ: NOTE_FREQ
  };
})();
