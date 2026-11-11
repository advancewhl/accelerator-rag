"""Publication figures, 180 mm wide; editable SVG, TrueType PDF, 600 dpi PNG."""
from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/rag-paper-matplotlib")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.colors import ListedColormap, BoundaryNorm
from matplotlib.patches import Rectangle, FancyArrowPatch
import numpy as np

OUT = Path(__file__).resolve().parents[1]
FIG = OUT / "figures"
D = json.loads((OUT / "data/evidence-snapshot.json").read_text())
font_manager.fontManager.addfont("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf")
font_manager.fontManager.addfont("/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf")
plt.rcParams.update({"font.family": "Liberation Sans", "font.size": 7,
                     "axes.labelsize": 7, "axes.titlesize": 7, "xtick.labelsize": 6.5,
                     "ytick.labelsize": 6.5, "legend.fontsize": 6.5,
                     "axes.linewidth": .65, "xtick.major.width": .65,
                     "ytick.major.width": .65, "xtick.major.size": 2.5,
                     "ytick.major.size": 2.5, "axes.spines.top": False,
                     "axes.spines.right": False, "svg.fonttype": "none",
                     "pdf.fonttype": 42, "ps.fonttype": 42,
                     "text.color": "#24292E", "axes.labelcolor": "#24292E",
                     "xtick.color": "#24292E", "ytick.color": "#24292E",
                     "savefig.facecolor": "white", "mathtext.fontset": "dejavusans"})
# Wong/Okabe-Ito colour identities; no claim that Nature prescribes fixed hex values.
C = {"blue": "#0072B2", "sky": "#56B4E9", "orange": "#E69F00",
     "vermillion": "#D55E00", "teal": "#009E73", "purple": "#CC79A7",
     "ink": "#24292E", "grey": "#A6ADB4", "light": "#F2F4F5"}
WIDTH = 180 / 25.4
RECEIPTS = []


def panel(ax, letter, title):
    ax.text(-.11, 1.045, letter, transform=ax.transAxes, fontsize=8, weight="bold", va="bottom")
    ax.set_title(title, loc="left", pad=9)


def save(fig, name, note):
    FIG.mkdir(parents=True, exist_ok=True)
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    outside = []
    bounds = fig.bbox
    for text in fig.findobj(matplotlib.text.Text):
        if not text.get_visible() or not text.get_text():
            continue
        box = text.get_window_extent(renderer)
        if box.x0 < -2 or box.y0 < -2 or box.x1 > bounds.x1 + 2 or box.y1 > bounds.y1 + 2:
            outside.append(text.get_text())
    if outside:
        raise ValueError(f"{name}: text outside figure: {outside}")
    for suffix in ("svg", "pdf", "png"):
        fig.savefig(FIG / f"{name}.{suffix}", dpi=600)
    RECEIPTS.append({"figure": name, "width_mm": 180,
                     "height_mm": round(fig.get_figheight() * 25.4, 1),
                     "note": note, "text_bounds_check": "passed"})
    plt.close(fig)


def box(ax, x, y, w, h, title, detail="", color="blue"):
    ax.add_patch(Rectangle((x, y), w, h, ec=C[color], fc="white", lw=.8))
    ax.add_patch(Rectangle((x, y + h - .014), w, .014, ec="none", fc=C[color]))
    ax.text(x + w / 2, y + h * (.66 if detail else .50), title, ha="center", va="center", fontsize=7)
    if detail:
        ax.text(x + w / 2, y + h * .29, detail, ha="center", va="center", fontsize=6.3, linespacing=1.4)


def arrow(ax, a, b, color="ink", style="-", connection="arc3"):
    ax.add_patch(FancyArrowPatch(a, b, arrowstyle="-|>", mutation_scale=7,
                                 lw=.7, color=C[color], linestyle=style,
                                 connectionstyle=connection, shrinkA=1, shrinkB=1))


