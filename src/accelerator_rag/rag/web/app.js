'use strict';
// Accelerator knowledge workbench: Q&A, exact table lookup and the library
// share one evidence/reader panel.  Model and catalog text is always inserted
// as text nodes (or through markdown-it with html:false); never as raw HTML.
const $ = (id) => document.getElementById(id);
const MAX_SCOPE = 32;
const HISTORY_KEY = 'accelerator-rag.history.v2';
const usageLabels = {current:'现行', reference:'参考', pending_review:'待核实', historical:'历史', unknown:'状态未知'};
const kindLabels = {overall_design:'总体设计', subsystem_design:'分系统设计', standard_specification:'标准规范', interface_specification:'接口说明', operation_manual:'操作手册', installation_maintenance:'安装维护', test_plan:'测试大纲', test_report:'测试报告', acceptance_report:'验收报告', development_summary:'研制总结', review_opinion:'评审意见', meeting_record:'会议记录', paper:'论文', configuration_snapshot:'配置表', structured_list:'结构化清单', drawing:'图纸'};
const categoryLabels = {accelerator:'加速器', accelerator_physics:'加速器物理', beam_diagnostics:'束流诊断', control_system:'控制系统', 'control-system':'控制系统', epics:'EPICS', documentation:'技术文档', high_level_application:'高层应用'};
const topicLabels = {network:'网络', timing:'定时', interlock:'联锁', vacuum:'真空', laser:'激光', archiver:'存档', data_storage:'数据存储', pdu:'PDU', power_supply:'电源', cryogenics:'低温/恒温', acceptance:'验收', design:'设计', gui:'界面', ioc:'IOC', epics:'EPICS', cybersecurity:'网络安全', motion_control:'运动控制', alarm:'报警', database:'数据库', installation:'安装', standards:'规范', review:'评审', documentation:'文档'};
const locatorLabels = {page:'物理页', section:'章节索引', paragraph:'段落', slide:'幻灯片', cell_range:'单元格'};
const statusLabels = {answered:'已找到完整依据', partial:'部分资料可确认', insufficient:'当前资料无法确认'};
const statusNotes = {
  answered: '点击引用编号，可在右栏核对原文。',
  partial: '已回答有依据的部分；未确认的内容在答案末尾和“需求覆盖”中列出。',
  insufficient: '当前资料不能确认所问事实。可补充设备、机柜、时间范围或文档版本后重试。'
};
const views = {
  ask: {title:'文档问答', subtitle:'回答只引用可定位的原文'},
  lookup: {title:'表格查询', subtitle:'线缆、端口与端子表的精确行匹配'},
  library: {title:'资料库', subtitle:'资料状态、版本与阅读方式'}
};

let view = 'ask';
let busy = false;
let current = null;
let readerModule = null;
let scope = [];               // [{document_id, title, usage, version}]
let catalog = {documents: [], families: []};
let catalogLoaded = null;
const selection = new Map();  // document_id -> catalog row
let history = loadHistory();

function el(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined && text !== null && text !== '') node.textContent = text;
  if (className) node.className = className;
  return node;
}
function button(text, className, onClick, label) {
  const node = el('button', text, className);
  node.type = 'button';
  if (label) node.setAttribute('aria-label', label);
  if (onClick) node.addEventListener('click', onClick);
  return node;
}
function versionText(value, title) {
  const text = (value || '').trim();
  if (!text || text === 'unknown' || text.startsWith('batch-') || (title && text.includes(title))) return '';
  return text;
}
function primaryUsage(row) {
  return (row.usage_statuses || []).find(v => v && v !== 'unknown') || 'unknown';
}
function defaultQueryable(usage) { return usage === 'current' || usage === 'reference' || usage === 'unknown'; }
function locatorText(citation) {
  const kind = citation.locator_kind || 'page';
  const label = citation.position_label || `${citation.page_start}${citation.page_start === citation.page_end ? '' : `～${citation.page_end}`}`;
  return `${locatorLabels[kind] || kind} ${label}`;
}

