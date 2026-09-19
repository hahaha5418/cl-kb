/* ============================================================
   build-content.mjs · 每次构建前自动运行
   1. 扫描 docs/ 下所有 .md，自动生成各板块的卡片流索引页
   2. 统计学习路径的完成情况，自动更新进度条
   用法：node tools/build-content.mjs
   ============================================================ */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DOCS = path.resolve(__dirname, '..', 'docs');

/* ---------- 读取 frontmatter ---------- */
function readFM(file) {
  // 统一换行：Python 脚本在 Windows 上写出的文件是 CRLF，不规范化会导致 frontmatter 解析失败
  const raw = fs.readFileSync(file, 'utf8').replace(/\r\n/g, '\n');
  const m = raw.match(/^---\n([\s\S]*?)\n---/);
  const out = {};
  if (!m) return out;
  m[1].split('\n').forEach((line) => {
    const i = line.indexOf(':');
    if (i < 0) return;
    const k = line.slice(0, i).trim();
    let v = line.slice(i + 1).trim().replace(/^"|"$/g, '');
    if (v === 'true') v = true;
    else if (v === 'false') v = false;
    out[k] = v;
  });
  return out;
}

function listMd(dir) {
  if (!fs.existsSync(dir)) return [];
  return fs.readdirSync(dir)
    .filter((f) => f.endsWith('.md') && f !== 'index.md')
    .sort();
}

function write(file, content) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, content, 'utf8');
}

function fm(obj) {
  return '---\n' + Object.entries(obj)
    .map(([k, v]) => `${k}: ${typeof v === 'string' ? '"' + v + '"' : v}`)
    .join('\n') + '\n---\n\n';
}

function bar(done, total) {
  const pct = total ? Math.round((done / total) * 100) : 0;
  const filled = Math.round(pct / 5);
  return '`' + '█'.repeat(filled) + '░'.repeat(20 - filled) + '` ' + pct + '%';
}

/* ---------- 各板块封面（生成索引页顶部 hero） ----------
   只给 3 个核心板块配真实图片（省资源、加载快），
   其余板块用高级 CSS 渐变 + 图标代替，样式见 style.css。 */
const SECTION_COVERS = {
  glossary: { img: '/covers/glossary.png' },
  dev:      { img: '/covers/dev.png' },
  scenes:   { img: '/covers/scenes.png' },
  tools:    { grad: 'g-tools', icon: '🧰', text: '精选 AI 工具 · 附评分与上手建议' },
  path:     { grad: 'g-path',  icon: '🗺️', text: '4 阶段 26 步 · 从零基础到能上手' },
  news:     { grad: 'g-news',  icon: '🔥', text: '每天早 7 点自动抓取 · 含初学者建议' },
  notes:    { grad: 'g-notes', icon: '✍️', text: '记录你的理解、踩坑与灵感' },
  video:    { grad: 'g-video', icon: '🎬', text: '跟着视频动手学 · 直接嵌入 B 站' }
};
function hero(folder) {
  const c = SECTION_COVERS[folder];
  if (!c) return '';
  if (c.img) return `<img class="cl-hero" src="${c.img}" alt="" loading="lazy">\n\n`;
  return `<div class="cl-hero-grad ${c.grad}"><span class="cl-hero-icon">${c.icon}</span><span class="cl-hero-text">${c.text}</span></div>\n\n`;
}

/* ---------- 卡片项 ---------- */
function cardItem({ title, link, emoji = '📄', desc = '', tag = '', cover = '', extra = '' }) {
  const coverHtml = cover ? `<img class="cl-cover" src="${cover}" alt="" loading="lazy">` : '';
  const tagHtml = tag ? `<span class="cl-tag">${tag}</span>` : '';
  // 卡片是写在 markdown 里的原生 <a>，VitePress 不会把 .md 链接自动改写为 .html，
  // 必须手动把 .md 换成 .html，否则线上点卡片会 404。
  const target = (link || '').replace(/\.md$/, '.html');
  return `<a class="cl-card" href="${target}">
    ${coverHtml}
    <span class="cl-emoji">${emoji}</span>
    <span class="cl-title">${title}</span>
    <span class="cl-desc">${desc}</span>
    ${extra}${tagHtml}
  </a>`;
}

/* 通用：按 category 分组输出卡片流 */
function buildGrouped(folder, title, defaultEmoji, intro) {
  const dir = path.join(DOCS, folder);
  const files = listMd(dir);
  const groups = {};
  files.forEach((f) => {
    const d = readFM(path.join(dir, f));
    const cat = d.category || '未分类';
    (groups[cat] = groups[cat] || []).push({
      title: d.title || f.replace(/\.md$/, ''),
      link: './' + f,
      emoji: d.emoji || defaultEmoji,
      desc: d.desc || '',
      tag: d.tag || '',
      cover: d.cover || ''
    });
  });

  let body = fm({ title }) + hero(folder) + `# ${title}\n\n${intro}\n共 **${files.length}** 篇。\n`;
  if (files.length === 0) {
    body += '\n_还没有内容。在 `docs/' + folder + '/` 下新建 `.md` 文件就会出现在这里。_\n';
  } else {
    Object.keys(groups).forEach((cat) => {
      body += `\n## ${cat}\n\n<div class="cl-cards">\n` +
        groups[cat].map((g) => cardItem(g)).join('\n') +
        `\n</div>\n`;
    });
  }
  write(path.join(dir, 'index.md'), body);
  return files.length;
}

/* ---------- 1. 术语词典 ---------- */
(function buildGlossary() {
  const dir = path.join(DOCS, 'glossary');
  const files = listMd(dir);
  const groups = {};
  files.forEach((f) => {
    const d = readFM(path.join(dir, f));
    const cat = d.category || '未分类';
    (groups[cat] = groups[cat] || []).push({
      name: d.title || f, link: './' + f, en: d.en || '',
      emoji: d.emoji || '📘', desc: d.desc || ''
    });
  });

  let body = fm({ title: '术语词典' }) + hero('glossary') +
    `# 术语词典\n\n共 **${files.length}** 条术语。点卡片进入详情页，可以在页面底部补充你自己的理解。\n`;

  Object.keys(groups).forEach((cat) => {
    body += `\n## ${cat}\n\n<div class="cl-cards">\n` +
      groups[cat].map((g) => cardItem({ title: g.name, link: g.link, emoji: g.emoji, desc: g.desc, tag: g.en })).join('\n') +
      `\n</div>\n`;
  });

  write(path.join(dir, 'index.md'), body);
  console.log('术语索引：' + files.length + ' 条');
})();