def architecture():
    fig, ax = plt.subplots(figsize=(WIDTH, 4.35))
    fig.subplots_adjust(left=.03, right=.98, bottom=.04, top=.98)
    ax.set(xlim=(0, 1), ylim=(0, 1)); ax.axis("off")
    ax.text(0, .96, "a", weight="bold", fontsize=8)
    ax.text(.035, .96, "Offline corpus and immutable evidence identity", fontsize=7)
    xs = [.00, .255, .51, .765]
    titles = ["Registered PDF corpus", "Parse, clean and chunk", "Canonical evidence", "Model-specific indexes"]
    details = ["13 documents / 2,178 pages", "Page-local text; max. 1,200 chars", "4,537 parents; 4,532 eligible", "E5: 4,746 / Qwen3: 4,532 passages"]
    for x, title, detail in zip(xs, titles, details):
        box(ax, x, .75, .225, .14, title, detail)
    for x in xs[:-1]: arrow(ax, (x + .225, .82), (x + .255, .82))
    ax.text(0, .65, "b", weight="bold", fontsize=8)
    ax.text(.035, .65, "Online retrieval with the original user query", fontsize=7)
    box(ax, 0, .39, .17, .16, "User query", "No evaluation labels")
    box(ax, .24, .49, .23, .11, "E5 Top-10 parents", "Actual winning passages", "blue")
    box(ax, .24, .31, .23, .11, "Qwen3 Top-10 parents", "Actual winning passages", "orange")
    box(ax, .55, .39, .21, .16, "Candidate union", "Deduplicate by parent + text")
    box(ax, .83, .39, .16, .16, "Qwen3 reranker", "Top-5 full parents", "teal")
    for end in [(.24,.545),(.24,.365)]: arrow(ax,(.17,.47),end)
    for start in [(.47,.545),(.47,.365)]: arrow(ax,start,(.55,.47))
    arrow(ax,(.76,.47),(.83,.47))
    ax.text(.875,.695,"Queried by E5 and Qwen3",ha="center",fontsize=6.2)
    ax.text(0, .235, "c", weight="bold", fontsize=8)
    ax.text(.035, .235, "Grounded generation and source inspection", fontsize=7)
    items = [(0,.23,"Extract requirements","1-6 explicit factual needs"),(.31,.25,"Select and review claims","Only verified evidence spans"),(.64,.35,"Return answer and original PDF","Code-resolved citations + physical pages")]
    for x,w,t,d in items: box(ax,x,.025,w,.14,t,d,"teal")
    arrow(ax,(.23,.095),(.31,.095)); arrow(ax,(.56,.095),(.64,.095))
    arrow(ax,(.91,.39),(.91,.19)); arrow(ax,(.115,.39),(.115,.19),style="--")
    save(fig,"fig01-rag-architecture","Implementation schematic; arrows show data flow, not measured throughput.")


def corpus():
    labels = ["EPICS developer guide", "EPICS documentation", "European XFEL TDR", "Undulator spectrometer", "X-ray optics / transport", "E-beam diagnostics", "SHINE IOC / PV management", "SHINE fast interlock", "SHINE control status", "SHINE cryogenic control", "SHINE White Rabbit timing", "SHINE control slides", "SHINE preliminary design"]
    fig, axs = plt.subplots(1, 2, figsize=(WIDTH, 4.65), sharey=True)
    fig.subplots_adjust(left=.285, right=.95, bottom=.13, top=.88, wspace=.30)
    rows = D["corpus"]; y = np.arange(len(rows))
    for ax, key, letter, title in zip(axs,["pages","eligible_chunks"],["a","b"],["Physical pages", "Eligible canonical chunks"]):
        vals = [r[key] for r in rows]
        ax.barh(y, vals, height=.60, color=C["blue"], lw=0)
        ax.set_yticks(y, labels if ax is axs[0] else labels)
        ax.set_xlim(0,max(vals)*1.24)
        ax.set_xticks([0,200,400,600,800] if key == "pages" else [0,500,1000,1500,2000])
        ax.set_xlabel("Count")
        for yy,v in zip(y,vals): ax.text(v+max(vals)*.028,yy,f"{v:,}",va="center",fontsize=6.4)
        panel(ax,letter,title)
    axs[0].invert_yaxis()
    fig.text(.285,.035,"13 documents; 2,178 pages; 4,532 eligible parents. Bar lengths use linear scales.",fontsize=6.4)
    save(fig,"fig02-corpus-composition","All 13 registered documents; count axes start at zero.")


