import re, sys, pathlib, math, html
"""Builds contact-sheet.html from contact-sheet.tpl.html: expands {{icon:..}}, {{sparkline:..}} and the other macros.
Run: python3 docs/design/build-contact-sheet.py   (from anywhere)"""
S = pathlib.Path(__file__).resolve().parent; out = S / "contact-sheet.html"
tpl = (S/"contact-sheet.tpl.html").read_text()
def path(n):
    t = (S/"icons"/f"{n}.svg").read_text()
    return re.search(r'<path d="([^"]+)"', t).group(1)
def icon(n, cls="pa-icon"):
    if cls != "pa-icon": cls = "pa-icon " + cls
    return f'<svg class="{cls}" viewBox="0 -960 960 960" aria-hidden="true" focusable="false"><path d="{path(n)}"/></svg>'
H = 56; TOP = 4
def sparksvg(counts):
    n=len(counts); scale=max(5, max(counts)); step=100/(n-1)  # one y-scale shared by every card, as the app does
    y=lambda c: H - math.sqrt(min(c,scale)/scale)*(H-TOP)
    pts=[(i*step,y(c)) for i,c in enumerate(counts)]
    f=lambda ps:" ".join(f"{a:.2f},{b:.2f}" for a,b in ps)
    runs=[]
    for i in range(n-1):
        act=counts[i]>0 or counts[i+1]>0
        if runs and runs[-1][0]==act: runs[-1][1].append(pts[i+1])
        else: runs.append([act,[pts[i],pts[i+1]]])
    runs.sort(key=lambda r:r[0])
    lines="".join(f'<polyline class="pa-sparkline__line{"" if a else " pa-sparkline__line--quiet"}" points="{f(p)}"/>' for a,p in runs)
    area=f"0,{H} {f(pts)} 100,{H}"
    dot="pa-sparkline__dot" + ("" if counts[-1]>0 else " pa-sparkline__dot--quiet")
    bottom=(H-pts[-1][1])/H*100
    return (f'<svg class="pa-sparkline__svg" viewBox="0 0 100 {H}" preserveAspectRatio="none" aria-hidden="true">'
            f'<line class="pa-sparkline__grid" x1="0" x2="100" y1="{y(scale):.2f}" y2="{y(scale):.2f}"/><polygon class="pa-sparkline__area" points="{area}"/>{lines}</svg>'
            f'<span class="{dot}" style="bottom:{bottom:.1f}%"></span>')
def sparkline(counts):
    peak=max(counts)
    return (f'<span class="pa-sparkline" role="img" aria-label="Signals per week over the last {len(counts)} weeks: peak {peak}; {counts[-1]} this week.">'
            f'<span class="pa-sparkline__plot">{sparksvg(counts)}</span><span class="pa-sparkline__axis"><span>12 May</span><span>This week</span></span></span>')
C=2*math.pi*7.5
def ring(score):
    return (f'<svg class="pa-meter__ring" viewBox="0 0 20 20" aria-hidden="true"><circle class="pa-meter__track" cx="10" cy="10" r="7.5"/>'
            f'<circle class="pa-meter__arc" cx="10" cy="10" r="7.5" stroke-dasharray="{C*score/100:.2f} {C:.2f}"/></svg>')
def meter(score,label,value):
    v=f'<span class="pa-meter__value">{value}</span>' if value else ""
    return f'<figure class="cs-var"><span class="pa-meter">{ring(int(score))}<span class="pa-meter__label">{label}</span>{v}</span><figcaption><b>Score {score}</b></figcaption></figure>'
def empty(title,text,action):
    a=f'<button class="pa-btn pa-btn--secondary pa-btn--compact pa-empty-state__action" type="button">{action}</button>' if action else ""
    return (f'<figure class="cs-var cs-var--grow"><div class="pa-empty-state" role="status"><span class="pa-empty-state__icon">{icon("inbox")}</span>'
            f'<div class="pa-empty-state__body"><p class="pa-empty-state__title">{title}</p><p class="pa-empty-state__text">{text}</p>{a}</div></div>'
            f'<figcaption><b>{"With action" if action else "Text only"}</b></figcaption></figure>')
