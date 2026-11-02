'use strict';
(async () => {
  const status = document.getElementById('status');
  try {
    const source = location.pathname.replace(/\/view$/, '');
    const response = await fetch(`${source}/sections`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    const md = window.markdownit({html:false, linkify:false});
    // Source links are plain labels here: relative repo paths aren't web routes.
    md.renderer.rules.link_open = () => '';
    md.renderer.rules.link_close = () => '';
    md.disable(['image']);
    for (const row of data.sections) {
      const section = document.createElement('section');
      section.id = `section-${row.index}`;
      const label = document.createElement('p');
      label.className = 'locator'; label.textContent = `Markdown 章节索引 ${row.index}`;
      const body = document.createElement('div');
      let text = row.text;
      const metadata = text.match(/^---[ \t]*\n([\s\S]*?)\n---[ \t]*(?:\n|$)/);
      if (metadata) {
        const details = document.createElement('details');
        const summary = document.createElement('summary'); summary.textContent = '文档元数据';
        const pre = document.createElement('pre'); pre.textContent = metadata[1];
        details.append(summary, pre); section.append(details);
        text = text.slice(metadata[0].length);
      }
      const math = [];
      const protectedText = text.replace(/\\\([\s\S]*?\\\)|\\\[[\s\S]*?\\\]|\$\$[\s\S]*?\$\$|(?<!\$)\$[^\n$]+\$(?!\$)/g, text => {
        const token = `RAGMATHPLACEHOLDER${math.length}END`; math.push(text); return token;
      });
      body.innerHTML = md.render(protectedText.replace(/^<a id="[A-Za-z0-9_.-]+"><\/a>\s*$/gm, ''));
      const walker = document.createTreeWalker(body, NodeFilter.SHOW_TEXT);
      const nodes = []; while (walker.nextNode()) nodes.push(walker.currentNode);
      for (const node of nodes) node.textContent = node.textContent.replace(/RAGMATHPLACEHOLDER(\d+)END/g, (_, n) => math[Number(n)]);
      window.renderMathInElement(body, {delimiters:[{left:'$$',right:'$$',display:true},{left:'\\[',right:'\\]',display:true},{left:'\\(',right:'\\)',display:false},{left:'$',right:'$',display:false}],throwOnError:false,trust:false});
      section.append(label, body); document.getElementById('content').append(section);
    }
    status.textContent = '章节索引仅对应此修订版 Markdown，不是 PDF 页码。';
    document.getElementById(location.hash.slice(1))?.scrollIntoView();
  } catch (error) {
    status.textContent = `原文加载失败：${error.message}。请检查文档是否仍可访问。`;
  }
})();