def retrieval():
    methods = [m for m in D["metrics_v2"] if "multi-query" not in m["method"]]
    fig,axs=plt.subplots(1,2,figsize=(WIDTH,3.7),sharey=True)
    fig.subplots_adjust(left=.21,right=.95,bottom=.17,top=.88,wspace=.30)
    y=np.arange(len(methods))
    colors=[C["blue"] if m["method"]!="Dual + reranker" else C["vermillion"] for m in methods]
    for ax,key,letter,title in zip(axs,["Hit@5","MRR@5"],["a","b"],["Complete evidence in Top-5","Reciprocal rank of complete evidence"]):
        vals=[m[key] for m in methods]
        ax.barh(y,vals,height=.60,color=colors,linewidth=0)
        for yy,v,m in zip(y,vals,methods):
            txt=f"{m['complete_at_5']}/21" if key=="Hit@5" else f"{v:.4f}"
            ax.text(v+.025,yy,txt,va="center",fontsize=6.5)
        ax.set(yticks=y,yticklabels=[m["method"] for m in methods],xlim=(0,1.22),xticks=[0,.25,.5,.75,1])
        ax.set_xlabel("Hit@5" if key=="Hit@5" else "MRR@5")
        panel(ax,letter,title)
    axs[0].invert_yaxis()
    fig.text(.21,.035,"Same 21 answerable queries and evidence-contract-v2. Descriptive results; no held-out test set.",fontsize=6.3)
    save(fig,"fig03-retrieval-comparison","11 methods exported; 9 original-query methods shown here; multi-query in Figure 5.")


def rankmap():
    methods=["BM25","E5","Qwen3","Language router","Dual RRF","Dual + reranker"]
    rows=[r for r in D["ranks_v2"] if r["method"]=="E5"]
    lookup={(r["query_id"],r["method"]):r["first_complete_rank"] for r in D["ranks_v2"]}
    a=np.array([[lookup[(r["query_id"],m)] or 6 for m in methods] for r in rows])
    fig,ax=plt.subplots(figsize=(WIDTH,5.3));fig.subplots_adjust(left=.30,right=.96,top=.90,bottom=.13)
    cmap=ListedColormap(["#C0E0EF","#CBE5F0","#D6EBF3","#E2F0F6","#EDF6F9","#E8EAEC"])
    ax.imshow(a,cmap=cmap,norm=BoundaryNorm(np.arange(.5,7.5),6),aspect="auto",interpolation="nearest")
    for i in range(a.shape[0]):
        for j in range(a.shape[1]):ax.text(j,i,str(a[i,j]) if a[i,j]<6 else "-",ha="center",va="center",fontsize=6.5)
    ax.set(xticks=range(6),xticklabels=["BM25","E5","Qwen3","Language\nrouter","Dual\nRRF","Dual +\nreranker"],yticks=range(21),yticklabels=[r["query_id"] for r in rows])
    ax.tick_params(axis="both",length=0);ax.spines[["left","bottom"]].set_visible(False)
    panel(ax,"a","First rank at which all required evidence is covered")
    fig.text(.30,.025,"Digits: first complete rank (1-5); dash: incomplete within Top-5. All cells use v2 labels.\nColour is supporting context; exact ranks remain visible in grayscale.",fontsize=6.3,linespacing=1.6)
    save(fig,"fig04-query-rank-matrix","21 answerable queries; a cell can require evidence spread across multiple parent results.")