// ---------- persistence (per-viewer convenience only) ----------
function loadHistory() {
  try {
    const parsed = JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]');
    return Array.isArray(parsed) ? parsed.slice(0, 40) : [];
  } catch { return []; }
}
function saveHistory() {
  try { localStorage.setItem(HISTORY_KEY, JSON.stringify(history.slice(0, 40))); } catch { /* storage unavailable */ }
}
function remember(entry) {
  history = [entry, ...history.filter(item => !(item.kind === entry.kind && item.question === entry.question))].slice(0, 40);
  saveHistory(); renderHistory();
}

// ---------- views ----------
function setView(name) {
  view = name;
  for (const key of Object.keys(views)) $(`view-${key}`).hidden = key !== name;
  document.querySelectorAll('.rail-link').forEach(link => {
    const active = link.dataset.view === name;
    link.classList.toggle('active', active);
    if (active) link.setAttribute('aria-current', 'page'); else link.removeAttribute('aria-current');
  });
  $('page-title').textContent = views[name].title;
  $('page-subtitle').textContent = views[name].subtitle;
  closeRail();
  if (name !== 'ask') ensureCatalog();
  if (name === 'lookup') setTimeout(() => $('lookup-query').focus(), 0);
}
function closeRail() { $('rail').classList.remove('open'); $('rail-toggle').setAttribute('aria-expanded', 'false'); }
document.querySelectorAll('.rail-link').forEach(link => link.addEventListener('click', () => setView(link.dataset.view)));
$('rail-toggle').addEventListener('click', () => {
  const open = $('rail').classList.toggle('open');
  $('rail-toggle').setAttribute('aria-expanded', String(open));
});
document.addEventListener('keydown', event => { if (event.key === 'Escape') closeRail(); });

