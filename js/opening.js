// The opening: the printed cover sits still with the painting already moving in its frame. Scrolling grows
// that frame until the video fills the screen, and slides the card left until only its spine shows.
// One video element throughout: only the window around it changes, so it never restarts.
(function () {
  var root = document.documentElement;
  var sec = document.querySelector('.opening');
  var reduce = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (!sec || reduce || !window.requestAnimationFrame) return;      // the still version in the markup stays

  var stage = sec.querySelector('.stage'), plate = sec.querySelector('.plate'), win = sec.querySelector('.win');
  var card = sec.querySelector('.card'), cue = sec.querySelector('.cue');
  var video = sec.querySelector('.win-video'), still = sec.querySelector('.win-still');

  // the tall cut is a crop of the wide master: the cover's painting area (x 810 to 1730 of 2560)
  var SRC = {
    wide: { av1: 'assets/hero-wide.av1.mp4?v=3', h264: 'assets/hero-wide.h264.mp4?v=3', codec: 'av01.0.12M.08', poster: 'assets/poster-wide.jpg?v=3', ar: 2560 / 1440, a0: 810 / 2560 },
    tall: { av1: 'assets/hero-tall.av1.mp4?v=3', h264: 'assets/hero-tall.h264.mp4?v=3', codec: 'av01.0.08M.08', poster: 'assets/poster-tall.jpg?v=3', ar: 920 / 1440, a0: 0 }
  };
  var CARD = 656 / 1800;      // card width as a share of the cover
  var SPINE = 186 / 1800;     // the part of the card that carries the title, as a share of its height
  var probe = document.createElement('video');
  function av1(c) { return !!(probe.canPlayType && probe.canPlayType('video/mp4; codecs="' + c + '"') === 'probably'); }

  var cut = null, g = null, p = 0, target = 0, ticking = false, inView = true;

  function play() {
    if (!inView || document.hidden || !video.paused || !video.currentSrc) return;
    var q = video.play(); if (q && q.catch) q.catch(function () {});
  }
  function pick() {
    var next = stage.clientWidth / stage.clientHeight < 0.8 ? 'tall' : 'wide';
    if (next === cut) return;
    cut = next;
    var s = SRC[cut];
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
    // on a phone the full-height spine would take a fifth of the screen, so the card ends shorter there
    var kEnd = (W < H ? 0.62 : 1) * H / S, spine = SPINE * S * kEnd;
    g = {
      H: H, S: S, cx: cx, cy: cy, k0: k0, kEnd: kEnd,
      txEnd: W < H ? Math.min(spine / 2, (vw - W) / 2) : 0,      // keep her face centred in what the spine leaves free
      tx0: cx + S * CARD - (W - vw) / 2 - x0 * k0, ty0: cy - (H - vh) / 2,
      clipL: x0, clipR: Math.max(vw - x0 - slotW / k0, 0),
      cardEnd: spine - S * CARD * kEnd
    };
    win.style.width = vw + 'px'; win.style.height = vh + 'px';
    win.style.left = (W - vw) / 2 + 'px'; win.style.top = (H - vh) / 2 + 'px';
    card.style.height = S + 'px';
    plate.style.width = plate.style.height = S + 'px';
    plate.style.transform = 'translate(' + cx + 'px,' + cy + 'px)';
    root.style.setProperty('--spine', Math.round(spine) + 'px');
    render();
  }
  function ease(t) { return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2; }
  function render() {
    var e = ease(p), r = 1 - e;
    var k = g.k0 + (1 - g.k0) * e;
    win.style.transform = 'translate(' + (g.tx0 * r + g.txEnd * e) + 'px,' + g.ty0 * r + 'px) scale(' + k + ')';
    win.style.clipPath = 'inset(0px ' + g.clipR * r + 'px 0px ' + g.clipL * r + 'px)';
    var kc = 1 + (g.kEnd - 1) * e;
    card.style.transform = 'translate(' + (g.cx + (g.cardEnd - g.cx) * e) + 'px,' + g.cy * r + 'px) scale(' + kc + ')';
    card.style.boxShadow = '12px 0 40px rgba(15,20,32,' + 0.5 * e + ')';
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
  video.muted = true; video.defaultMuted = true; video.loop = true;
  video.addEventListener('canplay', play);
  document.addEventListener('visibilitychange', play);
  measure(); read(); p = target; render();
  window.addEventListener('scroll', read, { passive: true });
  window.addEventListener('resize', function () { measure(); read(); });
  if ('IntersectionObserver' in window) {
    new IntersectionObserver(function (en) {
      inView = en[0].isIntersecting;
      if (inView) play(); else video.pause();
    }).observe(sec);
  }
})();