def ablations():
    fig,axs=plt.subplots(1,3,figsize=(WIDTH,3.25));fig.subplots_adjust(left=.07,right=.98,top=.85,bottom=.23,wspace=.52)
    ax=axs[0]; rows=[r for r in D["historical_ablations"] if r["experiment"].startswith("annotation") and "multilingual-e5" in r["method"]]
    vals=[r["Hit@5"] for r in rows];ax.bar([0,1],vals,color=[C["grey"],C["blue"]],width=.55)
    ax.set(xticks=[0,1],xticklabels=["v1 labels","v2 labels"],ylim=(0,1.08),ylabel="Hit@5")
    for i,v in enumerate(vals):ax.text(i,v+.03,f"{round(v*21)}/21",ha="center",fontsize=6.5)
    panel(ax,"a","Annotation-only rejudgment\nE5; identical saved ranking")
    ax=axs[1];rows=[r for r in D["historical_ablations"] if r["experiment"].startswith("passage")];vals=[r["Hit@5"] for r in rows]
    ax.bar([0,1],vals,color=[C["grey"],C["blue"]],width=.55);ax.set(xticks=[0,1],xticklabels=["Direct","Passage"],ylim=(0,1.08),ylabel="Hit@5")
    for i,v in enumerate(vals):ax.text(i,v+.03,f"{round(v*21)}/21",ha="center",fontsize=6.5)
    panel(ax,"b","Token-safe representation\nBGE-small-zh; v1 labels")
    ax=axs[2];names=["E5","Qwen3"]; lookup={m["method"]:m for m in D["metrics_v2"]}
    for offset,suffix,color in [(-.17,"",C["blue"]),(.17," + multi-query",C["orange"])]:
        vals=[lookup[n+suffix]["Hit@5"] for n in names];xx=np.arange(2)+offset
        ax.bar(xx,vals,width=.30,color=color,label="Original" if not suffix else "Multi-query")
        for x,v in zip(xx,vals):ax.text(x,v+.025,str(round(v*21)),ha="center",fontsize=6.2)
    ax.set(xticks=range(2),xticklabels=names,ylim=(0,1.08),ylabel="Hit@5");ax.legend(frameon=False,loc="upper right",bbox_to_anchor=(1.05,-.13),ncol=1)
    panel(ax,"c","Shared query-plan experiment\nv2 labels; counts out of 21")
    fig.text(.07,.035,"Panels use different controls. Panel a changes labels only; it is not a retrieval improvement.",fontsize=6.3)
    save(fig,"fig05-controls-and-negative-results","No cross-panel effect sizes should be inferred; label versions are explicit.")


def coverage():
    fig,axs=plt.subplots(1,2,figsize=(WIDTH,3.65));fig.subplots_adjust(left=.30,right=.97,top=.88,bottom=.19,wspace=.42)
    ax=axs[0];vals=[20,19,20,19];labels=["Candidate parents", "Scored candidate passages", "Final Top-5 parents", "Final winning passages"]
    ax.barh(range(4),vals,color=[C["blue"],C["orange"],C["blue"],C["orange"]],height=.55)
    for y,v in enumerate(vals):ax.text(v+.25,y,f"{v}/21",va="center",fontsize=6.5)
    ax.set(yticks=range(4),yticklabels=labels,xlim=(0,23),xticks=[0,5,10,15,20],xlabel="Queries with complete evidence");ax.invert_yaxis()
    panel(ax,"a","Coverage at different evidence layers")
    ax=axs[1];ax.axis("off");ax.set(xlim=(0,1),ylim=(0,1))
    ax.text(0,1.03,"b",fontsize=8,weight="bold");ax.text(.12,1.03,"Observed failure mechanisms",fontsize=7)
    box(ax,0,.60,1,.26,"shine-main-linac","Full parent: complete\nScored passage: incomplete","orange")
    box(ax,0,.16,1,.26,"shine-ioc-startup","Candidate evidence: 1 of 2 groups\nReranking cannot add missing evidence","vermillion")
    fig.text(.30,.04,"Coverage is measured against frozen v2 evidence groups. Parent coverage does not prove model exposure.",fontsize=6.1)
    save(fig,"fig06-evidence-layer-gap","Candidate union has up to 20 parents; final ranking has at most 5 parents.")


def generation():
    fig,ax=plt.subplots(figsize=(WIDTH,4.0));fig.subplots_adjust(left=.025,right=.975,bottom=.04,top=.96)
    ax.axis("off");ax.set(xlim=(0,1),ylim=(0,1))
    box(ax,0,.75,.26,.18,"Requirement extraction","Original query only\n1-6 factual requirements")
    box(ax,.37,.75,.26,.18,"Evidence selection","Top-5 full parents\nRequest-local span IDs")
    box(ax,.74,.75,.26,.18,"Claim synthesis","Supported requirements\nVerified spans only","teal")
    arrow(ax,(.26,.84),(.37,.84));arrow(ax,(.63,.84),(.74,.84))
    box(ax,.74,.40,.26,.20,"Claim and coverage review","Subject, condition, number, version\nOne bounded rewrite if needed","orange")
    arrow(ax,(.87,.75),(.87,.60))
    box(ax,.37,.40,.26,.20,"Deterministic checks","IDs, bindings, numeric provenance\nReject unsupported claims","teal")
    arrow(ax,(.74,.50),(.63,.50))
    box(ax,0,.40,.26,.20,"Code-computed status","All / some / none supported\nanswered / partial / insufficient","teal")
    arrow(ax,(.37,.50),(.26,.50))
    box(ax,0,.055,.63,.20,"Source resolution and original PDF","Map span to canonical parent, document, version and physical page\nThe model does not generate filesystem paths or citation identities")
    arrow(ax,(.13,.40),(.13,.255))
    ax.text(.74,.16,"Semantic review is model-based.\nValid IDs and numbers do not\nprove factual completeness.",fontsize=6.5,linespacing=1.7)
    save(fig,"fig07-grounded-generation-contract","Schematic of current implementation; same model/provider performs multiple roles, not an independent judge.")


