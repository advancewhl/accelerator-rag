'use strict';
const $ = (id) => document.getElementById(id);
const params = new URLSearchParams(location.search);
const match = location.pathname.match(/^\/v1\/rag\/documents\/([a-zA-Z0-9_-]+)\/view$/);
const documentId = match ? match[1] : '';
const usageLabels = {
  current: '现行资料', reference: '参考资料', pending_review: '待核实',
  historical: '历史资料', excluded: '已排除', unknown: '状态未知'
};
const kindLabels = {
  overall_design: '总体设计', subsystem_design: '分系统设计',
  standard_specification: '标准规范', interface_specification: '接口说明',
  operation_manual: '操作手册', installation_maintenance: '安装维护',
  test_plan: '测试大纲', test_report: '测试报告',
  acceptance_report: '验收报告', development_summary: '研制总结',
  review_opinion: '评审意见', meeting_record: '会议记录',
  paper: '论文', configuration_snapshot: '配置快照',
  structured_list: '结构化清单', drawing: '图纸'
};
function el(tag, text, className) {
  const node = document.createElement(tag);
  if (text) node.textContent = text;
  if (className) node.className = className;
  return node;
}
function notice(text, tone = 'info') {
  const box = $('office-notice');
  box.textContent = text;
  box.className = `office-notice ${tone}`;
  box.hidden = !text;
}
function statusText(document) {
  if (!document) return '';
  const usage = (document.usage_statuses || []).filter(v => v && v !== 'unknown');
  const kinds = (document.document_kinds || []).filter(v => v && v !== 'unknown');
  const parts = [];
  if (usage.length) parts.push(usage.map(v => usageLabels[v] || v).join('、'));
  if (kinds.length) parts.push(kinds.map(v => kindLabels[v] || v).join('、'));
  return parts.join(' · ');
}
function renderTable(table) {
  const wrapper = el('div', '', 'office-table-wrap');
  const node = document.createElement('table');
  const rows = table.rows || [];
  const headerRows = Number(table.header_rows || 0);
  const rowNumbers = table.row_numbers || [];
  for (let i = 0; i < rows.length; i += 1) {
    const tr = document.createElement('tr');
    if (rowNumbers[i]) tr.dataset.row = String(rowNumbers[i]);
    if (i >= headerRows && rowNumbers[i]) tr.title = `第 ${rowNumbers[i]} 行`;
    for (const value of rows[i]) {
      const cell = document.createElement(i < headerRows ? 'th' : 'td');
      cell.textContent = value;
      if (i < headerRows) cell.scope = 'col';
      tr.append(cell);
    }
    node.append(tr);
  }
  if (rows.length - headerRows > 30) {
    // Large sheets: an in-table filter keeps the header and row numbers.
    const filter = document.createElement('input');
    filter.type = 'search';
    filter.placeholder = '筛选本表（任一单元格包含）…';
    filter.className = 'office-table-filter';
    filter.setAttribute('aria-label', '筛选本表');
    filter.addEventListener('input', () => {
      const needle = filter.value.trim().toLocaleLowerCase();
      node.querySelectorAll('tr').forEach((tr, index) => {
        if (index < headerRows) return;
        tr.hidden = Boolean(needle) && !tr.textContent.toLocaleLowerCase().includes(needle);
      });
    });
    wrapper.append(filter);
  }
  wrapper.append(node);
  if (table.caption) wrapper.prepend(el('p', table.caption, 'office-caption'));
  return wrapper;
}
function renderBlock(block) {
  const wrapper = el('section', '', 'office-block');
  wrapper.id = `block-${block.ordinal}`;
  wrapper.dataset.blockId = block.block_id;
  wrapper.dataset.contentRole = block.content_role || '';
  if (block.section_path) {
    wrapper.append(el('div', block.section_path, 'office-breadcrumb'));
  }
  if (block.block_type === 'heading') {
    const level = Math.min(6, Math.max(1, Number(block.heading_level) || 2));
    wrapper.append(el(`h${level}`, block.text, 'office-heading'));
  } else if (block.block_type === 'table' && block.table) {
    wrapper.append(renderTable(block.table));
  } else if (block.block_type === 'formula') {
    const formula = el('div', block.text || '（公式文字未提取）', 'office-formula');
    wrapper.append(formula);
    if (block.formula_status === 'unresolved') {
      wrapper.append(el('p', '公式尚未恢复为 LaTeX，请对照原件核对。', 'office-flag'));
    } else if (block.formula_status === 'latex') {
      wrapper.append(el('p', 'LaTeX 源码，已按公式渲染。', 'office-flag'));
    }
  } else if (block.block_type === 'image') {
    if (block.media_url) {
      const image = document.createElement('img');
      image.src = block.media_url;
      image.alt = block.caption || '文档图片';
      image.loading = 'lazy';
      image.className = 'office-image';
      wrapper.append(image);
      if (!block.caption) {
        wrapper.append(el('p', '嵌入图片；可对照原件核对。', 'office-flag'));
      }
    } else {
      wrapper.append(el('p', '图片内容未提取为文字；请在原件中查看。', 'office-flag'));
    }
  } else if (block.block_type === 'note') {
    const note = el('aside', block.text, 'office-note');
    note.prepend(el('strong', '备注', 'office-note-label'));
    wrapper.append(note);
  } else {
    wrapper.append(el('p', block.text, block.block_type === 'list_item' ? 'office-list-item' : 'office-paragraph'));
  }
  if (block.caption && block.block_type !== 'table') {
    wrapper.append(el('p', block.caption, 'office-caption'));
  }
  if (block.review_status === 'required') {
    wrapper.append(el('p', block.content_role === 'image_ocr' ? '此段来自图片自动识别，尚未人工复核。' : '此段来自自动识别，尚未人工复核。', 'office-flag'));
  }
  return wrapper;
}
function renderOutline(headings) {
  if (!headings || headings.length < 2) return null;
  const nav = el('nav', '', 'office-outline');
  nav.setAttribute('aria-label', '文档目录');
  nav.append(el('strong', '文档目录', 'office-outline-title'));
  for (const heading of headings) {
    const link = el('a', heading.text, `office-outline-level-${Math.min(3, heading.heading_level || 1)}`);
    link.href = `#block-${heading.ordinal}`;
    nav.append(link);
  }
  return nav;
}
let loadedBlocks = [];
let nextOffset = null;
let contentUrl = '';
const renderedCaptions = new Set();
function appendBlocks(blocks) {
  // Pre-scan image/table captions so a preceding CAPTION block is skipped too.
  const batchCaptions = new Set(
    blocks
      .map(block => (block.caption || (block.table && block.table.caption) || '').trim())
      .filter(Boolean)
  );
  const fragment = document.createDocumentFragment();
  for (const block of blocks) {
    const caption = (block.caption || (block.table && block.table.caption) || '').trim();
    if (block.block_type === 'caption') {
      const text = (block.text || '').trim();
      if (renderedCaptions.has(text) || batchCaptions.has(text)) continue;
    } else if (caption) {
      renderedCaptions.add(caption);
    }
    fragment.append(renderBlock(block));
  }
  $('office-content').append(fragment);
  loadedBlocks = loadedBlocks.concat(blocks);
}
function renderMore(offset) {
  const existing = $('office-more');
  if (existing) existing.remove();
  if (offset === null || offset === undefined) return;
  const button = el('button', '加载更多内容', 'office-more');
  button.id = 'office-more';
  button.type = 'button';
  button.addEventListener('click', () => loadPage(offset, ''));
  $('office-content').append(button);
}
async function loadPage(offset, blockId) {
  const button = $('office-more');
  if (button) button.disabled = true;
  const query = new URLSearchParams({offset: String(offset), limit: '200'});
  if (blockId) query.set('block_id', blockId);
  const response = await fetch(`${contentUrl}?${query}`, {cache: 'no-store'});
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    const code = detail.detail?.code;
    if (code === 'ANCHOR_NOT_FOUND') {
      notice('当前发布不包含该引用位置，可能已被重新解析。', 'warning');
      return;
    }
    throw new Error('正文暂时无法读取。可下载原件后查看。');
  }
  const content = await response.json();
  if (content.snapshot_missing) {
    notice('当前发布未提供正文快照；本页按原件即时解析，引用位置可能与索引快照不同。', 'warning');
  } else if (content.source === 'on_demand_conversion') {
    notice('原件为 DOC，正文按转换件显示；引用位置对应转换后的结构。', 'warning');
  } else {
    notice('');
  }
  const outline = renderOutline(content.outline);
  if (outline && !document.querySelector('.office-outline')) {
    $('office-content').prepend(outline);
  }
  appendBlocks(content.blocks || []);
  if (window.renderMathInElement) {
    window.renderMathInElement($('office-content'), {
      delimiters: [
        {left: '\\(', right: '\\)', display: false},
        {left: '\\[', right: '\\]', display: true}
      ],
      throwOnError: false, trust: false, strict: 'warn'
    });
  }
  nextOffset = content.next_offset;
  renderMore(nextOffset);
  if (blockId) highlight(loadedBlocks);
}
function highlight(blocks) {
  const requested = params.get('block_id');
  const ordinal = Number(params.get('ordinal'));
  let target = null;
  if (requested) {
    target = document.querySelector(`[data-block-id="${CSS.escape(requested)}"]`);
    if (!target) {
      // The citation may point at a block inside a chunk whose first block is
      // still the closest usable anchor.
      target = null;
    }
  }
  if (!target && Number.isInteger(ordinal)) {
    target = document.querySelector(`[data-block-id="${CSS.escape(blocks[ordinal]?.block_id || '')}"]`);
  }
  if (!target) return;
  target.classList.add('office-hit');
  const row = Number(params.get('row'));
  const rowNode = Number.isInteger(row) && row > 0 ? target.querySelector(`tr[data-row="${row}"]`) : null;
  if (rowNode) {
    rowNode.classList.add('office-row-hit');
    rowNode.scrollIntoView({block: 'center'});
    return;
  }
  target.scrollIntoView({block: 'center'});
  target.setAttribute('tabindex', '-1');
  target.focus({preventScroll: true});
}
async function load() {
  if (!documentId) {
    notice('无法识别文档编号。', 'error');
    return;
  }
  contentUrl = `/v1/rag/documents/${documentId}/content`;
  $('office-download').href = `/v1/rag/documents/${documentId}`;
  try {
    const metadataResponse = await fetch(`/v1/rag/documents/${documentId}/metadata`, {cache: 'no-store'});
    const metadata = metadataResponse.ok ? await metadataResponse.json() : {};
    const row = metadata.document || {};
    $('office-title').textContent = row.document_title || documentId;
    document.title = `${$('office-title').textContent} · 文档正文`;
    const metaParts = [
      (metadata.document_format || '').toUpperCase(),
      statusText(row)
    ].filter(Boolean);
    $('office-meta').textContent = metaParts.join(' · ');
    const blockId = params.get('block_id') || '';
    await loadPage(0, blockId);
    if (!loadedBlocks.length) {
      notice('该文档没有可显示的正文块，请下载原件查看。', 'warning');
      return;
    }
    $('office-meta').textContent = [
      $('office-meta').textContent,
      `${loadedBlocks.length} 个内容块起`
    ].filter(Boolean).join(' · ');
    if (!blockId) highlight(loadedBlocks);
  } catch (error) {
    notice(error.message || '正文加载失败。', 'error');
  }
}
load();
