import {getDocument, GlobalWorkerOptions} from './pdfjs/build/pdf.mjs';
GlobalWorkerOptions.workerSrc = '/assets/pdfjs/build/pdf.worker.mjs';
const $ = id => document.getElementById(id);
const source = location.pathname.replace(/\/view\/?$/, '');
$('original').href = source;
let pdf, rendering = false;
function pageNumber() {return Math.max(1, Math.min(pdf?.numPages || 1, Number(new URLSearchParams(location.hash.slice(1)).get('page')) || 1));}
async function render() {
  if (!pdf || rendering) return;
  rendering = true;
  $('previous').disabled = $('next').disabled = true;
  try {
    const number = pageNumber();
    $('number').value = number;
    $('original').href = source + '#page=' + number;
    const page = await pdf.getPage(number);
    const viewport = page.getViewport({scale:1.5});
    const canvas = $('canvas');
    canvas.width = viewport.width; canvas.height = viewport.height;
    canvas.style.width = `${Math.min(viewport.width, window.innerWidth - 32)}px`;
    await page.render({canvasContext:canvas.getContext('2d'),viewport}).promise;
    $('message').hidden = true;
    document.title = `物理页 ${number} / ${pdf.numPages} · 原始文档`;
  } catch { $('message').hidden = false; $('message').textContent = '此页暂时无法显示，请使用“打开 / 下载 PDF”核对原文。'; }
  finally {rendering = false; $('previous').disabled = pageNumber() <= 1; $('next').disabled = pageNumber() >= pdf.numPages;}
}
function go(value) {location.hash = 'page=' + Math.max(1,Math.min(pdf.numPages,Number(value)||1));}
$('previous').onclick = () => go(pageNumber()-1);
$('next').onclick = () => go(pageNumber()+1);
$('number').onchange = () => go($('number').value);
window.addEventListener('hashchange',render);
window.addEventListener('resize',render);
try {
  pdf = await getDocument({url:source,cMapUrl:'/assets/pdfjs/cmaps/',cMapPacked:true,standardFontDataUrl:'/assets/pdfjs/standard_fonts/',wasmUrl:'/assets/pdfjs/wasm/',isEvalSupported:false}).promise;
  $('total').textContent = pdf.numPages; $('number').max = pdf.numPages;
  await render();
} catch { $('message').textContent = '原始文档暂时无法加载，请稍后重试。'; }