/* ---------- 2. 工具库 ---------- */
(function buildTools() {
  const dir = path.join(DOCS, 'tools');
  const files = listMd(dir);
  const groups = {};
  files.forEach((f) => {
    const d = readFM(path.join(dir, f));
    const cat = d.category || '未分类';
    (groups[cat] = groups[cat] || []).push({
      name: d.title || f, link: './' + f,
      score: Number(d.score) || 0,
      emoji: d.emoji || '🧰', desc: d.desc || '', cover: d.cover || ''
    });
  });

  let body = fm({ title: '工具库' }) + hero('tools') +
    `# 工具库\n\n共 **${files.length}** 个工具。评分是我按通用体验给的，你可以直接在对应文件里改。\n`;

  Object.keys(groups).forEach((cat) => {
    body += `\n## ${cat}\n\n<div class="cl-cards">\n` +
      groups[cat].map((t) => cardItem({
        title: t.name, link: t.link, emoji: t.emoji,
        desc: t.desc,
        cover: t.cover || '',
        tag: '★'.repeat(t.score) + '☆'.repeat(5 - t.score)
      })).join('\n') + `\n</div>\n`;
  });

  write(path.join(dir, 'index.md'), body);
  console.log('工具索引：' + files.length + ' 个');
})();

/* ---------- 3. 学习路径（保留进度逻辑） ---------- */
(function buildPath() {
  const base = path.join(DOCS, 'path');
  if (!fs.existsSync(base)) return;
  const stages = fs.readdirSync(base)
    .filter((f) => fs.statSync(path.join(base, f)).isDirectory())
    .sort();

  let total = 0, done = 0;
  let body = fm({ title: '学习路径' }) + hero('path') + `# 学习路径\n\n`;
  const stageRows = [];

  stages.forEach((sd) => {
    const dir = path.join(base, sd);
    const files = listMd(dir);
    const items = files.map((f) => {
      const d = readFM(path.join(dir, f));
      const isDone = d.done === true;
      total++;
      if (isDone) done++;
      return { title: d.title || f, link: './' + sd + '/' + f, done: isDone, order: Number(d.order) || 0 };
    });
    items.sort((a, b) => a.order - b.order);

    const meta = fs.existsSync(path.join(dir, 'index.md'))
      ? readFM(path.join(dir, 'index.md')) : {};
    const stDone = items.filter((i) => i.done).length;
    const stageTitle = meta.title || sd;

    write(path.join(dir, 'index.md'),
      fm({ title: stageTitle, stage: meta.stage || '' }) +
      `# ${stageTitle}\n\n` +
      `**本阶段进度**：${stDone} / ${items.length}　${bar(stDone, items.length)}\n\n` +
      `## 任务清单\n\n` +
      (items.length
        ? items.map((i) => `- ${i.done ? '[x]' : '[ ]'} [${i.title}](./${path.basename(i.link)})`).join('\n')
        : '_还没有任务_') +
      '\n'
    );

    stageRows.push(`- [${stageTitle}](./${sd}/)　${stDone}/${items.length}`);
  });

  body += `**总进度**：${done} / ${total}　${bar(done, total)}\n\n` +
    `## 四个阶段\n\n${stageRows.join('\n')}\n\n` +
    `## 怎么标记完成\n\n` +
    `打开某个任务文件，把开头的 \`done: false\` 改成 \`done: true\`，保存提交后，这里的进度条会自动更新。\n`;

  write(path.join(base, 'index.md'), body);

  // 生成 path-manifest.json：给首页进度条用（学习路径总步数）
  const manifestSteps = [];
  stages.forEach((sd) => {
    const dir = path.join(base, sd);
    listMd(dir).forEach((f) => manifestSteps.push('path/' + sd + '/' + f));
  });
  const pub2 = path.join(DOCS, 'public');
  if (!fs.existsSync(pub2)) fs.mkdirSync(pub2, { recursive: true });
  fs.writeFileSync(path.join(pub2, 'path-manifest.json'), JSON.stringify({ steps: manifestSteps }), 'utf8');

  console.log('学习路径：' + total + ' 个任务，已完成 ' + done + ' 个');
})();

/* ---------- 4. 每日热点详情库 ---------- */
(function buildNews() {
  const dir = path.join(DOCS, 'news');
  const files = listMd(dir);

  // 源文件（md）作为底账，保证一条不丢
  const mdItems = files.map((f) => {
    const d = readFM(path.join(dir, f));
    return {
      id: f.replace(/\.md$/, ''),
      title: d.title || f,
      date: d.date || '',
      source: d.source || '',
      summary: d.summary_zh || d.summary || '',
      cover: d.cover || '/covers/news/default.svg',
      updated: d.updated || '',
      url: d.url || '',
      tags: String(d.tags || '').split(/[、,，]/).map((s) => s.trim()).filter(Boolean),
      link: '/news/' + f.replace(/\.md$/, '.html')
    };
  }).filter((x) => /^\d{4}-\d{2}-\d{2}$/.test(x.date));

  // 读取 data/news/*.json（手动投放 或 AI 生成）
  const dataDir = path.resolve(__dirname, '..', 'data', 'news');
  const rich = new Map();
  if (fs.existsSync(dataDir)) {
    for (const f of fs.readdirSync(dataDir)) {
      if (!f.endsWith('.json') || f.startsWith('_')) continue;
      try {
        const obj = JSON.parse(fs.readFileSync(path.join(dataDir, f), 'utf8'));
        const day = f.replace(/\.json$/, '');
        (obj.items || []).forEach((it) => {
          if (it && it.id) rich.set(it.id, { ...it, _day: day });
        });
      } catch (e) { /* 坏文件跳过，不影响构建 */ }
    }
  }

  const mdIds = new Set(mdItems.map((m) => m.id));

  // 只在 JSON 里存在、没有对应 md 的条目（手工新增的）也要展示
  const extra = [];
  for (const [id, r] of rich) {
    if (mdIds.has(id)) continue;
    const day = /^\d{4}-\d{2}-\d{2}$/.test(r._day || '')
      ? r._day
      : String(r.publishedAt || '').slice(0, 10);
    if (!/^\d{4}-\d{2}-\d{2}$/.test(day)) continue;
    extra.push({
      id,
      title: r.title || id,
      date: day,
      source: r.source || '',
      image: r.image || '/covers/news/default.svg',
      url: r.url || '',
      link: r.link || '',
      tags: r.tags || [],
      publishedAt: r.publishedAt || (day + 'T09:00:00+08:00'),
      summary: r.summary || '',
      detail: r.detail || '',
      points: r.points || [],
      quotes: r.quotes || [],
      entities: r.entities || { companies: [], models: [], tools: [] },
      advice: r.advice || { learn: '', do: '' }
    });
  }

  const merged = mdItems.map((m) => {
    const r = rich.get(m.id);
    const base = {
      id: m.id,
      title: m.title,
      date: m.date,
      source: m.source,
      image: m.cover,
      url: m.url,
      link: m.link,
      tags: m.tags,
      publishedAt: m.updated || (m.date + 'T08:00:00+08:00'),
      summary: m.summary,
      detail: '',
      points: [],
      quotes: [],
      entities: { companies: [], models: [], tools: [] },
      advice: { learn: '', do: '' }
    };
    if (!r) return base;
    return {
      ...base,
      summary: r.summary || m.summary,
      detail: r.detail || '',
      points: r.points || [],
      quotes: r.quotes || [],
      image: r.image || m.cover,
      entities: r.entities || base.entities,
      tags: (r.tags && r.tags.length) ? r.tags : m.tags,
      advice: r.advice || base.advice,
      publishedAt: r.publishedAt || base.publishedAt,
      url: r.url || m.url,
      link: r.link || m.link
    };
  }).concat(extra).sort((a, b) => (a.publishedAt < b.publishedAt ? 1 : -1));

  // 按日期分组
  const byDate = new Map();
  merged.forEach((it) => {
    if (!byDate.has(it.date)) byDate.set(it.date, []);
    byDate.get(it.date).push(it);
  });
  const days = [...byDate.entries()]
    .sort((a, b) => (a[0] < b[0] ? 1 : -1))
    .map(([date, items]) => ({ date, items }));

  const srcSet = new Set();
  merged.forEach((i) => { if (i.source) srcSet.add(i.source); });
  const tagCount = new Map();
  merged.forEach((i) => (i.tags || []).forEach((t) => tagCount.set(t, (tagCount.get(t) || 0) + 1)));
  const tags = [...tagCount.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 20)
    .map(([name, count]) => ({ name, count }));

  const lib = {
    updatedAt: new Date().toISOString(),
    total: merged.length,
    days,
    sources: [...srcSet].sort(),
    tags
  };
  const pub = path.join(DOCS, 'public');
  if (!fs.existsSync(pub)) fs.mkdirSync(pub, { recursive: true });
  fs.writeFileSync(path.join(pub, 'news-library.json'), JSON.stringify(lib), 'utf8');

  const stamp = todayStr();
  const richCount = merged.filter((i) => i.detail).length;
  const body = fm({ title: '每日热点详情库' }) + hero('news') +
    `# 每日热点详情库\n\n共 **${merged.length}** 条，其中 **${richCount}** 条已生成详细解读。\n\n` +
    `> 🗓️ **数据更新于 ${stamp}** · 按日期分组，点卡片展开看详细摘要、关键要点、原文摘录和学习建议。\n` +
    `> 顶部可按关键词、来源、日期、标签筛选。\n\n` +
    `<NewsLibrary />\n`;

  write(path.join(dir, 'index.md'), body);
  console.log('热点详情库：' + merged.length + ' 条（含详细解读 ' + richCount + ' 条）');
})();