def rng(v):
    v=int(v)
    return (f'<div class="pa-range" style="--pa-range-value:{v}%"><output class="pa-range__value" for="r{v}">{v}</output>'
            f'<input class="pa-range__input" id="r{v}" type="range" min="0" max="100" value="{v}" aria-label="Minimum score" oninput="this.parentNode.style.setProperty(\'--pa-range-value\',this.value+\'%\');this.previousElementSibling.value=this.value">'
            f'<span class="pa-range__scale"><span>0</span><span>100</span></span></div>')
def linechart(counts):
    n=len(counts); top=max(counts); top=int(math.ceil(top/5)*5); HH=100
    y=lambda c: HH-(c/top)*(HH-4); step=100/(n-1)
    pts=[(i*step,y(c)) for i,c in enumerate(counts)]
    line="M"+" L".join(f"{a:.2f},{b:.2f}" for a,b in pts)
    area=f"{line} L100,{HH} L0,{HH} Z"
    grid="".join(f'<line class="pa-line-chart__grid" x1="0" x2="100" y1="{y(v):.2f}" y2="{y(v):.2f}"/>' for v in (top//2,top))
    ticks="".join(f'<span style="bottom:{(HH-y(v))/HH*100:.1f}%">{v}</span>' for v in (0,top//2,top))
    marks="".join(f'<span class="pa-line-chart__mark" style="left:{pts[i][0]:.2f}%;bottom:{(HH-pts[i][1])/HH*100:.1f}%"></span>' for i in (9,14,20,24))
    h=11; hx=pts[h][0]; hb=(HH-pts[h][1])/HH*100
    hover=(f'<span class="pa-line-chart__guide" style="left:{hx:.2f}%"></span><span class="pa-line-chart__hdot" style="left:{hx:.2f}%;bottom:{hb:.1f}%"></span><span class="pa-tooltip pa-line-chart__tip" style="left:{hx:.2f}%">'
           f'<span>21–27 Jul</span><span class="pa-tooltip__value">{counts[h]} signals</span><span>Top: Evolution Malta Holding Limited to pay £4.75m</span></span>')
    months=["May","Jun","Jul","Aug","Sep","Oct"]
    xs="".join(f'<span style="left:{(i*4+2)*step:.2f}%">{m}</span>' for i,m in enumerate(months) if (i*4+2)<n)
    return (f'<div class="pa-line-chart" role="img" aria-label="Signals per week over the last {n} weeks, {sum(counts)} in all.">'
            f'<div class="pa-line-chart__y">{ticks}</div><div class="pa-line-chart__plot"><svg class="pa-line-chart__svg" viewBox="0 0 100 {HH}" preserveAspectRatio="none" aria-hidden="true">'
            f'{grid}<line class="pa-line-chart__base" x1="0" x2="100" y1="{HH}" y2="{HH}"/><path class="pa-line-chart__area" d="{area}"/><path class="pa-line-chart__line" d="{line}"/></svg>{marks}{hover}</div>'
            f'<div class="pa-line-chart__x">{xs}</div></div>')
def heatmap():
    import random; random.seed(7)
    cats=[("Enforcement action","gavel",[0,1,2,1,3,2,4,1,2,3,5,2,3,4,1,2,6,3,2,8]),
          ("Advertising ruling","campaign",[1,0,1,2,0,1,1,3,1,0,2,1,1,0,2,4,1,2,1,2]),
          ("AML and compliance failures","account_balance",[0,0,1,0,0,2,0,1,0,0,1,3,0,1,0,0,2,1,0,1]),
          ("Licence change","label",[2,1,0,0,1,0,0,0,1,1,0,0,1,0,0,1,0,0,1,0]),
          ("Market entry","trending_up",[0,0,0,1,0,0,1,0,0,0,0,1,0,0,2,0,0,1,0,0])]
    step=lambda c: 0 if c==0 else 1 if c==1 else 2 if c==2 else 3 if c<=4 else 4 if c<=7 else 5
    weeks=len(cats[0][2]); mon=["Jun","","","","Jul","","","","","Aug","","","","Sep","","","","Oct","",""]
    head='<div class="pa-heat-map__row" aria-hidden="true"><span></span>'+"".join(f'<span class="pa-heat-map__month">{m}</span>' for m in mon)+'<span></span></div>'
    rows=""
    for name,ic,cs in cats:
        cells="".join(f'<span class="pa-heat-map__cell" role="cell" data-step="{step(c)}" aria-label="{name}: {c} signals" title="{c}"></span>' for c in cs)
        rows+=f'<div class="pa-heat-map__row" role="row"><span class="pa-heat-map__name" role="rowheader">{icon(ic)}{name}</span>{cells}<span class="pa-heat-map__total" role="cell">{sum(cs)}</span></div>'
    return f'<div class="pa-heat-map" role="table" aria-label="Signals per category by week" style="--weeks:{weeks}">{head}{rows}</div>'
def mover(ini,name,weekly,top,count,change):
    w=[int(x) for x in weekly.split(",")]; p=max(w) or 1; st=100/(len(w)-1)
    pts=" ".join(f"{i*st:.1f},{24-(c/p)*20:.1f}" for i,c in enumerate(w))
    arrow={"+":"▲ ","−":"▼ "}.get(change[0],"")
    return (f'<tr><td><span class="pa-ranked-table__name"><span class="pa-avatar pa-avatar--initials pa-avatar--xs">{ini}</span>{name}</span></td>'
            f'<td><svg class="pa-ranked-table__spark" viewBox="0 0 100 26" preserveAspectRatio="none" aria-hidden="true"><polyline points="{pts}"/></svg></td>'
            f'<td><span class="pa-meter pa-meter--bare">{ring(int(top))}<span class="pa-meter__value">{top}%</span></span></td>'
            f'<td class="is-num">{count}</td><td class="is-num"><span aria-hidden="true">{arrow}</span>{change}</td></tr>')
def bar(name,w,ic,word,counts):
    return (f'<li class="pa-bar-list__row"><span>{name}</span><span class="pa-bar-list__bar"><span style="width:calc({w}% - 3rem)"></span><b>{round(int(w)*2.14)}</b></span>'
            f'<span class="pa-bar-list__dir">{icon(ic)}{word} <span class="pa-bar-list__counts">{counts}</span></span></li>')

def sub(m):
    k, _, a = m.group(1).partition(":")
    if k=="icon": return icon(a)
    if k=="iconc": n,c=a.split(":"); return icon(n,c)
    if k=="sparkline": return sparkline([int(x) for x in a.split(",")])
    if k=="sparksvg": return sparksvg([int(x) for x in a.split(",")])
    if k=="meter": return meter(*a.split(":"))
    if k=="ring": return ring(int(a))
    if k=="linechart_plain": return re.sub(r'<span class="pa-line-chart__guide".*?</span></span>', "", linechart([int(x) for x in a.split(",")]), flags=re.S)
    if k=="empty": return empty(*a.split(":"))
    if k=="range": return rng(a)
    if k=="linechart": return linechart([int(x) for x in a.split(",")])
    if k=="heatmap": return heatmap()
    if k=="mover": return mover(*a.split(":"))
    if k=="bar": return bar(*a.split(":"))
    if k=="TOC":
        es=re.findall(r'<article class="cs-entry" id="e(\d+)" data-name="([^"]+)"', tpl)
        return "".join(f'<li><a href="#e{n}">{n}. {nm}</a></li>' for n,nm in es)
    raise SystemExit("unknown macro "+k)
res = re.sub(r"\{\{([^}]+)\}\}", sub, tpl)
out.write_text(res); print("wrote", out, len(res))
# screens.html: the same proposed recipes, composed into whole screens
st = S / "screens.tpl.html"
if st.exists():
    style = tpl[tpl.index("<style>") + len("<style>"):tpl.index("</style>")]
    page = st.read_text().replace("{{STYLE}}", style)
    page = re.sub(r"\{\{([^}]+)\}\}", sub, page)
    (S / "screens.html").write_text(page); print("wrote", S / "screens.html", len(page))
