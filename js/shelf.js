// The shelf: every tape as its printed spine, newest first, grouped by year. Opening a spine shows the
// whole cover and its Bandcamp link. One tape is open at a time.
(function () {
  var rows = document.getElementById('rows');
  if (!rows || !window.fetch) return;
  var title = document.getElementById('now-title'), meta = document.getElementById('now-meta'), link = document.getElementById('now-link');

  function open(btn, a, scroll) {
    [].forEach.call(rows.querySelectorAll('.cas[aria-pressed="true"]'), function (b) { b.setAttribute('aria-pressed', 'false'); });
    btn.setAttribute('aria-pressed', 'true');
    title.textContent = a.title;
    meta.textContent = a.year + ' · ' + a.tracks + (a.tracks === 1 ? ' track' : ' tracks');
    link.href = a.bandcamp;
    if (scroll && btn.scrollIntoView) btn.scrollIntoView({ block: 'nearest', inline: 'center', behavior: 'smooth' });
  }

  fetch('data/albums.json?v=1').then(function (r) { return r.json(); }).then(function (albums) {
    var byYear = {}, years = [], first = null;
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
        var img = new Image(); img.alt = ''; img.loading = 'lazy'; img.decoding = 'async'; img.src = a.cover;
        b.appendChild(img);
        b.addEventListener('click', function () { open(b, a, true); });
        group.appendChild(b);
        if (a.featured) { open(b, a, false); first = b; }
      });
      rows.appendChild(group);
    });
    // on a phone the shelf scrolls sideways: start it at the open tape, without moving the page
    if (first && rows.scrollWidth > rows.clientWidth) rows.scrollLeft = first.offsetLeft - rows.offsetLeft - (rows.clientWidth - first.offsetWidth) / 2;
  }).catch(function () {
    rows.innerHTML = '<p class="meta"><a href="https://mabisyo.bandcamp.com/music">Every tape is on Bandcamp</a></p>';
  });
})();