/* ---------- 5. 我的笔记 ---------- */
(function buildNotes() {
  const dir = path.join(DOCS, 'notes');
  const files = listMd(dir);
  const groups = {};
  files.forEach((f) => {
    const d = readFM(path.join(dir, f));
    const cat = d.category || '未分类';
    (groups[cat] = groups[cat] || []).push({
      name: d.title || f, link: './' + f,
      emoji: d.emoji || '✍️',
      desc: [d.date, d.tags, d.summary].filter(Boolean).join(' · '),
      tag: cat
    });
  });

  let body = fm({ title: '我的笔记' }) + hero('notes') +
    `# 我的笔记\n\n共 **${files.length}** 篇。\n\n` +
    `> 在 \`docs/notes/\` 下新建 \`.md\` 文件就会出现在这里。配了 AI 之后，脚本会自动帮你补上分类、标签和一句话总结。\n`;

  Object.keys(groups).forEach((cat) => {
    body += `\n## ${cat}\n\n<div class="cl-cards">\n` +
      groups[cat].map((n) => cardItem(n)).join('\n') + `\n</div>\n`;
  });

  if (!files.length) {
    body += '\n_还没有笔记。在 `docs/notes/` 下新建一个 `.md` 文件试试。_\n';
  }

  write(path.join(dir, 'index.md'), body);
  console.log('笔记索引：' + files.length + ' 篇');
})();

/* ---------- 6. AI 实操 / 开发进阶 ---------- */
(function buildDev() {
  const n = buildGrouped('dev', 'AI 实操 / 开发进阶', '⚙️',
    '从调 API 到搭 Agent、跑工作流，动手把 AI 用起来。');
  console.log('AI实操索引：' + n + ' 篇');
})();

/* ---------- 7. 场景应用 ---------- */
(function buildScenes() {
  const n = buildGrouped('scenes', '场景应用', '✨',
    'AI PPT、视频生成、绘图等实用玩法，附详细图文 / 视频步骤。');
  console.log('场景应用索引：' + n + ' 篇');
})();

/* ---------- 8. 视频教程（B 站外链嵌入，纯前端） ----------
   用户在 cl-kb/data/videos.json 里粘贴 B 站链接即可，
   本函数读取后生成 docs/video/index.md（含 <BiliEmbed> 嵌入框），
   不调用任何外部接口，不会出现 404。 */
