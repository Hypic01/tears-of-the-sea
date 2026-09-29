// The shelf: every tape as its printed spine, newest first, grouped by year. Opening a spine shows the
// whole cover over its neighbours (nothing moves or changes row) and its Bandcamp link. One tape is open at a time.
(function () {
  var rows = document.getElementById('rows');
  if (!rows || !window.fetch) return;
  var title = document.getElementById('now-title'), meta = document.getElementById('now-meta'), link = document.getElementById('now-link'), openLink = document.getElementById('now-open');
  var here = JSON.parse(document.getElementById('tape-data').textContent).slug;

  function open(btn, a, scroll) {
    [].forEach.call(rows.querySelectorAll('.cas[aria-pressed="true"]'), function (b) { b.setAttribute('aria-pressed', 'false'); });
    btn.setAttribute('aria-pressed', 'true');
    var full = btn.querySelector('.full');
    if (!full.getAttribute('src')) full.src = '/' + a.cover;
    // keep the opened cover inside the screen when its spine sits near an edge
    full.style.setProperty('--nudge', '0px');
    var wide = rows.scrollWidth <= rows.clientWidth + 1;
    if (wide) {
      var h = btn.offsetHeight, left = btn.getBoundingClientRect().left - a.spineX * h, over = left + h - (document.documentElement.clientWidth - 12);
      full.style.setProperty('--nudge', (left < 12 ? 12 - left : over > 0 ? -over : 0) + 'px');
    }
    title.textContent = a.title;
    meta.textContent = a.year + ' · ' + a.tracks + (a.tracks === 1 ? ' track' : ' tracks');
    link.href = a.bandcamp;
    // a tape with its own page opens there; the page you are on needs no link to itself
    openLink.hidden = !(a.page && a.slug !== here);
    openLink.href = '/tape/' + a.slug + '/';
    if (scroll && btn.scrollIntoView) btn.scrollIntoView({ block: 'nearest', inline: 'center', behavior: 'smooth' });
  }

  fetch('/data/albums.json?v=2').then(function (r) { return r.json(); }).then(function (albums) {
    var byYear = {}, years = [], first = null;
    albums = albums.filter(function (a) { return a.shelf; });
    albums.forEach(function (a) { if (!byYear[a.year]) { byYear[a.year] = []; years.push(a.year); } byYear[a.year].push(a); });
    years.forEach(function (y) {
      var group = document.createElement('div');
      group.className = 'year'; group.setAttribute('role', 'group'); group.setAttribute('aria-label', 'Tapes from ' + y);
      var n = document.createElement('span'); n.className = 'year-n'; n.textContent = y; n.setAttribute('aria-hidden', 'true');
      group.appendChild(n);
      byYear[y].forEach(function (a) {
        var b = document.createElement('button');
        b.type = 'button'; b.className = 'cas'; b.setAttribute('aria-pressed', 'false'); b.setAttribute('aria-label', a.title + ', ' + a.year);
        b.style.setProperty('--x', a.spineX);
        var slice = document.createElement('span'); slice.className = 'slice';
        var img = new Image(); img.alt = ''; img.loading = 'lazy'; img.decoding = 'async'; img.src = '/' + a.cover;
        slice.appendChild(img); b.appendChild(slice);
        var full = new Image(); full.alt = ''; full.className = 'full'; full.decoding = 'async';
        b.appendChild(full);
        b.addEventListener('click', function () { open(b, a, true); });
        group.appendChild(b);
        if (a.slug === here) { open(b, a, false); first = b; }
      });
      rows.appendChild(group);
    });
    // on a phone the shelf scrolls sideways: start it at the open tape, without moving the page
    if (first && rows.scrollWidth > rows.clientWidth) rows.scrollLeft = first.offsetLeft - rows.offsetLeft - (rows.clientWidth - first.offsetWidth) / 2;
  }).catch(function () {
    rows.innerHTML = '<p class="meta"><a href="https://mabisyo.bandcamp.com/music">Every tape is on Bandcamp</a></p>';
  });
})();
