"""Chinese publication figures; exact 180 mm width and vector PDF/SVG."""
import os
os.environ.setdefault('MPLCONFIGDIR','/tmp/rag-paper-v2-mpl')
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import Rectangle,FancyArrowPatch
from fontTools.ttLib import TTCollection
import numpy as np

OUT=Path(__file__).resolve().parents[1];FIG=OUT/'figures';FIG.mkdir(exist_ok=True)
S=json.loads((OUT/'data/paper-statistics.json').read_text())
ROOT=OUT.parents[1]
LAT=json.loads((ROOT/'papers/rag-thesis/data/evidence-snapshot.json').read_text())['latency']
sc=Path('/tmp/rag-paper-v2-noto-sc.otf')
if not sc.exists():TTCollection('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc').fonts[2].save(sc)
font_manager.fontManager.addfont(sc)
plt.rcParams.update({'font.family':'Noto Sans CJK SC','font.size':8.2,'axes.labelsize':8.2,'axes.titlesize':8.5,
 'xtick.labelsize':8,'ytick.labelsize':8,'legend.fontsize':8,'axes.linewidth':.65,'xtick.major.width':.65,'ytick.major.width':.65,
 'axes.spines.top':False,'axes.spines.right':False,'pdf.fonttype':3,'svg.fonttype':'none','mathtext.fontset':'dejavusans',
 'text.color':'#24292E','axes.labelcolor':'#24292E','savefig.facecolor':'white'})
C={'blue':'#0072B2','orange':'#E69F00','teal':'#009E73','grey':'#A6ADB4','light':'#E9F1F5','ink':'#24292E'}
W=180/25.4
RECEIPTS=[]


def save(fig,name):
 fig.canvas.draw();renderer=fig.canvas.get_renderer();bad=[]
 for t in fig.findobj(matplotlib.text.Text):
  if t.get_visible() and t.get_text():
   b=t.get_window_extent(renderer)
   if b.x0<-.5 or b.y0<-.5 or b.x1>fig.bbox.x1+.5 or b.y1>fig.bbox.y1+.5:bad.append(t.get_text())
 if bad:raise ValueError((name,bad))
 for ext in ['pdf','svg','png']:fig.savefig(FIG/(name+'.'+ext),dpi=600)
 RECEIPTS.append({'figure':name,'width_mm':180,'height_mm':fig.get_figheight()*25.4,'minimum_label_pt':8,'text_bounds':'passed'})
 plt.close(fig)


def box(ax,x,y,w,h,title,detail='',color='blue'):
 ax.add_patch(Rectangle((x,y),w,h,ec=C[color],fc='white',lw=.8))
 ax.add_patch(Rectangle((x,y+h-.014),w,.014,color=C[color],lw=0))
 ax.text(x+w/2,y+h*(.66 if detail else .5),title,ha='center',va='center',fontsize=8.2)
 if detail:ax.text(x+w/2,y+h*.28,detail,ha='center',va='center',fontsize=8,linespacing=1.35)


def arrow(ax,a,b,style='-'):
 ax.add_patch(FancyArrowPatch(a,b,arrowstyle='-|>',mutation_scale=8,lw=.75,color=C['ink'],linestyle=style,shrinkA=1,shrinkB=1))


def architecture():
 fig,ax=plt.subplots(figsize=(W,2.95));fig.subplots_adjust(left=.015,right=.985,top=.98,bottom=.025)
 ax.set(xlim=(0,1),ylim=(0,1));ax.axis('off')
 ax.text(0,.96,'a  离线证据与表示',fontsize=8.5)
 for x,t,d in [(0,'登记语料','13 份 PDF / 2,178 页'),(.26,'规范证据块','4,532 个可检索父块'),(.52,'模型专用片段','E5：4,746 / Qwen3：4,532'),(.78,'签名索引','权重、模板、tokenizer 契约')]:box(ax,x,.70,.22,.17,t,d)
 for x in [0,.26,.52]:arrow(ax,(x+.22,.785),(x+.26,.785))
 ax.text(0,.59,'b  在线候选与重排',fontsize=8.5)
 box(ax,0,.25,.17,.22,'原始问题','标识符与条件')
 box(ax,.235,.36,.25,.17,'E5 前 10 个父块','保留实际命中片段')
 box(ax,.235,.10,.25,.17,'Qwen3 前 10 个父块','保留实际命中片段','orange')
 box(ax,.55,.25,.19,.22,'候选合并','按父块与片段去重')
 box(ax,.805,.25,.195,.22,'重排与父块恢复','返回前 5 个完整父块','teal')
 for y in [.445,.185]:arrow(ax,(.17,.36),(.235,y));arrow(ax,(.485,y),(.55,.36))
 arrow(ax,(.74,.36),(.805,.36))
 save(fig,'fig01-architecture-cn')