(function buildVideo() {
  const dir = path.join(DOCS, 'video')
  fs.mkdirSync(dir, { recursive: true })

  let videos = []
  const dataFile = path.resolve(__dirname, '..', 'data', 'videos.json')
  if (fs.existsSync(dataFile)) {
    try {
      const raw = fs.readFileSync(dataFile, 'utf8').replace(/\r\n/g, '\n')
      const arr = JSON.parse(raw)
      if (Array.isArray(arr)) videos = arr
    } catch (e) {
      console.log('视频数据解析失败（videos.json）：' + e.message)
    }
  }

  let body = fm({ title: '视频教程' }) + hero('video') +
    '# 视频教程\n\n跟着视频动手学，比纯文字快得多。\n\n' +
    '> 视频直接嵌入 **B 站（哔哩哔哩）**，站内就能看，**不用跳出去、也不会 404**。\n'

  if (!videos.length) {
    body += '\n_还没有视频。把 B 站链接填进 `data/videos.json` 就会出现在这一页。_\n'
  } else {
    videos.forEach((v, i) => {
      const title = (v.title || '未命名视频').replace(/"/g, '&quot;')
      const url = (v.url || v.bvid || '').replace(/"/g, '&quot;')
      body += `## ${i + 1}. ${title}\n\n`
      if (v.desc) body += v.desc + '\n\n'
      if (v.tag) body += `<span class="cl-tag">${v.tag}</span>\n\n`
      if (url) {
        body += `<BiliEmbed url="${url}" title="${title}" />\n\n`
      } else {
        body += `<BiliEmbed title="${title}" />\n\n`
      }
    })
  }

  write(path.join(dir, 'index.md'), body)
  console.log('视频索引：' + videos.length + ' 个')
})();

/* ---------- 9. 全能搜索索引（纯前端） ----------
   生成 docs/public/search-index.json，前端 SiteSearch 组件读取后做站内模糊搜索。
   覆盖：文章标题、工具名、标签、板块分类、正文摘要。不调用任何外部接口。 */
(function buildSearch() {
  const PUBLIC = path.join(DOCS, 'public')
  fs.mkdirSync(PUBLIC, { recursive: true })

  const FOLDER_LABEL = {
    glossary: '术语词典', tools: '工具库', news: '每日热点',
    path: '学习路径', dev: 'AI 实操', scenes: '场景应用',
    video: '视频教程', notes: '我的笔记', utils: '小工具'
  }

  const out = []
  function walk(dir, rel) {
    if (!fs.existsSync(dir)) return
    for (const f of fs.readdirSync(dir)) {
      if (f.startsWith('.')) continue
      const fp = path.join(dir, f)
      const st = fs.statSync(fp)
      if (st.isDirectory()) {
        walk(fp, path.join(rel, f))
        continue
      }
      if (!f.endsWith('.md')) continue
      const relp = path.relative(DOCS, fp).split(path.sep).join('/')
      let url
      if (path.basename(f, '.md') === 'index') {
        const d = path.dirname(relp).split('/').filter((s) => s && s !== '.').join('/')
        url = d ? '/' + d + '/' : '/'
      } else {
        url = '/' + relp.replace(/\.md$/, '') + '.html'
      }
      const raw = fs.readFileSync(fp, 'utf8').replace(/\r\n/g, '\n')
      const d = readFM(fp)
      const fmBlock = raw.match(/^---\n[\s\S]*?\n---\n?/)
      const body = (fmBlock ? raw.slice(fmBlock[0].length) : raw)
        .replace(/```[\s\S]*?```/g, ' ')
        .replace(/^---\n[\s\S]*?\n---/, ' ')
        .replace(/[#>*_`~]/g, ' ')
        .replace(/\[([^\]]*)\]\([^)]*\)/g, '$1')
        .replace(/\s+/g, ' ')
        .trim()
      const title = d.title
        || (body.match(/^#\s+(.+)$/m) || [, ''])[1]
        || path.basename(f, '.md')
      const top = relp.split('/')[0]
      const cat = FOLDER_LABEL[top] || (top || '首页')
      const tags = []
      if (d.tag) tags.push(String(d.tag))
      if (d.tags) tags.push(String(d.tags))
      if (d.category) tags.push(String(d.category))
      if (d.en) tags.push(String(d.en))
      out.push({
        title: title.trim(),
        url,
        category: cat,
        tags: [...new Set(tags)].slice(0, 6),
        desc: (d.desc || d.summary || '').toString().slice(0, 120),
        text: body.slice(0, 240)
      })
    }
  }
  walk(DOCS, '')
  fs.writeFileSync(path.join(PUBLIC, 'search-index.json'), JSON.stringify(out), 'utf8')
  console.log('搜索索引：' + out.length + ' 条')
})();

/* ---------- 10. 站点地图 + robots（SEO / 可发现性） ----------
   生成 docs/public/sitemap.xml 与 docs/public/robots.txt。
   VitePress 构建时会把 docs/public 的内容原样拷贝到站点根目录，
   因此线上可直接访问 /sitemap.xml 与 /robots.txt。
   站点根地址由环境变量 SITE_URL 控制（默认是 WorkBuddy 发布地址）。 */
(function buildSitemap() {
  const PUBLIC = path.join(DOCS, 'public')
  fs.mkdirSync(PUBLIC, { recursive: true })
  const SITE_URL = (process.env.SITE_URL || 'https://fc04b7d4bf66445ba9dd7b6f99bd2681.app.workbuddy.link')
    .replace(/\/+$/, '')

  const urls = new Set()
  function walk(dir, rel) {
    if (!fs.existsSync(dir)) return
    for (const f of fs.readdirSync(dir)) {
      if (f.startsWith('.')) continue
      if (f === '404.md') continue
      const fp = path.join(dir, f)
      const st = fs.statSync(fp)
      if (st.isDirectory()) { walk(fp, path.join(rel, f)); continue }
      if (!f.endsWith('.md')) continue
      const relp = path.relative(DOCS, fp).split(path.sep).join('/')
      let url
      if (path.basename(f, '.md') === 'index') {
        const d = path.dirname(relp).split('/').filter((s) => s && s !== '.').join('/')
        url = d ? '/' + d + '/' : '/'
      } else {
        url = '/' + relp.replace(/\.md$/, '') + '.html'
      }
      urls.add(url)
    }
  }
  walk(DOCS, '')

  // 去重并按路径排序，保证每次生成结果稳定（便于 diff / 缓存）
  const list = [...urls].sort()
  const locs = list.map((u) => '  <url><loc>' + SITE_URL + u + '</loc></url>').join('\n')
  const xml = '<?xml version="1.0" encoding="UTF-8"?>\n' +
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + locs + '\n</urlset>\n'
  fs.writeFileSync(path.join(PUBLIC, 'sitemap.xml'), xml, 'utf8')

  const robots = 'User-agent: *\nAllow: /\n\nSitemap: ' + SITE_URL + '/sitemap.xml\n'
  fs.writeFileSync(path.join(PUBLIC, 'robots.txt'), robots, 'utf8')
  console.log('站点地图：' + list.length + ' 条 → /sitemap.xml /robots.txt')
})();

/* ============================================================
   第二步新板块（赛博朋克升级）
   11. 把 data/ 下的板块数据复制到公开目录
   12. 时光引擎（昨日复盘 / 今日冲刺 / 明日先知 / 灵感瀑布）
   13. AI 盲盒挑战
   14. 技能树
   15. 视觉影音室
   全部在构建期生成静态 HTML，页面不依赖运行时请求，不会 404
   ============================================================ */

/* ---------- 11. 板块数据 → 公开目录 ---------- */
(function copyBoardData() {
  const DATA = path.resolve(__dirname, '..', 'data')
  const PUBLIC = path.join(DOCS, 'public')
  fs.mkdirSync(PUBLIC, { recursive: true })
  let n = 0
  for (const f of ['blindbox.json', 'skilltree.json', 'media.json']) {
    const src = path.join(DATA, f)
    if (!fs.existsSync(src)) continue
    fs.writeFileSync(path.join(PUBLIC, f), fs.readFileSync(src, 'utf8'), 'utf8')
    n++
  }
  console.log('板块数据：复制 ' + n + ' 个 JSON 到 public')
})();

/* ---------- 通用小工具 ---------- */
function esc(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

/* 把 markdown 里的相对链接 ./path/x.md 转成站点可直接访问的 /path/x.html */
function toSiteUrl(u) {
  let s = String(u == null ? '' : u).trim()
  if (s.startsWith('./')) s = s.slice(1)
  if (!s.startsWith('/')) s = '/' + s
  return s.replace(/\.md$/, '.html')
}

/* 从 B 站链接或裸 BV 号里抠出 BV 号 */
function pickBv(s) {
  const t = String(s == null ? '' : s)
  const m = t.match(/BV[0-9A-Za-z]+/)
  return m ? m[0] : ''
}

/* 按标题/标签猜一张本地封面（境外图床会裂图，一律用本地 SVG） */
const NEWS_COVER_RULES = [
  [/agent|智能体/i, 'agent'],
  [/robot|机器人|具身/i, 'robot'],
  [/video|视频|sora|可灵|runway/i, 'video'],
  [/image|图像|绘图|生图|flux|midjourney|stable/i, 'image'],
  [/code|编程|coding|代码|cursor|copilot/i, 'code'],
  [/search|搜索|检索|rag|向量/i, 'search'],
  [/open.?source|开源/i, 'opensource'],
  [/policy|监管|法规|合规|隐私|安全/i, 'policy'],
  [/research|研究|论文|paper/i, 'research'],
  [/office|ppt|文档|表格|幻灯片/i, 'office'],
  [/chip|芯片|算力|gpu|英伟达/i, 'chip'],
  [/flow|工作流|自动化|n8n|dify|编排/i, 'flow'],
  [/chat|对话|聊天/i, 'chat'],
  [/llm|大模型|gpt|claude|gemini|qwen|deepseek|模型/i, 'llm']
]
function pickCover(text) {
  const s = String(text || '')
  for (const r of NEWS_COVER_RULES) {
    if (r[0].test(s)) return '/covers/news/' + r[1] + '.svg'
  }
  return '/covers/news/default.svg'
}

function todayStr() {
  const d = new Date()
  const p = (n) => String(n).padStart(2, '0')
  return d.getFullYear() + '-' + p(d.getMonth() + 1) + '-' + p(d.getDate())
}

/* ---------- 12. 时光引擎 ---------- */
(function buildTimeEngine() {
  /* —— 今日冲刺：解析 docs/today.md（每日脚本自动写入的那个文件） —— */
  const todayFile = path.join(DOCS, 'today.md')
  const todayTasks = []
  let intro = ''
  if (fs.existsSync(todayFile)) {
    const raw = fs.readFileSync(todayFile, 'utf8').replace(/\r\n/g, '\n')
    const body = raw.replace(/^---\n[\s\S]*?\n---\n?/, '')
    for (const line of body.split('\n')) {
      const t = line.trim()
      if (!t || t.startsWith('#') || t.startsWith('>') || t.startsWith('-') || t.startsWith('---')) continue
      if (t.startsWith('##')) break
      intro = t
      break
    }
    const sec = body.split(/^##\s+/m).find((s) => s.indexOf('今天做这几件事') === 0)
    if (sec) {
      const re = /^\s*\d+\.\s+\[([^\]]+)\]\(([^)]+)\)(.*)$/gm
      let m
      while ((m = re.exec(sec))) {
        const rest = m[3] || ''
        const sm = rest.match(/<sub>([^<]*)<\/sub>/)
        todayTasks.push({
          title: m[1].trim(),
          url: toSiteUrl(m[2]),
          stage: sm ? sm[1].trim() : ''
        })
      }
    }
  }

  /* —— 昨日复盘 / 明日先知：来自 docs/path 的任务完成情况 —— */
  const pathDir = path.join(DOCS, 'path')
  const pTasks = []
  if (fs.existsSync(pathDir)) {
    for (const sd of fs.readdirSync(pathDir).sort()) {
      const sub = path.join(pathDir, sd)
      if (!fs.statSync(sub).isDirectory()) continue
      for (const f of fs.readdirSync(sub).sort()) {
        if (!f.endsWith('.md') || f === 'index.md') continue
        const d = readFM(path.join(sub, f))
        pTasks.push({
          title: d.title || path.basename(f, '.md'),
          stage: Number(d.stage) || 0,
          order: Number(d.order) || 0,
          done: d.done === true,
          url: '/path/' + sd + '/' + f.replace(/\.md$/, '.html')
        })
      }
    }
  }
  pTasks.sort((a, b) => (a.stage - b.stage) || (a.order - b.order))
  const todayUrls = new Set(todayTasks.map((t) => t.url))
  const yesterday = pTasks.filter((t) => t.done).slice(-3).reverse()
  const tomorrow = pTasks.filter((t) => !t.done && !todayUrls.has(t.url)).slice(0, 4)

  /* —— 灵感瀑布：最新热点 + 本地封面 —— */
  const newsDir = path.join(DOCS, 'news')
  const news = []
  if (fs.existsSync(newsDir)) {
    for (const f of fs.readdirSync(newsDir)) {
      if (!f.endsWith('.md') || f === 'index.md') continue
      const d = readFM(path.join(newsDir, f))
      const title = d.title || path.basename(f, '.md')
      news.push({
        title,
        date: d.date || (f.match(/^\d{4}-\d{2}-\d{2}/) || [''])[0],
        tag: d.tag || d.tags || '热点',
        url: '/news/' + f.replace(/\.md$/, '.html'),
        cover: pickCover(title + ' ' + (d.tag || '') + ' ' + (d.tags || ''))
      })
    }
  }
  news.sort((a, b) => String(b.date).localeCompare(String(a.date)))
  const inspiration = news.slice(0, 8)

  /* —— 组装页面 —— */
  const LEVELS = { must: '必做', urgent: '重要紧急', normal: '常规' }
  const L = []
  L.push('---')
  L.push('title: "时光引擎"')
  L.push('sidebar: false')
  L.push('aside: false')
  L.push('---')
  L.push('')
  L.push('<div class="cl-te">')
  L.push('  <div class="cl-te-hero">')
  L.push('    <div class="cl-te-hero-main">')
  L.push('      <span class="cl-te-kicker">TIME ENGINE</span>')
  L.push('      <h1 class="cl-te-h1">时光引擎</h1>')
  L.push('      <p class="cl-te-intro">' + esc(intro || '昨天做了什么、今天该冲什么、明天会学到什么、现在有什么值得看——一屏全给你。') + '</p>')
  L.push('    </div>')
  L.push('    <div class="cl-te-hero-side">')
  L.push('      <div class="cl-te-date">' + todayStr() + '</div>')
  L.push('      <div class="cl-te-date-sub">打卡记录存在你自己的浏览器里，刷新不丢</div>')
  L.push('    </div>')
  L.push('  </div>')

  /* 昨日复盘 */
  L.push('  <section class="cl-te-block" data-block="yesterday">')
  L.push('    <div class="cl-te-head"><span class="cl-te-ico">🕰️</span><h2>昨日复盘</h2><span class="cl-te-sub">回头看一眼，心里有数</span></div>')
  L.push('    <div class="cl-te-list">')
  if (!yesterday.length) {
    L.push('      <div class="cl-te-empty">还没有已完成的任务。去 <a href="/path/">学习路径</a> 勾掉第一个，明天这里就有内容了。</div>')
  } else {
    yesterday.forEach((t) => {
      L.push('      <a class="cl-te-item is-done" href="' + esc(t.url) + '">')
      L.push('        <span class="cl-te-dot"></span>')
      L.push('        <span class="cl-te-title">' + esc(t.title) + '</span>')
      L.push('        <span class="cl-te-stage">阶段' + '一二三四五六'[Math.max(0, t.stage - 1)] + '</span>')
      L.push('      </a>')
    })
  }
  L.push('    </div>')
  L.push('  </section>')

  /* 今日冲刺 */
  L.push('  <section class="cl-te-block is-main" data-block="today">')
  L.push('    <div class="cl-te-head"><span class="cl-te-ico">⚡</span><h2>今日冲刺</h2><span class="cl-te-sub">点圆圈打卡，点标签切换「必做 / 重要紧急 / 常规」</span></div>')
  L.push('    <div class="cl-te-list">')
  if (!todayTasks.length) {
    L.push('      <div class="cl-te-empty">今天的推荐任务还没生成。可以先去 <a href="/path/">学习路径</a> 自己挑一个。</div>')
  } else {
    todayTasks.forEach((t, i) => {
      const lv = i === 0 ? 'must' : (i === 1 ? 'urgent' : 'normal')
      L.push('      <div class="cl-te-item cl-te-task" data-key="' + esc(t.url) + '">')
      L.push('        <button class="cl-te-check" type="button" aria-label="打卡"></button>')
      L.push('        <span class="cl-te-title"><a href="' + esc(t.url) + '">' + esc(t.title) + '</a></span>')
      if (t.stage) L.push('        <span class="cl-te-stage">' + esc(t.stage) + '</span>')
      L.push('        <button class="cl-te-level" type="button" data-level="' + lv + '">' + LEVELS[lv] + '</button>')
      L.push('      </div>')
    })
  }
  L.push('    </div>')
  L.push('  </section>')

  /* 明日先知 */
  L.push('  <section class="cl-te-block" data-block="tomorrow">')
  L.push('    <div class="cl-te-head"><span class="cl-te-ico">🔭</span><h2>明日先知</h2><span class="cl-te-sub">提前瞄一眼，明天不慌</span></div>')
  L.push('    <div class="cl-te-list">')
  if (!tomorrow.length) {
    L.push('      <div class="cl-te-empty">后面的任务都学完了，厉害！可以去 <a href="/dev/">AI 实操</a> 找点难的。</div>')
  } else {
    tomorrow.forEach((t) => {
      L.push('      <a class="cl-te-item" href="' + esc(t.url) + '">')
      L.push('        <span class="cl-te-dot"></span>')
      L.push('        <span class="cl-te-title">' + esc(t.title) + '</span>')
      L.push('        <span class="cl-te-stage">阶段' + '一二三四五六'[Math.max(0, t.stage - 1)] + '</span>')
      L.push('      </a>')
    })
  }
  L.push('    </div>')
  L.push('  </section>')

  /* 灵感瀑布 */
  L.push('  <section class="cl-te-block" data-block="inspiration">')
  L.push('    <div class="cl-te-head"><span class="cl-te-ico">🌊</span><h2>灵感瀑布</h2><span class="cl-te-sub">最近值得看的动态，看图挑</span></div>')
  L.push('    <div class="cl-te-falls">')
  if (!inspiration.length) {
    L.push('      <div class="cl-te-empty">热点还在抓取中，去 <a href="/news/">每日热点</a> 看看。</div>')
  } else {
    inspiration.forEach((n) => {
      L.push('      <a class="cl-te-fall" href="' + esc(n.url) + '">')
      L.push('        <img src="' + esc(n.cover) + '" alt="" loading="lazy">')
      L.push('        <div class="cl-te-fall-meta">')
      L.push('          <span class="cl-te-fall-tag">' + esc(n.tag) + '</span>')
      L.push('          <span class="cl-te-fall-title">' + esc(n.title) + '</span>')
      L.push('          <span class="cl-te-fall-date">' + esc(n.date) + '</span>')
      L.push('        </div>')
      L.push('      </a>')
    })
  }
  L.push('    </div>')
  L.push('  </section>')
  L.push('</div>')

  write(path.join(DOCS, 'time-engine.md'), L.join('\n'))
  console.log('时光引擎：' + todayTasks.length + ' 冲刺 / ' + yesterday.length + ' 复盘 / ' + tomorrow.length + ' 先知 / ' + inspiration.length + ' 灵感')
})();

/* ---------- 13. AI 盲盒挑战 ---------- */
(function buildBlindBox() {
  const src = path.join(path.resolve(__dirname, '..', 'data'), 'blindbox.json')
  if (!fs.existsSync(src)) return
  const list = JSON.parse(fs.readFileSync(src, 'utf8'))
  const L = []
  L.push('---')
  L.push('title: "AI 盲盒挑战"')
  L.push('sidebar: false')
  L.push('aside: false')
  L.push('---')
  L.push('')
  L.push('<div class="cl-bb">')
  L.push('  <p class="cl-bb-lead">每天开一个盒子，抽到一个 3–20 分钟就能做完的小挑战。做完点「标记已完成」，进度存在你自己的浏览器里，刷新不丢。</p>')
  L.push('  <div class="cl-bb-slot" id="cl-bb-slot">')
  L.push('    <button class="cl-bb-box" id="cl-bb-box" type="button">')
  L.push('      <span class="cl-bb-box-emoji">🎁</span>')
  L.push('      <span class="cl-bb-box-txt">点击开启今日盲盒</span>')
  L.push('    </button>')
  L.push('  </div>')
  L.push('  <div class="cl-bb-actions">')
  L.push('    <button class="cl-bb-btn" id="cl-bb-again" type="button">🔄 换一个</button>')
  L.push('    <button class="cl-bb-btn ghost" id="cl-bb-done" type="button">✅ 标记已完成</button>')
  L.push('  </div>')
  L.push('  <div class="cl-bb-stat" id="cl-bb-stat"></div>')
  L.push('  <div class="cl-bb-pool" id="cl-bb-pool" hidden>')
  list.forEach((c, i) => {
    L.push('    <div class="cl-bb-card" data-idx="' + i + '">')
    L.push('      <span class="cl-bb-card-tag">' + esc(c.tag) + '</span>')
    L.push('      <h3 class="cl-bb-card-title">' + esc(c.title) + '</h3>')
    L.push('      <p class="cl-bb-card-desc">' + esc(c.desc) + '</p>')
    if (c.tip) L.push('      <p class="cl-bb-card-tip">💡 ' + esc(c.tip) + '</p>')
    L.push('      <div class="cl-bb-card-foot">')
    L.push('        <span class="cl-bb-min">⏱ 约 ' + Number(c.min || 5) + ' 分钟</span>')
    if (c.link) L.push('        <a class="cl-bb-link" href="' + esc(c.link) + '">相关板块 →</a>')
    L.push('      </div>')
    L.push('    </div>')
  })
  L.push('  </div>')
  L.push('</div>')
  write(path.join(DOCS, 'blindbox.md'), L.join('\n'))
  console.log('AI 盲盒：' + list.length + ' 个挑战')
})();

/* ---------- 14. 技能树 ---------- */
(function buildSkillTree() {
  const src = path.join(path.resolve(__dirname, '..', 'data'), 'skilltree.json')
  if (!fs.existsSync(src)) return
  const tiers = JSON.parse(fs.readFileSync(src, 'utf8'))
  let total = 0
  tiers.forEach((t) => { total += (t.skills || []).length })
  const L = []
  L.push('---')
  L.push('title: "技能树"')
  L.push('sidebar: false')
  L.push('aside: false')
  L.push('---')
  L.push('')
  L.push('<div class="cl-st">')
  L.push('  <p class="cl-st-lead">像打游戏一样点亮技能。点左边的圈就算学会，进度和等级存在你自己的浏览器里。</p>')
  L.push('  <div class="cl-st-hud">')
  L.push('    <div class="cl-st-hud-left">')
  L.push('      <span class="cl-st-lv" id="cl-st-lv">Lv.1</span>')
  L.push('      <span class="cl-st-lvname" id="cl-st-lvname">AI 新手</span>')
  L.push('    </div>')
  L.push('    <div class="cl-st-hud-right"><span id="cl-st-count">0 / ' + total + '</span><span class="cl-st-xpsum" id="cl-st-xp">0 XP</span></div>')
  L.push('  </div>')
  L.push('  <div class="cl-st-bar"><span id="cl-st-bar" style="width:0%"></span></div>')
  tiers.forEach((t) => {
    L.push('  <section class="cl-st-tier" data-tier="' + esc(t.id) + '">')
    L.push('    <div class="cl-st-tier-head">')
    L.push('      <span class="cl-st-ico">' + esc(t.icon || '⭐') + '</span>')
    L.push('      <h3>' + esc(t.name) + '</h3>')
    if (t.desc) L.push('      <span class="cl-st-tier-desc">' + esc(t.desc) + '</span>')
    L.push('    </div>')
    L.push('    <div class="cl-st-nodes">')
    ;(t.skills || []).forEach((s) => {
      L.push('      <div class="cl-st-node" data-skill="' + esc(s.id) + '" data-xp="' + Number(s.xp || 10) + '">')
      L.push('        <button class="cl-st-dot" type="button" aria-label="点亮这个技能"></button>')
      L.push('        <div class="cl-st-node-main">')
      L.push('          <a class="cl-st-node-name" href="' + esc(s.link || '/path/') + '">' + esc(s.name) + '</a>')
      if (s.desc) L.push('          <span class="cl-st-node-desc">' + esc(s.desc) + '</span>')
      L.push('        </div>')
      L.push('        <span class="cl-st-xp">+' + Number(s.xp || 10) + ' XP</span>')
      L.push('      </div>')
    })
    L.push('    </div>')
    L.push('  </section>')
  })
  L.push('  <div class="cl-st-foot"><button class="cl-st-reset" id="cl-st-reset" type="button">重置全部进度</button></div>')
  L.push('</div>')
  write(path.join(DOCS, 'skilltree.md'), L.join('\n'))
  console.log('技能树：' + tiers.length + ' 层 / ' + total + ' 个技能')
})();

/* ---------- 15. 视觉影音室 ---------- */
(function buildMediaRoom() {
  const src = path.join(path.resolve(__dirname, '..', 'data'), 'media.json')
  if (!fs.existsSync(src)) return
  const list = JSON.parse(fs.readFileSync(src, 'utf8'))
  const L = []
  L.push('---')
  L.push('title: "视觉影音室"')
  L.push('sidebar: false')
  L.push('aside: false')
  L.push('---')
  L.push('')
  L.push('<div class="cl-mr">')
  L.push('  <p class="cl-mr-lead">左边看视频，右边看要点。<strong>想换成你自己的 B 站视频</strong>：打开视频页复制带 BV 的链接，粘到 <code>data/media.json</code> 的 <code>bvid</code> 后面，重新发布即可。</p>')
  L.push('  <div class="cl-mr-list">')
  list.forEach((it) => {
    const bv = pickBv(it.bvid || it.url || '')
    L.push('    <article class="cl-mr-item">')
    L.push('      <div class="cl-mr-video">')
    if (bv) {
      const q = 'bvid=' + bv + '&page=1&high_quality=1&danmaku=0&autoplay=0'
      L.push('        <iframe src="https://player.bilibili.com/player.html?' + q + '" scrolling="no" border="0" frameborder="no" framespacing="0" allowfullscreen="true" loading="lazy" title="' + esc(it.title) + '"></iframe>')
    } else {
      L.push('        <div class="cl-mr-ph">')
      L.push('          <img src="' + esc('/covers/news/' + (it.cover || 'default') + '.svg') + '" alt="" loading="lazy">')
      L.push('          <span class="cl-mr-ph-badge">待接入</span>')
      L.push('          <span class="cl-mr-ph-tip">在 data/media.json 里填入 BV 号</span>')
      L.push('        </div>')
    }
    L.push('      </div>')
    L.push('      <div class="cl-mr-info">')
    L.push('        <span class="cl-mr-tag">' + esc(it.tag || '未分类') + '</span>')
    L.push('        <h3>' + esc(it.title) + '</h3>')
    L.push('        <p>' + esc(it.desc || '') + '</p>')
    if (it.level) L.push('        <span class="cl-mr-level">' + esc(it.level) + '</span>')
    L.push('      </div>')
    L.push('    </article>')
  })
  L.push('  </div>')
  L.push('</div>')
  write(path.join(DOCS, 'media.md'), L.join('\n'))
  console.log('视觉影音室：' + list.length + ' 个位置（' + list.filter((x) => pickBv(x.bvid || x.url || '')).length + ' 个已接入）')
})();

/* ---------- 14. 双向关联图谱（术语⇄路径⇄热点，按概念互联） ----------
   生成 docs/public/links-graph.json，前端 RelatedLinks 组件读取后，
   在每篇文档底部展示「来自其它板块、且话题相关」的跳转链接，实现双向关联。
   关联依据：从术语词典抽取概念词 + 一份跨板块常见概念词表，
   对每篇文档的标题/简介/标签/正文做概念命中；命中同一概念即认为相关。 */
(function buildLinksGraph() {
  const PUBLIC = path.join(DOCS, 'public')
  fs.mkdirSync(PUBLIC, { recursive: true })

  const TYPE_LABEL = {
    glossary: '术语', path: '学习路径', dev: 'AI 实操',
    scenes: '场景应用', tools: '工具库', notes: '我的笔记', news: '每日热点'
  }

  // 递归收集目录下的所有 .md（不含 index.md）
  function walkMd(dir, rel) {
    const out = []
    if (!fs.existsSync(dir)) return out
    for (const f of fs.readdirSync(dir)) {
      if (f.startsWith('.')) continue
      const fp = path.join(dir, f)
      const st = fs.statSync(fp)
      if (st.isDirectory()) out.push(...walkMd(fp, path.join(rel, f)))
      else if (f.endsWith('.md') && f !== 'index.md') out.push({ fp, rel: path.join(rel, f) })
    }
    return out
  }

  function bodyText(fp, n = 600) {
    const raw = fs.readFileSync(fp, 'utf8').replace(/\r\n/g, '\n')
    const m = raw.match(/^---\n[\s\S]*?\n---\n?/)
    const body = (m ? raw.slice(m[0].length) : raw)
      .replace(/```[\s\S]*?```/g, ' ')
      .replace(/<[^>]+>/g, ' ')
      .replace(/[#>*_`~]/g, ' ')
      .replace(/\s+/g, ' ')
      .trim()
    return body.slice(0, n)
  }

  // 概念词典：key(小写) -> Set(别名小写)
  const conceptMap = new Map()
  const addConcept = (key, aliases) => {
    const k = String(key).trim().toLowerCase()
    if (!k) return
    if (!conceptMap.has(k)) conceptMap.set(k, new Set())
    ;[key, ...(aliases || [])].forEach((a) => {
      const s = String(a).trim().toLowerCase()
      if (s) conceptMap.get(k).add(s)
    })
  }
  // 来自术语词典
  for (const { fp } of walkMd(path.join(DOCS, 'glossary'), '')) {
    const d = readFM(fp)
    if (d.en) addConcept(d.en, [d.en, d.title || ''])
    if (d.title) addConcept(d.title, [d.title, d.en || ''])
    if (d.category) addConcept(d.category, [d.category])
  }
  // 跨板块常见概念（保证术语⇄实操⇄热点能连上）
  const curated = {
    API: ['api', '接口'],
    Agent: ['agent', '智能体', 'agentic'],
    GPT: ['gpt', 'chatgpt'],
    Claude: ['claude'],
    OpenAI: ['openai'],
    Anthropic: ['anthropic'],
    Gemini: ['gemini', 'google ai', 'deepmind'],
    Llama: ['llama', 'meta ai'],
    提示词: ['提示词', '提示工程', 'prompt', 'prompting'],
    微调: ['微调', 'fine-tun', 'finetune', 'sft', 'lora'],
    多模态: ['多模态', 'multimodal'],
    文生图: ['文生图', 'text-to-image', 'stable diffusion', 'diffusion', 'midjourney', 'mj', '即梦', '可灵绘图'],
    文生视频: ['文生视频', 'text-to-video', 'sora', '可灵', '即梦视频', 'runway'],
    RAG: ['rag', '检索增强', 'retrieval-augmented'],
    大模型: ['大模型', 'llm', '大语言模型', 'language model', '基座模型'],
    聊天机器人: ['聊天机器人', 'chatbot', '对话助手'],
    开源: ['开源', 'open source', 'open-source'],
    Transformer: ['transformer'],
    注意力机制: ['注意力', 'attention'],
    扩散模型: ['扩散模型', 'diffusion model'],
    工作流: ['工作流', 'workflow', 'n8n', 'dify', '自动化流程'],
    本地部署: ['本地部署', 'local deploy', 'ollama', 'llama.cpp', '私有化部署'],
    向量数据库: ['向量数据库', 'vector db', 'embedding', '向量检索'],
    知识库: ['知识库', 'knowledge base'],
    语音识别: ['语音识别', 'asr', 'tts', '语音合成'],
    图像生成: ['图像生成', 'image generation'],
    视频生成: ['视频生成', 'video generation'],
    智能体: ['智能体', 'agent'],
    幻觉: ['幻觉', 'hallucinat'],
    对齐: ['对齐', 'alignment'],
    训练: ['训练', 'training', '预训练', 'pretrain'],
    推理: ['推理', 'inference', '部署推理']
  }
  for (const [k, al] of Object.entries(curated)) addConcept(k, al)

  function detect(text) {
    const low = String(text || '').toLowerCase()
    const found = []
    for (const [k, aliases] of conceptMap) {
      for (const a of aliases) {
        if (a.length >= 2 && low.includes(a)) { found.push(k); break }
      }
    }
    return [...new Set(found)]
  }

  const nodes = []
  for (const folder of Object.keys(TYPE_LABEL)) {
    if (folder === 'news') continue
    for (const { fp, rel } of walkMd(path.join(DOCS, folder), '')) {
      const d = readFM(fp)
      // 用正斜杠拼接 URL（Windows 的 path.join 会产生反斜杠，不能直接进链接）
      const relPosix = rel.split(path.sep).join('/')
      const url = '/' + folder + '/' + relPosix.replace(/\.md$/, '.html')
      const title = d.title || path.basename(relPosix, '.md')
      const text = [d.title, d.desc, d.tag, d.tags, d.category, d.en, d.summary, bodyText(fp)]
        .filter(Boolean).join(' ')
      nodes.push({ type: folder, title, url, concepts: detect(text) })
    }
  }
  // 热点：按日期聚合 data/news/*.json 的标签与标题
  const newsDir = path.resolve(__dirname, '..', 'data', 'news')
  if (fs.existsSync(newsDir)) {
    for (const f of fs.readdirSync(newsDir)) {
      if (!f.endsWith('.json')) continue
      const date = f.replace(/\.json$/, '')
      let arr = []
      try { arr = JSON.parse(fs.readFileSync(path.join(newsDir, f), 'utf8')) } catch (_) { continue }
      const items = Array.isArray(arr) ? arr : (arr.items || [])
      if (!items.length) continue
      const text = items.map((it) =>
        [it.title, it.summary, it.detail, (it.tags || []).join(' '), (it.tag || '')].join(' ')).join(' ')
      nodes.push({ type: 'news', title: date + ' 每日热点', url: '/news/' + date + '.html', concepts: detect(text) })
    }
  }

  // 计算每节点的「跨板块」相关项（共享概念数降序，取前 6）
  const byUrl = {}
  for (const node of nodes) {
    const set = new Set(node.concepts)
    const related = nodes
      .filter((o) => o.url !== node.url && o.type !== node.type && o.concepts.some((c) => set.has(c)))
      .map((o) => ({ shared: o.concepts.filter((c) => set.has(c)).length, o }))
      .sort((a, b) => b.shared - a.shared)
      .slice(0, 6)
      .map((x) => ({ title: x.o.title, url: x.o.url, type: x.o.type, label: TYPE_LABEL[x.o.type] }))
    byUrl[node.url] = { title: node.title, type: node.type, concepts: node.concepts, related }
  }

  fs.writeFileSync(path.join(PUBLIC, 'links-graph.json'), JSON.stringify({ byUrl }), 'utf8')
  const linked = Object.values(byUrl).filter((n) => n.related.length).length
  console.log('关联图谱：' + nodes.length + ' 节点 / ' + linked + ' 个页面有跨板块关联')
})();

console.log('索引与进度生成完成');
