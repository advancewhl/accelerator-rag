import {getDocument, GlobalWorkerOptions} from './pdfjs/build/pdf.mjs';
GlobalWorkerOptions.workerSrc = '/assets/pdfjs/build/pdf.worker.mjs';
const $ = id => document.getElementById(id);
let pdf = null, loading = null, renderTask = null, generation = 0, page = 1, zoom = 1, activeUrl = '', visible = false, returnFocus = null;
let paintQueue = Promise.resolve();
let returnScroll = 0;
let backAction = null;
function controls(disabled = false) {
  $('pdf-prev').disabled = disabled || page <= 1;
  $('pdf-next').disabled = disabled || !pdf || page >= pdf.numPages;
  for (const id of ['pdf-page', 'pdf-minus', 'pdf-plus', 'pdf-fit']) $(id).disabled = disabled;
}
function message(text) { $('pdf-message').textContent = text; $('pdf-message').hidden = !text; }
async function paint(id) {
  if (!pdf || !visible || id !== generation) return;
  const document = pdf;
  const requestedPage = page;
  const pdfPage = await document.getPage(requestedPage);
  if (id !== generation || document !== pdf || !visible) return;
  const base = pdfPage.getViewport({scale: 1});
  const available = Math.max(200, $('pdf-viewport').clientWidth - 36);
  const scale = Math.min(3, available / base.width * zoom);
  const viewport = pdfPage.getViewport({scale});
  const ratio = Math.min(window.devicePixelRatio || 1, 2);
  const canvas = $('pdf-canvas');
  canvas.width = Math.floor(viewport.width * ratio);
  canvas.height = Math.floor(viewport.height * ratio);
  canvas.style.width = `${viewport.width}px`;
  canvas.style.height = `${viewport.height}px`;
  renderTask = pdfPage.render({canvasContext:canvas.getContext('2d'), viewport, transform:ratio === 1 ? null : [ratio,0,0,ratio,0,0]});
  await renderTask.promise;
  renderTask = null;
  if (id !== generation || !visible) return;
  canvas.hidden = false; message('');
  $('pdf-page').value = requestedPage;
  $('pdf-total').textContent = `/ ${document.numPages}`;
  $('pdf-caption').textContent = `物理页 ${requestedPage} / ${document.numPages}`;
  $('pdf-fit').textContent = zoom === 1 ? '适宽' : `${Math.round(zoom * 100)}%`;
  controls();
}
function render() {
  if (!pdf || !visible) return;
  const id = ++generation;
  renderTask?.cancel();
  paintQueue = paintQueue.catch(() => {}).then(() => paint(id)).catch(error => {
    if (id !== generation || error.name === 'RenderingCancelledException') return;
    message('此页暂时无法显示，请重新选择页码或返回证据列表后重试。');
    controls();
  });
}
export async function openReader(citation, trigger, options = {}) {
  const url = citation.document_url;
  if (!/^\/v1\/rag\/documents\/[a-zA-Z0-9_-]+$/.test(url || '')) return;
  if (!visible) returnScroll = $('workspace').scrollTop;
  returnFocus = trigger || document.activeElement; visible = true;
  $('workspace').classList.add('reading');
  $('evidence-panel').hidden = true; $('pdf-reader').hidden = false;
  backAction = options.onClose || null;
  $('reader-expand').hidden = Boolean(options.onClose);
  $('reader-close').textContent = options.backLabel || '← 证据列表';
  $('reader-title').textContent = citation.document_title;
  $('reader-version').textContent = `${citation.number ? `引用 [${citation.number}]` : '知识库原文'} · ${citation.document_version === 'unknown' ? '文档未标明版本' : citation.document_version} · PDF 物理页`;
  $('reader-close').focus({preventScroll:true});
  page = Math.max(1, Number(citation.page_start) || 1); zoom = 1;
  $('pdf-viewport').scrollTop = 0;
  if (pdf && activeUrl === url) { page = Math.min(page, pdf.numPages); render(); return; }
  const id = ++generation;
  $('pdf-page').value = page; $('pdf-total').textContent = '/ …';
  renderTask?.cancel(); controls(true); message('正在加载 PDF 原文…'); $('pdf-canvas').hidden = true;
  const oldLoading = loading; loading = null; pdf = null; activeUrl = url;
  if (oldLoading) await oldLoading.destroy().catch(() => {});
  if (id !== generation || !visible) return;
  loading = getDocument({url, cMapUrl:'/assets/pdfjs/cmaps/', cMapPacked:true, standardFontDataUrl:'/assets/pdfjs/standard_fonts/', wasmUrl:'/assets/pdfjs/wasm/', isEvalSupported:false});
  try {
    const loaded = await loading.promise;
    if (id !== generation || !visible) return;
    pdf = loaded; page = Math.min(page, pdf.numPages); $('pdf-page').max = pdf.numPages; render();
  } catch {
    if (id === generation && visible) message('原文暂时无法加载。请返回证据列表，再次点击“阅读原文”重试。');
  }
}
export function closeReader(restoreFocus = true) {
  const action = backAction; backAction = null;
  visible = false; generation++; renderTask?.cancel();
  if (!pdf && loading) { loading.destroy().catch(() => {}); loading = null; }
  $('workspace').classList.remove('reading','expanded');
  $('reader-expand').hidden = false;
  $('reader-expand').setAttribute('aria-pressed','false');
  $('reader-expand').setAttribute('aria-label','展开阅读器');
  $('pdf-reader').hidden = true; $('evidence-panel').hidden = false;
  if (restoreFocus && action) action();
  if (restoreFocus) $('workspace').scrollTop = returnScroll;
  if (restoreFocus && returnFocus?.isConnected) returnFocus.focus({preventScroll:true});
}
$('reader-close').addEventListener('click', () => closeReader());
$('reader-expand').addEventListener('click', () => {
  const expanded = $('workspace').classList.toggle('expanded');
  $('reader-expand').setAttribute('aria-pressed', String(expanded));
  $('reader-expand').setAttribute('aria-label', expanded ? '恢复分栏' : '展开阅读器');
  render();
});
function go(value) {
  if (!pdf) return;
  page = Math.max(1, Math.min(pdf.numPages, Math.trunc(Number(value)) || page));
  $('pdf-viewport').scrollTop = 0; render();
}
$('pdf-prev').addEventListener('click', () => go(page - 1));
$('pdf-next').addEventListener('click', () => go(page + 1));
$('pdf-page').addEventListener('change', event => go(event.target.value));
$('pdf-page').addEventListener('keydown', event => { if (event.key === 'Enter') go(event.target.value); });
$('pdf-minus').addEventListener('click', () => { zoom = Math.max(.5, zoom - .25); render(); });
$('pdf-plus').addEventListener('click', () => { zoom = Math.min(2.5, zoom + .25); render(); });
$('pdf-fit').addEventListener('click', () => { zoom = 1; render(); });
document.addEventListener('keydown', event => { if (event.key === 'Escape' && visible) closeReader(); });
let resizeTimer;
new ResizeObserver(() => { clearTimeout(resizeTimer); resizeTimer = setTimeout(render, 150); }).observe($('pdf-viewport'));