def state():
 fig,ax=plt.subplots(figsize=(W,2.65));fig.subplots_adjust(left=.015,right=.985,top=.98,bottom=.02)
 ax.set(xlim=(0,1),ylim=(0,1));ax.axis('off')
 for x,t,d in [(0,'需求提取','原始问题 → 1～6 项'),(.35,'证据选择','父块 → 请求内 span'),(.70,'受限综合','已支持要求 → claim')]:box(ax,x,.70,.30,.24,t,d)
 arrow(ax,(.30,.82),(.35,.82));arrow(ax,(.65,.82),(.70,.82))
 for x,t,d,col in [(0,'代码计算状态','全部 / 部分 / 无支持','teal'),(.35,'确定性校验','ID、绑定、数字来源','teal'),(.70,'语义与覆盖核查','失败后用同证据重写一次','orange')]:box(ax,x,.20,.30,.24,t,d,col)
 arrow(ax,(.85,.70),(.85,.44));arrow(ax,(.70,.32),(.65,.32));arrow(ax,(.35,.32),(.30,.32))
 ax.text(.5,.045,'span → 规范父块 → 文档与版本 → PDF 物理页',ha='center',fontsize=8.2)
 save(fig,'fig02-grounded-state-cn')


def confidence():
 names=['BM25','E5','Qwen3','Dual + reranker'];labels=['BM25','E5','Qwen3','双模型重排']
 fig,axs=plt.subplots(1,2,figsize=(W,2.9));fig.subplots_adjust(left=.17,right=.97,top=.86,bottom=.22,wspace=.40)
 for ax,metric,ci,title,letter in [(axs[0],'Hit@5','hit_ci95','完整证据覆盖','a'),(axs[1],'MRR@5','mrr_ci95','完整首次排名','b')]:
  for y,m in enumerate(names):
   v=S['methods'][m][metric];low,high=S['methods'][m][ci];col=C['blue'] if m!='Dual + reranker' else C['orange']
   ax.errorbar(v,y,xerr=[[v-low],[high-v]],fmt='o' if m!='Dual + reranker' else 's',color=col,ecolor=col,markersize=4,capsize=2,elinewidth=.9)
   ax.text(1.05,y,f'{v:.3f}',fontsize=8,va='center')
  ax.set(yticks=range(4),yticklabels=labels,xlim=(0,1.22),xticks=[0,.25,.5,.75,1],ylim=(3.55,-.55),xlabel=metric)
  ax.set_title(title,loc='left',fontsize=8.5);ax.text(-.16,1.06,letter,transform=ax.transAxes,fontsize=9,fontweight='bold')
 fig.text(.17,.055,'n = 21；v2 标注；配对 bootstrap 1,000 次，seed = 20261027',fontsize=8)
 save(fig,'fig03-bootstrap-cn')


def diagnostic():
 fig,axs=plt.subplots(1,3,figsize=(W,2.9));fig.subplots_adjust(left=.07,right=.98,top=.85,bottom=.24,wspace=.55)
 ax=axs[0];vals=[20,19];ax.bar([0,1],vals,width=.55,color=[C['blue'],C['orange']]);ax.set(xticks=[0,1],xticklabels=['父块','评分片段'],ylim=(0,23),yticks=[0,5,10,15,20],ylabel='完整问题数')
 for i,v in enumerate(vals):ax.text(i,v+.5,str(v)+'/21',ha='center',fontsize=8)
 ax.set_title('证据粒度差异',loc='left',fontsize=8.5);ax.text(-.22,1.06,'a',transform=ax.transAxes,fontsize=9,fontweight='bold')
 ax=axs[1];xs=np.arange(2)
 for delta,key,color,label in [(-.16,'','blue','原始查询'),(.16,' + multi-query','orange','多查询')]:
  vals=[S['methods'][m+key]['hit_count'] for m in ['E5','Qwen3']];ax.bar(xs+delta,vals,.29,color=C[color],label=label)
  for x,v in zip(xs+delta,vals):ax.text(x,v+.45,str(v),ha='center',fontsize=8)
 ax.set(xticks=xs,xticklabels=['E5','Qwen3'],ylim=(0,23),yticks=[0,5,10,15,20],ylabel='完整问题数（n=21）');ax.legend(frameon=False,loc='upper center',bbox_to_anchor=(.5,-.14),ncol=2,columnspacing=.5,handlelength=.8)
 ax.set_title(f"多查询：{S['multi_query_cost']['E5']['call_multiplier']:.3f} 倍调用",loc='left',fontsize=8.5);ax.text(-.22,1.06,'b',transform=ax.transAxes,fontsize=9,fontweight='bold')
 ax=axs[2]
 for x,flag,marker,color in [(0,True,'o','blue'),(1,False,'s','grey')]:
  vals=[r['total_seconds'] for r in LAT if r['answerable']==flag];j=np.linspace(-.13,.13,len(vals));ax.scatter(x+j,vals,s=11,color=C[color],marker=marker,edgecolors='white',linewidths=.25)
  ax.plot([x-.2,x+.2],[np.median(vals)]*2,color=C['ink'],lw=1)
 ax.set(xticks=[0,1],xticklabels=['可答\n(n=21)','负例\n(n=11)'],ylim=(0,6),yticks=[0,2,4,6],ylabel='总耗时（s）')
 ax.set_title('端到端延迟分布',loc='left',fontsize=8.5);ax.text(-.22,1.06,'c',transform=ax.transAxes,fontsize=9,fontweight='bold')
 save(fig,'fig04-diagnostics-cn')


if __name__=='__main__':
 for f in [architecture,state,confidence,diagnostic]:f()
 (FIG/'receipts.json').write_text(json.dumps(RECEIPTS,ensure_ascii=False,indent=2)+'\n')
 print('PASS: four Chinese figures; 180 mm; minimum labels 8 pt; PDF + SVG + 600 dpi PNG.')