def production():
    fig=plt.figure(figsize=(WIDTH,4.4));gs=fig.add_gridspec(2,2,left=.13,right=.97,bottom=.17,top=.90,hspace=.9,wspace=.45)
    ax=fig.add_subplot(gs[0,0]);left=0
    for n,color,label in [(20,"blue","answered"),(1,"orange","partial")]:
        ax.barh([0],n,left=left,height=.4,color=C[color],label=label)
        ax.text(left+n/2,0,str(n),ha="center",va="center",color="white" if n>1 else C["ink"],fontsize=7)
        left+=n
    ax.barh([1],11,height=.4,color=C["grey"],label="insufficient");ax.text(5.5,1,"11",ha="center",va="center",fontsize=7)
    ax.set(yticks=[0,1],yticklabels=["Answerable","Negative"],xlim=(0,22),xticks=[0,5,10,15,20],xlabel="Requests");ax.invert_yaxis()
    ax.legend(frameon=False,ncol=3,loc="upper left",bbox_to_anchor=(-.10,-.55),columnspacing=.75,handlelength=1)
    panel(ax,"a","Returned states; not answer accuracy")
    ax=fig.add_subplot(gs[0,1]);lat=D["latency"]
    for x,flag,color,marker in [(0,True,"blue","o"),(1,False,"grey","s")]:
        vals=np.array([r["total_seconds"] for r in lat if r["answerable"]==flag]);jitter=np.linspace(-.12,.12,len(vals))
        ax.scatter(x+jitter,vals,s=8,color=C[color],marker=marker,linewidths=.3,edgecolors="white")
        ax.plot([x-.18,x+.18],[np.median(vals)]*2,color=C["ink"],lw=1.1)
    ax.set(xticks=[0,1],xticklabels=["Answerable\n(n = 21)","Negative\n(n = 11)"],ylabel="Total latency (s)",ylim=(0,6.5))
    panel(ax,"b","Individual requests; line = median")
    ax=fig.add_subplot(gs[1,:]);means=D["production"]["mean_latency_32"];start=0
    for field,color,label in [("retrieval_seconds","sky","Dense retrieval"),("rerank_seconds","orange","Reranking"),("generation_seconds","blue","Generation pipeline")]:
        value=means[field];ax.barh([0],value,left=start,height=.4,color=C[color]);
        if value>.5:ax.text(start+value/2,0,f"{label}: {value:.3f} s",ha="center",va="center",color="white",fontsize=7)
        else:ax.annotate(f"{label}\n{value:.3f} s",xy=(start+value/2,.21),xytext=(.28 if start==0 else .72,.47 if start==0 else .82),ha="center",fontsize=6.2,arrowprops={"arrowstyle":"-","lw":.5})
        start+=value
    ax.set(xlim=(0,2.85),xticks=[0,.5,1,1.5,2,2.5],ylim=(-.5,1.15),yticks=[],xlabel="Mean latency over all 32 requests (s)")
    panel(ax,"c","Component timing; small orchestration overhead excluded from stack")
    fig.text(.13,.025,"qwen3.8-Flash-Next; 26 Oct 2026. Answerable mean: 3.337 s; all-query mean: 2.513 s.\nLater ds-1017 checks are a separate sample. The IOC-startup answer misses frozen required fields.",fontsize=6.2,linespacing=1.6)
    save(fig,"fig08-production-validation","Raw per-request points; fixed sample, warm runtime, no confidence interval or concurrency extrapolation.")


if __name__ == "__main__":
    for draw in [architecture,corpus,retrieval,rankmap,ablations,coverage,generation,production]:
        draw()
    (FIG / "figure-receipts.json").write_text(json.dumps(RECEIPTS,indent=2)+"\n")
    print(f"Created {len(RECEIPTS)} figures in SVG, PDF and 600 dpi PNG.")