// ---------- reader / evidence panel ----------
function closeReader() { readerModule?.closeReader(false); }
async function openSource(citation, trigger, options) {
  if (!citation.document_url) {
    $('source-hint').textContent = '该格式暂无正文阅读页；可下载原件核对。';
    return;
  }
  try {
    readerModule ||= await import('/assets/pdf-reader.js?v=20261105a');
    await readerModule.openReader(citation, trigger, options);
  } catch { $('source-hint').textContent = '阅读器加载失败，请检查连接后重试。'; }
}
function resetSources(hint) {
  closeReader();
  $('sources').replaceChildren();
  $('source-empty').hidden = false;
  $('source-empty-title').textContent = '答案有据可查';
  $('source-empty-note').textContent = '点击答案中的引用编号，在这里对照原文。';
  $('source-count').textContent = '0';
  $('source-hint').textContent = hint || '提问后，引用的文档和位置会显示在这里；点击可在本栏阅读原文。';
}
function renderMath(node) {
  if (window.renderMathInElement) window.renderMathInElement(node, {
    delimiters: [{left:'\\(', right:'\\)', display:false}, {left:'\\[', right:'\\]', display:true}, {left:'$$', right:'$$', display:true}],
    throwOnError:false, trust:false, strict:'warn'
  });
}
function inlineText(container, text, citations) {
  text = text.replace(/([≤≥])\s*(\d+(?:\.\d+)?)\s*(us|µs|μs|ms|ns|ps)\b/g, (_, op, value, unit) =>
    `\\(${op === '≤' ? '\\leq' : '\\geq'} ${value}\\,\\mathrm{${['us', 'µs', 'μs'].includes(unit) ? '\\mu s' : unit}}\\)`);
  for (const part of text.split(/(\[\d+\]|`[^`\n]+`)/g)) {
    const match = part.match(/^\[(\d+)\]$/);
    const citation = match && citations.find(c => c.number === Number(match[1]));
    if (citation) {
      const cite = button(part, 'cite', () => openSource(citation, cite), `查看来源 ${citation.number}`);
      cite.title = `${citation.document_title} · ${locatorText(citation)}`;
      container.append(cite);
    } else if (part.startsWith('`') && part.endsWith('`') && part.length > 1) {
      container.append(el('code', part.slice(1, -1)));
    } else {
      for (const fragment of part.split(/(\*\*[^*]+\*\*)/g)) {
        container.append(fragment.startsWith('**') && fragment.endsWith('**') && fragment.length > 4
          ? el('strong', fragment.slice(2, -2)) : document.createTextNode(fragment));
      }
    }
  }
}
function renderCitations(citations) {
  $('sources').replaceChildren();
  $('source-count').textContent = `${citations.length}`;
  $('source-empty').hidden = citations.length > 0;
  $('source-empty-title').textContent = citations.length ? '答案有据可查' : '本次没有可引用的证据';
  $('source-empty-note').textContent = citations.length ? '点击引用，在这里对照原文。' : '可补充设备名称、问题范围或文档版本后重试。';
  $('source-hint').textContent = citations.length
    ? '位置按修订版标示：PDF 物理页、Markdown 章节、DOCX 段落、PPTX 幻灯片、表格单元格范围。'
    : '本次没有足够依据，因此未附上无关文档。';
  for (const c of citations) {
    const item = el('li', '', 'source');
    item.id = `source-${c.number}`;
    const head = el('div', '', 'source-head');
    head.append(el('span', `[${c.number}]`, 'source-number'), el('h3', c.document_title));
    item.append(head, el('p', locatorText(c), 'source-locator'));
    const meta = [];
    const version = versionText(c.document_version, c.document_title);
    if (version) meta.push(version);
    if (c.usage_status) meta.push(usageLabels[c.usage_status] || c.usage_status);
    if (c.document_kind) meta.push(kindLabels[c.document_kind] || c.document_kind);
    if (c.content_role === 'note') meta.push('演讲者备注');
    if (c.review_status === 'required') meta.push('OCR 待复核');
    if (c.formula_status === 'unresolved') meta.push('公式未恢复');
    if (meta.length) item.append(el('p', meta.join(' · '), 'source-meta'));
    if (c.usage_status === 'pending_review' || c.usage_status === 'historical') item.classList.add('source-flagged');
    if (c.quote) { const quote = el('blockquote', '', 'source-quote'); inlineText(quote, c.quote, []); item.append(quote); }
    if (/^\/v1\/rag\/documents\/[a-zA-Z0-9_-]+$/.test(c.document_url || '')) {
      const open = button('阅读原文 →', 'link-button', () => openSource(c, open), `阅读来源 ${c.number} 的原文，${locatorText(c)}`);
      item.append(open);
    }
    $('sources').append(item);
  }
  renderMath($('sources'));
}

// ---------- Q&A ----------
function showResult(entry) {
  const {data, question} = entry;
  if (!Object.hasOwn(statusLabels, data.status) || typeof data.answer !== 'string' || !Array.isArray(data.citations)) throw new Error('BAD_RESPONSE');
  closeReader();
  current = entry;
  $('workspace').classList.add('has-result');
  $('welcome').hidden = true; $('error').hidden = true;
  $('conversation-scroll').scrollTop = 0;
  $('asked').textContent = question;
  $('result-scope').hidden = !entry.scope?.length;
  $('result-scope').textContent = entry.scope?.length ? `范围：${entry.scope.map(s => s.title).join('；')}` : '';
  $('status').textContent = statusLabels[data.status];
  $('status').className = `status ${data.status}`;
  $('status-note').textContent = statusNotes[data.status];
  const math = [];
  const protectedAnswer = data.answer.replace(/\\\([\s\S]*?\\\)|\\\[[\s\S]*?\\\]|\$\$[\s\S]*?\$\$/g, text => {
    const token = `RAGMATHPLACEHOLDER${math.length}END`; math.push(text); return token;
  });
  const answer = $('answer');
  answer.replaceChildren();
  if (window.markdownit) {
    answer.innerHTML = window.markdownit({html:false, breaks:true, linkify:false, typographer:false}).render(protectedAnswer);
  } else {
    answer.append(el('p', protectedAnswer));
  }
  const walker = document.createTreeWalker(answer, NodeFilter.SHOW_TEXT);
  const nodes = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);
  for (const node of nodes) {
    if (node.parentElement.closest('code,pre')) continue;
    const content = node.textContent.replace(/RAGMATHPLACEHOLDER(\d+)END/g, (_, i) => math[Number(i)] || '');
    const fragment = document.createDocumentFragment(); inlineText(fragment, content, data.citations); node.replaceWith(fragment);
  }
  renderMath(answer);
  renderCoverage(data.requirements || []);
  const seconds = data.latency?.total_seconds;
  $('elapsed').textContent = Number.isFinite(seconds) ? `已查阅资料 · ${seconds.toFixed(1)} 秒` : '查询完成';
  $('copy').textContent = '复制答案与出处';
  renderCitations(data.citations);
  $('result').hidden = false;
  renderHistory();
}
function renderCoverage(requirements) {
  const list = $('coverage-list');
  list.replaceChildren();
  $('coverage').hidden = requirements.length < 1;
  if (!requirements.length) return;
  const complete = requirements.filter(r => r.coverage === 'complete' || r.supported).length;
  $('coverage-summary').textContent = `${complete} / ${requirements.length} 项完整`;
  $('coverage').open = complete < requirements.length;
  for (const r of requirements) {
    const coverage = r.coverage || (r.supported ? 'complete' : 'none');
    const item = el('li', '', `coverage-item ${coverage}`);
    item.append(el('span', {complete:'完整', partial:'部分', none:'缺依据'}[coverage] || coverage, 'coverage-tag'));
    item.append(el('span', r.text || r.id, 'coverage-text'));
    if (!r.supported && r.missing) item.append(el('p', r.missing, 'coverage-missing'));
    list.append(item);
  }
}
async function ask(event) {
  event?.preventDefault();
  const question = $('question').value.trim();
  if (busy || !question) { if (!question) $('question').focus(); return; }
  busy = true; current = null;
  setView('ask');
  $('workspace').classList.remove('has-result');
  $('submit').disabled = true; $('question').readOnly = true;
  $('result').hidden = true; $('welcome').hidden = true; $('error').hidden = true;
  $('progress').hidden = false; $('ask-form').setAttribute('aria-busy', 'true');
  resetSources();
  const phases = ['正在拆解问题并检索资料…', '正在核对证据与适用范围…', '正在整理回答与引用…'];
  let phase = 0;
  $('progress-message').textContent = phases[0];
  const phaseTimer = setInterval(() => { phase = Math.min(phase + 1, phases.length - 1); $('progress-message').textContent = phases[phase]; }, 4000);
  const slow = setTimeout(() => { $('progress-message').textContent = '这次查询耗时较长（可能在补充检索），请保持页面打开。'; }, 25000);
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 180000);
  const usedScope = scope.slice();
  try {
    const payload = {query: question};
    if (usedScope.length) payload.scope = {mode: 'version', revision_ids: usedScope.map(s => s.document_id)};
    const response = await fetch('/v1/rag/answer', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload), signal:controller.signal});
    if (!response.ok) {
      const failure = await response.json().catch(() => ({}));
      const code = failure.detail?.code;
      throw new Error(code === 'INVALID_GROUNDED_ANSWER' ? 'UNVERIFIED' : code === 'AUTH' ? 'AUTH' : code === 'RATE_LIMIT' ? 'RATE_LIMIT' : response.status === 422 ? 'INPUT' : 'SERVICE');
    }
    const data = await response.json();
    const entry = {kind:'ask', question, data, scope: usedScope, at: Date.now()};
    remember(entry);
    showResult(entry);
  } catch (error) {
    const messages = {
      AUTH: '模型服务认证失败，暂时无法生成回答。请联系管理员检查服务凭据，问题已保留。',
      RATE_LIMIT: '模型服务当前繁忙，请稍后重试，问题已保留。',
      UNVERIFIED: '本次回答未通过证据或引用校验，系统没有展示该回答。请重试，或拆成更具体的单个问题。',
      INPUT: '问题或查阅范围未通过输入检查。请输入 1～8000 个字符；范围最多 32 份资料。',
      SERVICE: '问答服务暂时不可用。问题已保留，请稍后重试。',
      BAD_RESPONSE: '服务返回的结果不完整。问题已保留，请稍后重试。'
    };
    $('error').textContent = error.name === 'AbortError' ? '等待回答超时。问题已保留，请稍后重试。' : messages[error.message] || '暂时无法连接问答服务。请检查连接后重试，问题已保留。';
    $('error').hidden = false;
  } finally {
    clearInterval(phaseTimer); clearTimeout(slow); clearTimeout(timeout);
    $('progress').hidden = true; $('submit').disabled = false; $('question').readOnly = false;
    $('ask-form').removeAttribute('aria-busy');
    busy = false;
  }
}
$('ask-form').addEventListener('submit', ask);
$('question').addEventListener('keydown', event => {
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) { event.preventDefault(); $('ask-form').requestSubmit(); }
});
$('examples').addEventListener('click', event => {
  const target = event.target.closest('[data-question]');
  if (target) { $('question').value = target.dataset.question; $('question').focus(); }
});
$('copy').addEventListener('click', async () => {
  if (!current) return;
  const {data, question} = current;
  const sources = data.citations.map(c => `[${c.number}] ${c.document_title}；版本 ${c.document_version}；${locatorText(c)}`).join('\n');
  try {
    await navigator.clipboard.writeText(`${question}\n\n${statusLabels[data.status]}\n${data.answer}\n\n${sources}`);
    $('copy').textContent = '已复制';
  } catch { $('copy').textContent = '请选中答案后手动复制'; }
});
$('new-session').addEventListener('click', () => {
  if (busy) return;
  setView('ask'); closeReader(); current = null;
  $('workspace').classList.remove('has-result');
  $('result').hidden = true; $('error').hidden = true; $('welcome').hidden = false;
  $('question').value = ''; setScope([]); resetSources(); renderHistory(); $('question').focus();
});

// ---------- scope ----------
function setScope(items) {
  scope = items.slice(0, MAX_SCOPE);
  const chips = $('scope-chips');
  chips.replaceChildren();
  $('scope-bar').hidden = !scope.length;
  for (const item of scope) {
    const chip = el('span', '', `scope-chip usage-${item.usage}`);
    const version = item.version ? `（${item.version}）` : '';
    chip.append(el('span', `${item.title}${version}`), el('small', usageLabels[item.usage] || ''));
    chip.append(button('×', 'chip-remove', () => setScope(scope.filter(s => s.document_id !== item.document_id)), `移除 ${item.title}`));
    chips.append(chip);
  }
  const flagged = scope.filter(s => !defaultQueryable(s.usage));
  if (flagged.length && view === 'ask' && !current) {
    $('source-hint').textContent = '范围内含历史或待核实资料。回答会保留其状态，不能自动当作现行依据。';
  }
}
function scopeItem(row) {
  return {
    document_id: row.document_id,
    title: row.document_title,
    usage: primaryUsage(row),
    version: (row.versions || []).map(v => versionText(v, row.document_title)).find(Boolean) || ''
  };
}
$('scope-clear').addEventListener('click', () => setScope([]));

// ---------- history ----------
function renderHistory() {
  const list = $('history');
  list.replaceChildren();
  $('history-empty').hidden = history.length > 0;
  $('history-clear').hidden = !history.length;
  history.forEach(entry => {
    const active = (entry.kind === 'ask' && current?.question === entry.question && current?.at === entry.at);
    const item = button('', `history-item${active ? ' active' : ''}`, () => {
      if (busy) return;
      if (entry.kind === 'lookup') { setView('lookup'); $('lookup-query').value = entry.question; runLookup(); return; }
      setView('ask'); setScope(entry.scope || []);
      try { showResult(entry); } catch { /* stale entry */ }
    });
    item.title = entry.question;
    item.append(el('span', entry.kind === 'lookup' ? '表' : '问', `history-kind ${entry.kind}`), el('span', entry.question, 'history-text'));
    list.append(item);
  });
}
$('history-clear').addEventListener('click', () => { history = []; saveHistory(); renderHistory(); });

// ---------- catalog ----------
async function ensureCatalog(force = false) {
  if (catalogLoaded && !force) return catalogLoaded;
  catalogLoaded = (async () => {
    $('library-refresh').disabled = true;
    $('library-message').textContent = '正在读取已收录资料…';
    try {
      const response = await fetch('/v1/rag/documents', {signal:AbortSignal.timeout(15000), cache:'no-store'});
      if (!response.ok) throw new Error();
      const data = await response.json();
      if (!Array.isArray(data.documents)) throw new Error();
      catalog = data;
      $('library-count').textContent = String(data.document_count ?? data.documents.length);
      const defaults = data.documents.filter(d => defaultQueryable(primaryUsage(d))).length;
      $('library-summary').textContent = `${data.document_count} 份修订 · ${(data.indexed_section_count || 0).toLocaleString()} 段可检索内容 · 默认可问 ${defaults} 份`;
      fillFilters();
      fillLookupDocuments();
      renderLibrary();
    } catch {
      catalogLoaded = null;
      $('library-message').textContent = '目录暂时无法加载，请点击“刷新目录”重试。';
      $('library-summary').textContent = '知识库目录暂不可用';
    } finally { $('library-refresh').disabled = false; }
  })();
  return catalogLoaded;
}
function fillSelect(select, values, label, format) {
  const previous = select.value;
  select.replaceChildren(new Option(label, ''));
  values.forEach(v => select.append(new Option(format(v), v)));
  if (values.includes(previous)) select.value = previous;
}
function fillFilters() {
  const docs = catalog.documents;
  fillSelect($('library-category'), [...new Set(docs.flatMap(d => d.categories || []))].sort(), '全部分类', v => categoryLabels[v] || v);
  fillSelect($('library-format'), [...new Set(docs.map(d => d.document_format).filter(Boolean))].sort(), '全部格式', v => v.toUpperCase());
  fillSelect($('library-status'), [...new Set(docs.flatMap(d => d.usage_statuses || []).filter(v => v && v !== 'unknown'))], '全部状态', v => usageLabels[v] || v);
}
function fillLookupDocuments() {
  const tables = catalog.documents.filter(d => ['xlsx', 'xls', 'csv'].includes(d.document_format));
  const select = $('lookup-document');
  const previous = select.value;
  select.replaceChildren(new Option(`全部表格资料（${tables.length}）`, ''));
  tables.sort((a, b) => a.document_title.localeCompare(b.document_title, 'zh'))
    .forEach(d => select.append(new Option(d.document_title, d.document_id)));
  if (tables.some(d => d.document_id === previous)) select.value = previous;
}
function groupKey(d) {
  const topic = (d.topics || [])[0] || '';
  const category = (d.categories || [])[0] || 'other';
  return `${category}::${topic}`;
}
function renderLibrary() {
  const query = $('library-search').value.trim().toLocaleLowerCase();
  const category = $('library-category').value;
  const format = $('library-format').value;
  const status = $('library-status').value;
  const docs = catalog.documents.filter(d =>
    (!category || (d.categories || []).includes(category)) &&
    (!format || d.document_format === format) &&
    (!status || (d.usage_statuses || []).includes(status)) &&
    [d.document_title, ...(d.versions || []), ...(d.categories || []), ...(d.topics || []), ...(d.tags || [])].join(' ').toLocaleLowerCase().includes(query));
  const container = $('library-groups');
  container.replaceChildren();
  $('library-message').textContent = catalog.documents.length
    ? (docs.length ? `显示 ${docs.length} / ${catalog.documents.length} 份` : '未找到匹配的资料。试着缩短关键词或切换筛选。')
    : '当前服务尚未收录资料。';
  const groups = new Map();
  for (const d of docs) {
    const key = groupKey(d);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(d);
  }
  const ordered = [...groups.entries()].sort((a, b) => b[1].length - a[1].length);
  for (const [key, rows] of ordered) {
    const [cat, topic] = key.split('::');
    const group = el('details', '', 'library-group');
    group.open = ordered.length <= 4 || Boolean(query) || rows.some(r => selection.has(r.document_id));
    const summary = el('summary');
    summary.append(el('strong', `${categoryLabels[cat] || cat}${topic ? ` · ${topicLabels[topic] || topic}` : ''}`), el('span', `${rows.length} 份`, 'group-count'));
    group.append(summary);
    const list = el('ul', '', 'doc-list');
    rows.sort((a, b) => a.document_title.localeCompare(b.document_title, 'zh'));
    for (const d of rows) list.append(documentRow(d));
    group.append(list);
    container.append(group);
  }
  renderSelection();
}
function documentRow(d) {
  const usage = primaryUsage(d);
  const row = el('li', '', `doc-row usage-${usage}`);
  const pick = document.createElement('input');
  pick.type = 'checkbox'; pick.checked = selection.has(d.document_id);
  pick.setAttribute('aria-label', `选择 ${d.document_title} 作为查阅范围`);
  pick.addEventListener('change', () => {
    if (pick.checked) {
      if (selection.size >= MAX_SCOPE) { pick.checked = false; $('library-message').textContent = `一次最多选择 ${MAX_SCOPE} 份资料。`; return; }
      selection.set(d.document_id, d);
    } else selection.delete(d.document_id);
    renderSelection();
  });
  const body = el('div', '', 'doc-body');
  const title = el('div', '', 'doc-title');
  title.append(el('span', (d.document_format || '?').toUpperCase(), `format format-${d.document_format}`), el('strong', d.document_title));
  body.append(title);
  const facts = [];
  const versions = (d.versions || []).map(v => versionText(v, d.document_title)).filter(Boolean);
  if (versions.length) facts.push(versions.join('；'));
  facts.push(usageLabels[usage] || usage);
  const kinds = (d.document_kinds || []).filter(v => v && v !== 'unknown').map(k => kindLabels[k] || k);
  if (kinds.length) facts.push(kinds[0]);
  facts.push(`${(d.indexed_section_count || 0).toLocaleString()} 段`);
  if (!defaultQueryable(usage)) facts.push('需选定范围');
  body.append(el('p', facts.join(' · '), 'doc-facts'));
  const actions = el('div', '', 'doc-actions');
  if (d.document_url && d.reader_available !== false) {
    const read = button('阅读', 'link-button', () => openSource({document_url:d.document_url, document_title:d.document_title, document_format:d.document_format, document_version:versions.join('；') || 'unknown', page_start:1}, read), `阅读 ${d.document_title}`);
    actions.append(read);
  }
  if (d.download_url) { const link = el('a', '原件', 'link-button'); link.href = d.download_url; link.download = ''; actions.append(link); }
  actions.append(button('就此提问', 'link-button strong', () => { setScope([scopeItem(d)]); setView('ask'); $('question').focus(); }, `在 ${d.document_title} 中提问`));
  row.append(pick, body, actions);
  return row;
}
function renderSelection() {
  $('selection-bar').hidden = selection.size === 0;
  const flagged = [...selection.values()].filter(d => !defaultQueryable(primaryUsage(d))).length;
  $('selection-count').textContent = `已选 ${selection.size} 份${flagged ? `（含 ${flagged} 份历史/待核实）` : ''}`;
}
$('selection-clear').addEventListener('click', () => { selection.clear(); renderLibrary(); });
$('selection-ask').addEventListener('click', () => {
  setScope([...selection.values()].map(scopeItem));
  selection.clear(); renderLibrary();
  setView('ask'); $('question').focus();
});
for (const id of ['library-search']) $(id).addEventListener('input', renderLibrary);
for (const id of ['library-category', 'library-format', 'library-status']) $(id).addEventListener('change', renderLibrary);
$('library-refresh').addEventListener('click', () => ensureCatalog(true));

// ---------- table lookup ----------
let lookupRequest = 0;
async function runLookup(event) {
  event?.preventDefault();
  const query = $('lookup-query').value.trim();
  if (!query) { $('lookup-query').focus(); return; }
  const request = ++lookupRequest;
  const params = new URLSearchParams({q: query, limit: '60'});
  if ($('lookup-document').value) params.append('document_id', $('lookup-document').value);
  $('lookup-message').textContent = '正在匹配表格行…';
  $('lookup-results').replaceChildren();
  try {
    const response = await fetch(`/v1/rag/structured/lookup?${params}`, {signal:AbortSignal.timeout(15000)});
    if (!response.ok) throw new Error(response.status === 422 ? 'INPUT' : 'SERVICE');
    const data = await response.json();
    if (request !== lookupRequest) return;
    remember({kind:'lookup', question: query, at: Date.now()});
    renderLookup(data, query);
  } catch (error) {
    if (request !== lookupRequest) return;
    $('lookup-message').textContent = error.message === 'INPUT' ? '查询条件为空或过长（最多 500 字）。' : '表格查询暂时不可用，请稍后重试。';
  }
}
function renderLookup(data, query) {
  const hits = Array.isArray(data.hits) ? data.hits : [];
  const container = $('lookup-results');
  container.replaceChildren();
  if (!hits.length) {
    $('lookup-message').textContent = '没有完全匹配的表格行。请检查编号写法（如 FEL2-CN01、UN-LTU1:PS-01、DEVSW001），或改用“文档问答”。';
    return;
  }
  const near = hits.filter(h => h.near_best);
  const rest = hits.filter(h => !h.near_best);
  const unmatched = data.unmatched_identifiers || [];
  $('lookup-message').textContent = unmatched.length
    ? `表格中没有 ${unmatched.join('、')}；下列 ${rest.length} 行只满足其余条件，不能当作所问对象的记录。`
    : `最佳匹配 ${near.length} 行${rest.length ? `，另有 ${rest.length} 行只满足部分条件` : ''}。行内容来自表格原文，未经模型改写。`;
  const section = (title, items, collapsed) => {
    const wrap = el(collapsed ? 'details' : 'section', '', 'lookup-section');
    if (collapsed) wrap.append(el('summary', title)); else wrap.append(el('h3', title));
    const byDoc = new Map();
    for (const hit of items) {
      if (!byDoc.has(hit.revision_id)) byDoc.set(hit.revision_id, []);
      byDoc.get(hit.revision_id).push(hit);
    }
    for (const [revision, rows] of byDoc) {
      const card = el('article', '', 'lookup-card');
      const head = el('header', '', 'lookup-card-head');
      head.append(el('span', (rows[0].document_format || '').toUpperCase(), `format format-${rows[0].document_format}`), el('strong', rows[0].document_title));
      const usage = (rows[0].usage_statuses || []).find(v => v && v !== 'unknown');
      if (usage) head.append(el('span', usageLabels[usage] || usage, `pill usage-${usage}`));
      head.append(button('就此提问', 'link-button strong', () => {
        const row = catalog.documents.find(d => d.document_id === revision);
        setScope([row ? scopeItem(row) : {document_id: revision, title: rows[0].document_title, usage: usage || 'unknown', version: ''}]);
        $('question').value = query; setView('ask'); $('question').focus();
      }, `在 ${rows[0].document_title} 中就该条件提问`));
      card.append(head);
      for (const hit of rows) card.append(lookupRow(hit));
      wrap.append(card);
    }
    return wrap;
  };
  if (near.length) container.append(section('最佳匹配', near, false));
  if (rest.length) container.append(section(`部分匹配（${rest.length}）`, rest, true));
}
function lookupRow(hit) {
  const row = el('div', '', 'lookup-row');
  const meta = el('div', '', 'lookup-row-meta');
  meta.append(el('span', hit.location, 'lookup-location'));
  for (const term of hit.matched || []) meta.append(el('span', term, 'match-chip'));
  const open = button('定位原表 →', 'link-button', () => openSource({
    document_url: hit.document_url, document_title: hit.document_title, document_format: hit.document_format,
    document_version: 'unknown', page_start: 1, anchor_block_id: hit.table_block_id, row_number: hit.row_number,
    position_label: hit.location
  }, open), `在原表中定位 ${hit.location}`);
  meta.append(open);
  const grid = el('dl', '', 'lookup-fields');
  for (const field of hit.fields || []) {
    const wrap = el('div', '', field.column === '_group' ? 'field group' : 'field');
    wrap.append(el('dt', field.header || field.column), el('dd', field.value));
    grid.append(wrap);
  }
  row.append(meta, grid);
  return row;
}
$('lookup-form').addEventListener('submit', runLookup);
$('lookup-examples').addEventListener('click', event => {
  const target = event.target.closest('[data-lookup]');
  if (target) { $('lookup-query').value = target.dataset.lookup; runLookup(); }
});

// ---------- service status ----------
async function health() {
  try {
    const response = await fetch('/health', {signal:AbortSignal.timeout(5000)});
    if (!response.ok) throw new Error();
    $('connection').textContent = '服务已连接'; $('connection').className = 'connection ready';
  } catch {
    $('connection').textContent = '服务暂未连接'; $('connection').className = 'connection offline';
  }
}
async function release() {
  try {
    const response = await fetch('/v1/rag/releases/current', {signal:AbortSignal.timeout(5000)});
    if (!response.ok) return;
    const data = await response.json();
    if (data.release_id && data.release_id !== 'unknown') $('release').textContent = data.release_id;
  } catch { /* optional */ }
}
health(); release(); setInterval(health, 30000);
renderHistory();
setScope([]);
ensureCatalog();
