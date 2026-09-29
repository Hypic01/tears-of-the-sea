// The opening: the printed cover sits still with the painting already moving in its frame. Scrolling grows
// that frame until the video fills the whole screen, and slides the card off to the left.
// One video element throughout: only the window around it changes, so it never restarts.
(function () {
  var root = document.documentElement;
  var sec = document.querySelector('.opening');
  var reduce = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (!sec || reduce || !window.requestAnimationFrame) return;      // the still version in the markup stays

  var stage = sec.querySelector('.stage'), plate = sec.querySelector('.plate'), win = sec.querySelector('.win');
  var card = sec.querySelector('.card'), cue = sec.querySelector('.cue');
  var video = sec.querySelector('.win-video'), still = sec.querySelector('.win-still');

  // each page carries its album's sources. With a video, the tall cut is a crop of the wide master (the
  // cover's illustration area). Without one, both cuts are the illustration itself, zoomed to fill.
  var SRC = JSON.parse(document.getElementById('tape-data').textContent);
  var CARD = 656 / 1800;      // card width as a share of the cover
  var probe = document.createElement('video');
  function av1(c) { return !!(probe.canPlayType && probe.canPlayType('video/mp4; codecs="' + c + '"') === 'probably'); }

  var cut = null, g = null, p = 0, target = 0, ticking = false, inView = true;

  function play() {
    if (!video || !inView || document.hidden || !video.paused || !video.currentSrc) return;
    var q = video.play(); if (q && q.catch) q.catch(function () {});
  }
  function pick() {
    var next = stage.clientWidth / stage.clientHeight < 0.8 ? 'tall' : 'wide';
    if (next === cut) return;
    cut = next;
    var s = SRC[cut];
    if (!video) { still.src = s.still; return; }
    still.src = s.poster; video.poster = s.poster;
    video.src = av1(s.codec) ? s.av1 : s.h264;
    video.load(); play();
  }
  function measure() {
    pick();
    var s = SRC[cut], W = stage.clientWidth, H = stage.clientHeight;
    var vw = Math.max(W, H * s.ar), vh = vw / s.ar;                 // the video drawn to cover the screen
    var S = Math.min(H * 0.76, W * (W < H ? 0.92 : 0.6));           // the cover, a square
    var cx = (W - S) / 2, cy = (H - S) / 2 + 12;
    var slotW = S * (1 - CARD), k0 = S / vh, x0 = vw * s.a0;
    var top = (H - vh) * (s.focusY === undefined ? 0.5 : s.focusY);   // which part stays in view when it is taller than the screen
    var kEnd = H / S;                                                // the card grows with the painting as it leaves
    g = {
      H: H, S: S, cx: cx, cy: cy, k0: k0, kEnd: kEnd,
      tx0: cx + S * CARD - (W - vw) / 2 - x0 * k0, ty0: cy - top,
      clipL: x0, clipR: Math.max(vw - x0 - slotW / k0, 0),
      cardEnd: -S * CARD * kEnd - 60                                 // fully off the left edge: a spine cut the title at an odd spot
    };
    win.style.width = vw + 'px'; win.style.height = vh + 'px';
    win.style.left = (W - vw) / 2 + 'px'; win.style.top = top + 'px';
    card.style.height = S + 'px';
    plate.style.width = plate.style.height = S + 'px';
    plate.style.transform = 'translate(' + cx + 'px,' + cy + 'px)';
    render();
  }
  function ease(t) { return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2; }
  function render() {
    var e = ease(p), r = 1 - e;
    var k = g.k0 + (1 - g.k0) * e;
    win.style.transform = 'translate(' + g.tx0 * r + 'px,' + g.ty0 * r + 'px) scale(' + k + ')';
    win.style.clipPath = 'inset(0px ' + g.clipR * r + 'px 0px ' + g.clipL * r + 'px)';
    var kc = 1 + (g.kEnd - 1) * e;
    card.style.transform = 'translate(' + (g.cx + (g.cardEnd - g.cx) * e) + 'px,' + g.cy * r + 'px) scale(' + kc + ')';
    plate.style.opacity = Math.max(1 - e * 2.2, 0);
    cue.style.opacity = Math.max(1 - p * 5, 0);
  }
  function read() {
    var b = sec.getBoundingClientRect(), total = sec.offsetHeight - stage.clientHeight;
    target = Math.min(Math.max(-b.top / total, 0), 1);
    // the name and links turn light while they sit on the painting, and back to ink on the card below
    root.classList.toggle('on-art', target > 0.5 && b.bottom > 70);
    if (!ticking) { ticking = true; requestAnimationFrame(step); }
  }
  function step() {
    p += (target - p) * 0.16;
    if (Math.abs(target - p) < 0.0006) p = target;
    render();
    if (p !== target) requestAnimationFrame(step); else ticking = false;
  }

  root.classList.add('js-open');
  if (video) {
    video.muted = true; video.defaultMuted = true; video.loop = true;
    video.addEventListener('canplay', play);
    document.addEventListener('visibilitychange', play);
  }
  measure(); read(); p = target; render();
  window.addEventListener('scroll', read, { passive: true });
  window.addEventListener('resize', function () { measure(); read(); });
  if ('IntersectionObserver' in window) {
    new IntersectionObserver(function (en) {
      inView = en[0].isIntersecting;
      if (inView) play(); else if (video) video.pause();
    }).observe(sec);
  }
})();
