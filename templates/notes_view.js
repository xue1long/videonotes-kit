const LEFT_LINKS = document.querySelectorAll('aside.left a[data-target]');
const ARTICLES = document.querySelectorAll('article.pane');
const RIGHT_CONTENT = document.querySelector('aside.right .content');
const ALL_RIGHT_PANES = {};
const PLAYER_KEY = 'vn_left', PLAYERR_KEY = 'vn_right';
const main = document.querySelector('main.three');

document.querySelectorAll('article.pane').forEach(a => {
  ALL_RIGHT_PANES[a.id] = a.querySelector('.right-pane-content')?.innerHTML || '';
});

// ---- 笔记切换 ----
LEFT_LINKS.forEach(a => {
  a.addEventListener('click', e => {
    e.preventDefault();
    const t = a.dataset.target;
    LEFT_LINKS.forEach(x => x.classList.toggle('active', x === a));
    ARTICLES.forEach(art => { art.style.display = (art.id === 'file_' + t) ? '' : 'none'; });
    RIGHT_CONTENT.innerHTML = ALL_RIGHT_PANES['file_' + t] || '<div class="empty">本集没有时间轴链接</div>';
    bindRightPane();
    document.querySelector('section.middle').scrollTop = 0;
  });
});

// ---- 右栏：时间轴点击 → 播放器 seek + 播放（不跳页）----
function bindRightPane() {
  const v = RIGHT_CONTENT.querySelector('video.player');
  if (!v) return;
  RIGHT_CONTENT.querySelectorAll('button.step').forEach(btn => {
    btn.addEventListener('click', () => {
      const t = parseFloat(btn.dataset.t);
      if (v.readyState >= 1) {          // 元数据已加载
        v.currentTime = t;
        v.play();
      } else {                          // 首次点击，等 loadedmetadata 再 seek
        v.addEventListener('loadedmetadata', () => { v.currentTime = t; v.play(); }, { once: true });
      }
      RIGHT_CONTENT.querySelectorAll('button.step').forEach(x => x.classList.remove('playing'));
      btn.classList.add('playing');
    });
  });
}

// ---- 分割条拖动（三栏宽度可调 + localStorage 持久化）----
function setW(side, px) {
  if (side === 'l') main.style.setProperty('--w-left', px + 'px');
  else main.style.setProperty('--w-right', px + 'px');
}
function loadW() {
  const l = localStorage.getItem(PLAYER_KEY), r = localStorage.getItem(PLAYERR_KEY);
  if (l) setW('l', l);
  if (r) setW('r', r);
}
document.querySelectorAll('.splitter').forEach(sp => {
  sp.addEventListener('mousedown', e => {
    e.preventDefault();
    sp.classList.add('dragging');
    const side = sp.dataset.side;
    const mainR = main.getBoundingClientRect();
    const move = ev => {
      let px;
      if (side === 'l') { px = ev.clientX - mainR.left; px = Math.max(150, Math.min(px, 460)); }
      else              { px = mainR.right - ev.clientX; px = Math.max(200, Math.min(px, 560)); }
      setW(side, px);
    };
    const up = () => {
      sp.classList.remove('dragging');
      document.removeEventListener('mousemove', move);
      document.removeEventListener('mouseup', up);
      const cur = side === 'l'
        ? getComputedStyle(main).getPropertyValue('--w-left')
        : getComputedStyle(main).getPropertyValue('--w-right');
      localStorage.setItem(side === 'l' ? PLAYER_KEY : PLAYERR_KEY, parseInt(cur) || '');
    };
    document.addEventListener('mousemove', move);
    document.addEventListener('mouseup', up);
  });
  // 双击重置默认
  sp.addEventListener('dblclick', () => {
    const side = sp.dataset.side;
    if (side === 'l') { setW('l', 240); localStorage.removeItem(PLAYER_KEY); }
    else              { setW('r', 280); localStorage.removeItem(PLAYERR_KEY); }
  });
});
loadW();
bindRightPane();
