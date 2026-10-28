'use strict';
const $ = (id) => document.getElementById(id);
let current = null;
let busy = false;
const history = [];
let readerModule;
function closeReader() { readerModule?.closeReader(false); }
async function openSource(citation, trigger) {
  try {
    readerModule ||= await import('/assets/pdf-reader.js');
    if (current?.data.citations.includes(citation)) await readerModule.openReader(citation, trigger);
  } catch { $('source-hint').textContent = '阅读器加载失败，请检查连接后重试。'; }
}
const statusLabels = {answered: '已找到完整依据', partial: '部分资料可确认', insufficient: '当前资料无法确认'};
const statusNotes = {
  answered: '点击引用编号，可直接核对原文。',
  partial: '已回答有依据的部分，未确认的内容列在下方。',
  insufficient: '当前文档不能确认所问事实。可补充设备名称、时间范围或文档版本后重试。'
};
function textElement(tag, text, className) {
  const el = document.createElement(tag);
  el.textContent = text;
  if (className) el.className = className;
  return el;
}
function resetSources() {
  closeReader();
  $('sources').replaceChildren();
  $('source-empty').hidden = false;
  $('source-empty-title').textContent = '答案有据可查';
  $('source-empty-note').textContent = '点击答案中的引用编号，在这里对照文档原文。';
  $('source-count').textContent = '0';
  $('source-hint').textContent = '提问后，在这里查看答案引用的文档和页码。点击答案中的编号可直接阅读引用页。';
}
function inlineText(container, text, citations) {
  // Model text always becomes text nodes; never interpret it as HTML.
  text = text.replace(/([≤≥])\s*(\d+(?:\.\d+)?)\s*(us|µs|μs|ms|ns|ps)\b/g, (_, op, value, unit) =>
    `\\(${op === '≤' ? '\\leq' : '\\geq'} ${value}\\,\\mathrm{${['us', 'µs', 'μs'].includes(unit) ? '\\mu s' : unit}}\\)`);
  for (const part of text.split(/(\[\d+\]|`[^`\n]+`)/g)) {
    const match = part.match(/^\[(\d+)\]$/);
    if (match && citations.some(c => c.number === Number(match[1]))) {
      const number = Number(match[1]);
      const button = textElement('button', part, 'cite');
      button.type = 'button'; button.setAttribute('aria-label', `查看来源 ${number}`);
      const citation = citations.find(c => c.number === number);
      button.title = `${citation.document_title} · PDF 第 ${citation.page_start} 页`;
      button.addEventListener('click', () => {
        openSource(citations.find(c => c.number === number), button);
      });
      container.append(button);
    } else if (part.startsWith('`') && part.endsWith('`')) {
      container.append(textElement('code', part.slice(1, -1)));
    } else {
      const fragments = part.split(/(\*\*[^*]+\*\*)/g);
      fragments.forEach(f => container.append(f.startsWith('**') && f.endsWith('**') ? textElement('strong', f.slice(2,-2)) : document.createTextNode(f)));
    }
  }
}
function showResult(data, question) {
  if (!Object.hasOwn(statusLabels, data.status) || typeof data.answer !== 'string' || !Array.isArray(data.citations)) throw new Error('BAD_RESPONSE');
  closeReader();
  current = {data, question};
  $('workspace').classList.add('has-result');
  $('welcome').hidden = true;
  $('error').hidden = true;
  renderHistory();
  $('conversation-scroll').scrollTop = 0;
  $('workspace').scrollTop = 0;
  $('asked').textContent = question;
  $('status').textContent = statusLabels[data.status];
  $('status').className = `status ${data.status}`;
  $('status-note').textContent = statusNotes[data.status];
  $('answer').replaceChildren();
  const math = [];
  const protectedAnswer = data.answer.replace(/\\\([\s\S]*?\\\)|\\\[[\s\S]*?\\\]|\$\$[\s\S]*?\$\$/g, text => {
    const token = `RAGMATHPLACEHOLDER${math.length}END`;
    math.push(text); return token;
  });
  // Raw HTML is disabled; model text is escaped before parsing citations.
  const md = window.markdownit({html:false, breaks:true, linkify:false, typographer:false});
  $('answer').innerHTML = md.render(protectedAnswer);
  const walker = document.createTreeWalker($('answer'), NodeFilter.SHOW_TEXT);
  const nodes = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);
  for (const node of nodes) {
    if (node.parentElement.closest('code,pre')) continue;
    const content = node.textContent.replace(/RAGMATHPLACEHOLDER(\d+)END/g, (_,i) => math[Number(i)] || '');
    const fragment = document.createDocumentFragment(); inlineText(fragment, content, data.citations); node.replaceWith(fragment);
  }
  if (window.renderMathInElement) window.renderMathInElement($('answer'), {
    delimiters: [{left: '\\(', right: '\\)', display: false}, {left: '\\[', right: '\\]', display: true}, {left: '$$', right: '$$', display: true}],
    throwOnError: false, trust: false, strict: 'warn'
  });
  const seconds = data.latency?.total_seconds;
  $('elapsed').textContent = Number.isFinite(seconds) ? `已查阅资料 · ${seconds.toFixed(1)} 秒` : '查询完成';
  $('source-count').textContent = `${data.citations.length} 条引用`;
  $('source-empty').hidden = data.citations.length > 0;
  $('source-empty-title').textContent = data.citations.length ? '答案有据可查' : '本次没有可引用的证据';
  $('source-empty-note').textContent = data.citations.length ? '点击引用，在这里对照文档原文。' : '可补充设备名称、问题范围或文档版本后重试。';
  $('source-hint').textContent = data.citations.length ? '页码指 PDF 文件中的物理页，可能与页脚印刷页码不同。' : '本次没有足够依据，因此未附上无关文档。';
  $('sources').replaceChildren();
  for (const c of data.citations) {
    const item = textElement('li', '', 'source');
    item.id = `source-${c.number}`; item.tabIndex = -1;
    item.append(textElement('span', `[${c.number}]`, 'source-number'));
    item.append(textElement('h3', c.document_title));
    const page = c.page_start === c.page_end ? `${c.page_start}` : `${c.page_start}～${c.page_end}`;
    item.append(textElement('p', `物理页 ${page}`, 'page'));
    item.append(textElement('p', `版本：${c.document_version === 'unknown' ? '文档未标明' : c.document_version}`));
    if (/^\/v1\/rag\/documents\/[a-zA-Z0-9_-]+$/.test(c.document_url || '')) {
      const link = textElement('button', '阅读原文 →', 'pdf-link');
      link.type = 'button';
      link.setAttribute('aria-label', `阅读来源 ${c.number} 的 PDF 原文，第 ${c.page_start} 页`);
      link.addEventListener('click', () => openSource(c, link));
      item.append(link);
    }
    if (c.quote) {const quote = textElement('blockquote', '', 'source-quote'); inlineText(quote, c.quote, []); item.append(quote);}
    $('sources').append(item);
  }
  if (window.renderMathInElement) window.renderMathInElement($('sources'), {delimiters:[{left:'\\(',right:'\\)',display:false},{left:'\\[',right:'\\]',display:true}],throwOnError:false,trust:false});
  $('copy').textContent = '复制答案';
  $('result').hidden = false;
}
async function ask(event) {
  event.preventDefault();
  const question = $('question').value.trim();
  if (busy || !question) {if (!question) $('question').focus(); return;}
  busy = true; current = null;
  $('workspace').classList.remove('has-result');
  $('workspace').scrollTop = 0;
  $('sidebar').classList.remove('open');
  $('menu-toggle').setAttribute('aria-expanded', 'false');
  $('submit').disabled = true; $('question').readOnly = true;
  document.querySelectorAll('[data-question]').forEach(b => b.disabled = true);
  $('result').hidden = true; $('welcome').hidden = true; $('error').hidden = true;
  $('progress').hidden = false; $('ask-form').setAttribute('aria-busy', 'true');
  resetSources();
  $('progress-message').textContent = '正在检索证据并整理回答，请稍候…';
  const phases = ['正在检索相关资料…', '正在核对证据…', '正在整理回答…'];
  let phase = 0;
  $('progress-message').textContent = phases[phase];
  const phaseTimer = setInterval(() => {phase = Math.min(phase+1, phases.length-1); $('progress-message').textContent = phases[phase];}, 1400);
  const slow = setTimeout(() => $('progress-message').textContent = '这次查询耗时较长，仍在等待服务返回。请保持页面打开。', 12000);
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 180000);
  try {
    const response = await fetch('/v1/rag/answer', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({query: question}), signal: controller.signal});
    if (!response.ok) {
      const failure = await response.json().catch(() => ({}));
      const code = failure.detail?.code;
      throw new Error(code === 'INVALID_GROUNDED_ANSWER' ? 'UNVERIFIED' : code === 'AUTH' ? 'AUTH' : code === 'RATE_LIMIT' ? 'RATE_LIMIT' : response.status === 422 ? 'INPUT' : 'SERVICE');
    }
    const data = await response.json();
    history.push({data, question});
    renderHistory();
    showResult(data, question);
  } catch (error) {
    const messages = {
      AUTH: '模型服务认证失败，暂时无法生成回答。请联系管理员检查服务凭据，问题已保留。',
      RATE_LIMIT: '模型服务当前繁忙，请稍后重试，问题已保留。',
      UNVERIFIED: '本次回答未通过证据或引用校验，系统没有展示该回答。请重试，或将问题拆成更具体的单个问题。',
      INPUT: '问题未通过输入检查。请输入 1～8000 个字符，并明确要查询的内容。',
      SERVICE: '问答服务暂时不可用。问题已保留，请稍后点击“查找答案”重试。',
      BAD_RESPONSE: '服务返回的结果不完整。问题已保留，请稍后重试。'
    };
    $('error').textContent = error.name === 'AbortError' ? '等待回答超时。问题已保留，请稍后重试。' : messages[error.message] || '暂时无法连接问答服务。请检查服务连接后重试，问题已保留。';
    $('error').hidden = false;
  } finally {
    clearInterval(phaseTimer); clearTimeout(slow); clearTimeout(timeout);
    $('progress').hidden = true; $('submit').disabled = false; $('question').readOnly = false;
    $('ask-form').removeAttribute('aria-busy');
    document.querySelectorAll('[data-question]').forEach(b => b.disabled = false);
    busy = false;
  }
}
$('ask-form').addEventListener('submit', ask);
$('question').addEventListener('keydown', event => {
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) { event.preventDefault(); $('ask-form').requestSubmit(); }
});
document.querySelectorAll('[data-question]').forEach(button => button.addEventListener('click', () => {
  $('question').value = button.dataset.question; $('question').focus();
}));
$('copy').addEventListener('click', async () => {
  if (!current) return;
  const {data, question} = current;
  const sources = data.citations.map(c => `[${c.number}] ${c.document_title}；版本 ${c.document_version}；物理页 ${c.page_start}～${c.page_end}`).join('\n');
  try {
    await navigator.clipboard.writeText(`${question}\n\n${statusLabels[data.status]}\n${data.answer}\n\n${sources}`);
    $('copy').textContent = '已复制答案与出处';
  } catch { $('copy').textContent = '请选中答案后手动复制'; }
});
async function health() {
  try {
    const response = await fetch('/health', {signal: AbortSignal.timeout(5000)});
    if (!response.ok) throw new Error();
    $('connection').textContent = '文档服务已连接'; $('connection').className = 'connection ready';
  } catch {
    $('connection').textContent = '服务暂未连接'; $('connection').className = 'connection offline';
  }
}
health(); setInterval(health, 30000);

function renderHistory() {
  $('history').replaceChildren();
  $('history-count').textContent = history.length;
  $('history-empty').hidden = history.length > 0;
  history.forEach((entry, i) => {
    const button = textElement('button', entry.question, 'history-item' + (current?.data === entry.data ? ' active' : ''));
    button.title = entry.question;
    button.replaceChildren(textElement('span', entry.question));
    button.setAttribute('aria-current', current?.data === entry.data ? 'true' : 'false');
    button.type = 'button'; button.addEventListener('click', () => {if (!busy) { showChatView(); showResult(entry.data, entry.question); $('sidebar').classList.remove('open'); $('menu-toggle').setAttribute('aria-expanded','false'); }});
    $('history').append(button);
  });
}
$('new-session').addEventListener('click', () => {
  if (busy) return;
  showChatView();
  closeReader(); current = null;
  $('workspace').classList.remove('has-result');
  $('workspace').scrollTop = 0;
  $('sidebar').classList.remove('open');
  $('menu-toggle').setAttribute('aria-expanded','false');
  $('result').hidden = true; $('error').hidden = true; $('welcome').hidden = false;
  $('question').value = ''; resetSources(); $('question').focus();
});

$('menu-toggle').addEventListener('click', () => {
  const open = $('sidebar').classList.toggle('open');
  $('menu-toggle').setAttribute('aria-expanded', String(open));
});
document.addEventListener('click', event => {
  if (!$('sidebar').contains(event.target) && !$('menu-toggle').contains(event.target)) {
    $('sidebar').classList.remove('open'); $('menu-toggle').setAttribute('aria-expanded','false');
  }
});
document.addEventListener('keydown', event => {
  if (event.key === 'Escape') { $('sidebar').classList.remove('open'); $('menu-toggle').setAttribute('aria-expanded','false'); }
});


// The catalog contains only public metadata from the live server's loaded indexes.
let catalogDocuments = [];
let catalogRequest = 0;
function hideSidebar() {
  $('sidebar').classList.remove('open');
  $('menu-toggle').setAttribute('aria-expanded', 'false');
}
function showChatView() {
  closeReader();
  $('library-view').hidden = true;
  $('workspace').hidden = false;
  $('page-title').textContent = '文档问答';
  $('open-library').classList.remove('active');
  hideSidebar();
}
function showLibraryView() {
  closeReader();
  $('workspace').hidden = true;
  $('library-view').hidden = false;
  $('page-title').textContent = '文档目录';
  $('open-library').classList.add('active');
  hideSidebar();
}
function categoryLabel(value) {
  return ({accelerator:'加速器', accelerator_physics:'加速器物理', beam_diagnostics:'束流诊断', control_system:'控制系统', 'control-system':'控制系统', epics:'EPICS', documentation:'技术文档'})[value] || value;
}
function renderCatalog() {
  const query = $('library-search').value.trim().toLocaleLowerCase();
  const category = $('library-category').value;
  const visible = catalogDocuments.filter(d =>
    (!category || d.categories.includes(category)) &&
    [d.document_title, ...d.versions, ...d.categories, ...d.topics].join(' ').toLocaleLowerCase().includes(query));
  $('library-documents').replaceChildren();
  $('library-message').textContent = catalogDocuments.length ? `显示 ${visible.length} / ${catalogDocuments.length} 份文档` : '当前服务尚未收录可检索文档。';
  if (catalogDocuments.length && !visible.length) $('library-message').textContent = '未找到匹配的文档。试着缩短关键词或切换分类。';
  for (const d of visible) {
    const card = textElement('article', '', 'library-document');
    const heading = textElement('div', '', 'library-card-heading');
    heading.append(textElement('span', 'PDF', 'document-format'));
    heading.append(textElement('span', '已收录 · 可检索', 'document-indexed'));
    card.append(heading, textElement('h2', d.document_title));
    const versions = d.versions.filter(v => v !== 'unknown');
    card.append(textElement('p', versions.length ? versions.join('；') : '文档未标明版本', 'document-version'));
    const tags = textElement('div', '', 'document-tags');
    d.categories.forEach(c => tags.append(textElement('span', categoryLabel(c))));
    card.append(tags);
    const facts = textElement('p', `${d.page_count ? `${d.page_count} 页` : '页数待确认'} · ${d.indexed_section_count.toLocaleString()} 段可检索内容`, 'document-facts');
    const bottom = textElement('div', '', 'library-card-bottom');
    const button = textElement('button', d.original_available ? '阅读原文 →' : '原文暂不可用', 'pdf-link');
    button.type = 'button'; button.disabled = !d.original_available;
    button.setAttribute('aria-label', `阅读 ${d.document_title} 的 PDF 原文`);
    button.addEventListener('click', async () => {
      try {
        readerModule ||= await import('/assets/pdf-reader.js');
        if ($('library-view').hidden) return;
        $('library-view').hidden = true; $('workspace').hidden = false;
        $('workspace').classList.add('expanded');
        await readerModule.openReader({document_url:d.document_url, document_title:d.document_title,
          document_version:versions.join('；') || 'unknown', page_start:1}, button,
          {backLabel:'← 知识库目录', onClose:showLibraryView});
      } catch {
        showLibraryView(); $('library-message').textContent = '原文阅读器加载失败，请检查连接后重试。';
      }
    });
    bottom.append(facts, button); card.append(bottom); $('library-documents').append(card);
  }
}
async function loadCatalog() {
  const request = ++catalogRequest;
  $('library-refresh').disabled = true;
  $('library-message').textContent = '正在读取已收录文档…';
  try {
    const response = await fetch('/v1/rag/documents', {signal:AbortSignal.timeout(15000), cache:'no-store'});
    if (!response.ok) throw new Error();
    const data = await response.json();
    if (request !== catalogRequest) return;
    if (!Array.isArray(data.documents)) throw new Error();
    catalogDocuments = data.documents;
    const previous = $('library-category').value;
    $('library-category').replaceChildren(new Option('全部分类', ''));
    const categories = [...new Set(catalogDocuments.flatMap(d => d.categories))].sort();
    categories.forEach(c => $('library-category').append(new Option(categoryLabel(c), c)));
    if (categories.includes(previous)) $('library-category').value = previous;
    $('library-summary').textContent = `${data.document_count} 份文档  /  ${data.indexed_section_count.toLocaleString()} 段已收录内容`;
    renderCatalog();
  } catch {
    if (request !== catalogRequest) return;
    $('library-message').textContent = '目录暂时无法加载，请点击“刷新目录”重试。';
    if (!catalogDocuments.length) $('library-summary').textContent = '知识库目录暂不可用';
  } finally { if (request === catalogRequest) $('library-refresh').disabled = false; }
}
for (const id of ['open-library', 'knowledge-nav']) $(id).addEventListener('click', () => { showLibraryView(); loadCatalog(); });
$('back-to-chat').addEventListener('click', showChatView);
$('library-refresh').addEventListener('click', loadCatalog);
$('library-search').addEventListener('input', renderCatalog);
$('library-category').addEventListener('change', renderCatalog);
