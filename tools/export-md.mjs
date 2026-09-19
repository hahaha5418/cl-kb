/* ============================================================
   export-md.mjs · 一次性脚本
   把第一版 ai-kb/data.js 里的内容，批量导出成 Markdown 文件。
   以后你直接编辑 docs/ 下的 .md 文件就行，不用再跑这个脚本。
   用法：node tools/export-md.mjs
   ============================================================ */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const DATA_FILE = path.resolve(ROOT, '..', 'ai-kb', 'data.js');
const DOCS = path.join(ROOT, 'docs');

/* 少量英文名太长，手动指定一个短文件名 */
const SLUG_FIX = {
  'Reinforcement Learning from Human Feedback': 'rlhf',
  'Low-Rank Adaptation': 'lora',
  'Nucleus Sampling': 'top-p',
  'AI Generated Content': 'aigc',
  'Application Programming Interface': 'api',
  'Retrieval-Augmented Generation': 'rag',
  'Model Context Protocol': 'mcp'
};

function loadData() {
  const src = fs.readFileSync(DATA_FILE, 'utf8');
  const win = {};
  new Function('window', src)(win);
  return win.DATA;
}

function slugify(s, fallback = '') {
  const out = String(s || '').trim().toLowerCase()
    .replace(/[\s_]+/g, '-')
    .replace(/[^\p{L}\p{N}-]+/gu, '')
    .replace(/-+/g, '-')
    .replace(/^-+|-+$/g, '');
  return out || fallback || 'item';
}

function cut(s, n) {
  return String(s).replace(/[^\p{L}\p{N}]+/gu, '').slice(0, n);
}

function write(file, content) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, content, 'utf8');
}

function fm(obj) {
  const lines = Object.entries(obj).map(([k, v]) => {
    const val = typeof v === 'string' ? '"' + v.replace(/"/g, '\\"') + '"' : v;
    return `${k}: ${val}`;
  });
  return '---\n' + lines.join('\n') + '\n---\n\n';
}

const D = loadData();
let count = 0;

/* ---------- 术语：每个术语一个文件 ---------- */
const used = new Set();
D.glossary.forEach((g) => {
  let slug = SLUG_FIX[g.en] || slugify(g.en, slugify(g.term));
  while (used.has(slug)) slug += '-2';
  used.add(slug);

  write(path.join(DOCS, 'glossary', slug + '.md'),
    fm({ title: g.term, en: g.en, category: g.cat }) +
    `# ${g.term}\n\n` +
    `**一句话**：${g.one}\n\n` +
    `> 英文名：${g.en} · 分类：${g.cat}\n\n` +
    `## 详细解释\n\n${g.detail}\n\n` +
    `## 举个栗子\n\n${g.eg}\n\n` +
    `## 我的补充\n\n_（在这里写下你自己的理解、踩过的坑、看到的例子）_\n`
  );
  count++;
});

/* ---------- 学习路径：每个任务一个文件 ---------- */
D.path.forEach((stage, si) => {
  const sn = si + 1;
  const dir = path.join(DOCS, 'path', 'stage-' + sn);

  write(path.join(dir, 'index.md'),
    fm({ title: `${stage.stage} · ${stage.title}`, stage: sn }) +
    `# ${stage.stage} · ${stage.title}\n\n` +
    `**目标**：${stage.goal}\n\n` +
    `**预计耗时**：${stage.hours}\n\n` +
    `## 任务清单\n\n` +
    stage.tasks.map((t, ti) =>
      `- [ ] [${String(ti + 1).padStart(2, '0')} · ${t}](./${String(ti + 1).padStart(2, '0')}-${cut(t, 12)}.md)`
    ).join('\n') + '\n'
  );

  stage.tasks.forEach((t, ti) => {
    const nn = String(ti + 1).padStart(2, '0');
    write(path.join(dir, `${nn}-${cut(t, 12)}.md`),
      fm({ title: t, stage: sn, order: ti + 1, done: false }) +
      `# ${t}\n\n` +
      `> ${stage.stage} · ${stage.title} ｜ 第 ${ti + 1} 个任务\n\n` +
      `**阶段目标**：${stage.goal}\n\n` +
      `## 完成标准\n\n_（自己写：做到什么程度算过关）_\n\n` +
      `## 我的笔记\n\n_（学到什么、卡在哪里、参考了哪些资料）_\n`
    );
    count++;
  });
});

/* ---------- 工具：每个工具一个文件 ---------- */
const usedT = new Set();
D.tools.forEach((t) => {
  let slug = slugify(t.name);
  while (usedT.has(slug)) slug += '-2';
  usedT.add(slug);

  write(path.join(DOCS, 'tools', slug + '.md'),
    fm({ title: t.name, category: t.cat, score: t.score, price: t.price, url: t.url }) +
    `# ${t.name}\n\n` +
    `**一句话**：${t.use}\n\n` +
    `- 分类：${t.cat}\n` +
    `- 价格：${t.price}\n` +
    `- 评分：${'★'.repeat(t.score)}${'☆'.repeat(5 - t.score)}\n\n` +
    `## 优点\n\n${t.pros}\n\n` +
    `## 缺点\n\n${t.cons}\n\n` +
    `## 我的使用记录\n\n_（什么时候用过、效果如何、有没有平替）_\n\n` +
    `[打开官网](${t.url})\n`
  );
  count++;
});

/* ---------- 热点：每条一个文件 ---------- */
D.news.forEach((n, i) => {
  const nn = String(i + 1).padStart(2, '0');
  write(path.join(DOCS, 'news', `${n.date}-${nn}.md`),
    fm({ title: n.title, date: n.date, source: n.source, tag: n.tag, url: n.url }) +
    `# ${n.title}\n\n` +
    `${n.summary}\n\n` +
    `> ${n.source} · ${n.date}\n\n` +
    (n.url ? `[阅读原文](${n.url})\n` : '')
  );
  count++;
});

console.log('导出完成，共生成 ' + count + ' 个 Markdown 文件 → docs/');
