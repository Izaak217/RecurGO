"""v1.2.0: self-contained, offline browser viewer for saved game analysis."""

# ruff: noqa: E501 -- Embedded HTML/CSS/JavaScript has its own layout and syntax.

from __future__ import annotations

import json


def render_report_html(data: dict[str, object]) -> str:
    """Embed a report without allowing its text to become HTML or executable JS."""
    if data.get("schemaVersion") != 1:
        raise ValueError("Unsupported analysis report schema")
    serialized = json.dumps(data, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    for character, escaped in (
        ("&", "\\u0026"), ("<", "\\u003c"), (">", "\\u003e"),
        ("\u2028", "\\u2028"), ("\u2029", "\\u2029"),
    ):
        serialized = serialized.replace(character, escaped)
    return _HTML.replace("__REPORT_JSON__", serialized)


_HTML = r'''<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; connect-src 'none'; base-uri 'none'; form-action 'none'">
<title>RecurGO · Analysis report</title>
<style>
:root{
  color-scheme:dark;
  --bg:#11171e;
  --panel:#1b2530;
  --panel2:#222f3d;
  --line:#354352;
  --text:#ecf1f6;
  --muted:#a7b7c7;
  --accent:#57d2bc;
  --blue:#70b7ff;
  --bad:#ff7c86;
  --wood:#dfb779}

*{
  box-sizing:border-box}
body{
  margin:0;
  background:var(--bg);
  color:var(--text);
  font:15px/1.5 system-ui,-apple-system,"Segoe UI","Microsoft YaHei",sans-serif}
button,input,select{
  font:inherit}
button,select,input[type=number]{
  background:var(--panel2);
  border:1px solid var(--line);
  border-radius:8px;
  color:var(--text);
  min-height:40px;
  padding:7px 12px}
button{
  cursor:pointer}
button:hover,button:focus-visible,select:focus-visible,input:focus-visible{
  outline:2px solid var(--accent);
  outline-offset:2px}
button:disabled{
  opacity:.35;
  cursor:default;
  outline:none}
button.active,button[aria-selected=true]{
  background:#174d46;
  color:#caffef;
  border-color:var(--accent)}
h1,h2,h3,p{
  margin:0}
h1{
  font-size:clamp(22px,3vw,32px);
  line-height:1.25;
  overflow-wrap:anywhere}
h2{
  font-size:18px}
h3{
  font-size:15px}
.app{
  max-width:1460px;
  margin:auto;
  padding:28px 26px 40px}
.header{
  display:flex;
  gap:20px;
  align-items:flex-start;
  justify-content:space-between;
  margin-bottom:22px}
.brand{
  font-weight:750;
  letter-spacing:.12em;
  font-size:12px;
  color:var(--accent);
  margin-bottom:7px}
.subtitle,.muted{
  color:var(--muted)}
.subtitle{
  margin-top:8px}
.card{
  background:var(--panel);
  border:1px solid var(--line);
  border-radius:15px;
  padding:18px;
  min-width:0}
.workspace{
  display:grid;
  grid-template-columns:minmax(300px,.95fr) minmax(380px,1.15fr);
  gap:18px;
  align-items:start}
.card-title{
  display:flex;
  gap:12px;
  align-items:center;
  justify-content:space-between;
  flex-wrap:wrap}
.badge{
  display:inline-block;
  padding:3px 9px;
  border-radius:20px;
  background:#304353;
  color:#d0e3ee;
  font-size:12px}
.badge.complete{
  background:#153f35;
  color:#9ce5c5}
.badge.partial{
  background:#493e25;
  color:#ffd88a}
.badge.missing{
  background:#3f3543;
  color:#e4c4e7}
.board-wrap{
  max-width:520px;
  margin:12px auto 8px}
.board{
  display:block;
  width:100%;
  height:auto;
  border-radius:9px;
  background:var(--wood);
  touch-action:manipulation}
.board text{
  pointer-events:none}
.board .candidate-point{
  cursor:pointer}
.board .candidate-point:focus{
  outline:none}
.board .candidate-point:focus circle{
  stroke:#fff;
  stroke-width:4}
.nav{
  display:flex;
  gap:8px;
  align-items:center;
  justify-content:center;
  flex-wrap:wrap}
.nav button{
  min-width:44px}
.nav input{
  width:82px;
  text-align:center}
.slider{
  width:100%;
  margin:14px 0 8px;
  accent-color:var(--accent)}
.branch{
  display:flex;
  gap:10px;
  align-items:center;
  margin-top:10px}
.branch select{
  flex:1;
  min-width:0}
.branch select:disabled{
  opacity:.6}
.small{
  font-size:12px}
.metric-row{
  display:grid;
  grid-template-columns:repeat(3,minmax(0,1fr));
  gap:9px;
  margin:14px 0}
.metric{
  background:var(--bg);
  border:1px solid #2b3948;
  padding:10px 12px;
  border-radius:10px}
.metric .label{
  font-size:12px;
  color:var(--muted)}
.metric .value{
  font-size:21px;
  font-weight:650;
  white-space:nowrap}
.position-help{
  font-size:13px;
  color:var(--muted);
  margin-top:8px}
.table-wrap{
  overflow:auto;
  max-width:100%;
  border:1px solid var(--line);
  border-radius:9px;
  margin-top:12px}
table{
  width:100%;
  border-collapse:collapse;
  font-size:13px}
th,td{
  padding:10px 11px;
  text-align:left;
  border-bottom:1px solid #34414f;
  white-space:nowrap}
th{
  color:var(--muted);
  font-weight:500;
  background:#18212b}
tbody tr:last-child td{
  border-bottom:none}
tbody tr.clickable{
  cursor:pointer}
tbody tr.clickable:hover,tbody tr.selected{
  background:#25443f}
td button{
  min-height:32px;
  padding:4px 8px;
  font-size:12px}
.best{
  color:var(--accent);
  font-weight:700}
.move-review{
  padding:12px 14px;
  border-left:3px solid var(--blue);
  background:#172431;
  border-radius:0 9px 9px 0;
  margin-top:14px;
  font-size:13px}
.pv{
  border:1px solid #478e7d;
  background:#17372f;
  border-radius:10px;
  padding:12px;
  margin-top:12px}
.pv .nav{
  margin-top:8px;
  justify-content:flex-start}
.pv-warning{
  color:#ffd88a}
.review-card{
  margin-top:18px}
.review-head{
  display:flex;
  gap:12px;
  align-items:center;
  justify-content:space-between;
  flex-wrap:wrap}
.scope{
  display:flex;
  gap:8px;
  align-items:center}
.tabs{
  display:flex;
  gap:4px;
  overflow:auto;
  border-bottom:1px solid var(--line);
  margin:16px 0}
.tabs button{
  border-radius:8px 8px 0 0;
  white-space:nowrap;
  border-bottom:0}
.panel[hidden], [hidden]{
  display:none!important}
.chart-toolbar{
  display:flex;
  align-items:center;
  gap:9px;
  flex-wrap:wrap;
  margin-bottom:8px}
.chart-toolbar label{
  font-size:13px;
  color:var(--muted);
  display:flex;
  align-items:center;
  gap:6px}
.chart-scroll{
  overflow-x:auto;
  overscroll-behavior-x:contain;
  max-width:100%;
  touch-action:pan-x pan-y}
.trend{
  display:block;
  min-width:100%;
  touch-action:pan-x pan-y}
.chart-detail{
  min-height:30px;
  color:var(--blue);
  font-size:13px;
  margin-top:7px}
.chart-note{
  font-size:12px;
  color:var(--muted);
  margin-top:4px}
.empty{
  padding:25px 14px;
  text-align:center;
  color:var(--muted)}
.quality-grid{
  display:grid;
  grid-template-columns:1fr 1fr;
  gap:20px}
.quality-side{
  border:1px solid var(--line);
  border-radius:10px;
  padding:14px}
.quality-side h3{
  margin-bottom:12px}
.bar-row{
  display:grid;
  grid-template-columns:85px 1fr 40px;
  gap:9px;
  align-items:center;
  margin:12px 0;
  font-size:13px}
.bar-track{
  background:#101820;
  border-radius:5px;
  overflow:hidden;
  height:13px}
.bar-fill{
  height:100%;
  border-radius:5px;
  background:var(--blue)}
.bar-row:nth-of-type(4) .bar-fill{
  background:#f4ca67}
.bar-row:nth-of-type(5) .bar-fill{
  background:#f69c69}
.bar-row:nth-of-type(6) .bar-fill{
  background:var(--bad)}
.summary-grid{
  display:grid;
  grid-template-columns:repeat(2,minmax(0,1fr));
  gap:12px}
.summary-box{
  background:var(--bg);
  border:1px solid var(--line);
  border-radius:10px;
  padding:13px}
.summary-box h3{
  margin-bottom:6px}
.summary-box p{
  font-size:13px;
  color:var(--muted);
  margin:3px 0}
.overview-list{
  display:grid;
  grid-template-columns:145px minmax(0,1fr);
  gap:9px 15px;
  margin:18px 0 0;
  font-size:13px}
.overview-list dt{
  color:var(--muted)}
.overview-list dd{
  margin:0;
  overflow-wrap:anywhere}
.footer{
  font-size:12px;
  color:var(--muted);
  padding-top:18px}
.good{
  color:#9ce5c5}
.problem{
  color:#ffbd94}
#match-body .streak{
  color:var(--accent)}
#language-select{
  min-width:90px}
.mobile-note{
  font-size:12px;
  color:var(--muted);
  margin-top:8px}
.num{
  font-variant-numeric:tabular-nums}

@media(max-width:800px){
  .app{
  padding:16px 12px 28px}
.workspace{
  grid-template-columns:1fr}
.card{
  padding:14px;
  border-radius:12px}
.header{
  gap:10px;
  margin-bottom:16px}
.board-wrap{
  max-width:490px}
.quality-grid{
  grid-template-columns:1fr}
.metric .value{
  font-size:19px}
.overview-list{
  grid-template-columns:105px minmax(0,1fr)}
.tabs button{
  padding:8px 10px}
.chart-toolbar select{
  padding:5px 8px}
.summary-grid{
  gap:8px}
.scope select{
  max-width:215px}
th,td{
  padding:9px}
.nav{
  gap:6px}
.branch{
  font-size:13px}
.card-title h2{
  font-size:17px}
.review-head h2{
  font-size:17px}
}

@media print{
  body{
  background:white;
  color:black}
.app{
  padding:0;
  max-width:none}
.card{
  background:white;
  border-color:#aaa;
  break-inside:avoid}
.tabs,.chart-toolbar,.nav,.slider,.branch,#language-select,.scope,.pv{
  display:none}
.panel[hidden]{
  display:block!important}
.panel{
  margin:20px 0}
.workspace{
  grid-template-columns:1fr 1fr}
.muted,.subtitle,.chart-note,.footer{
  color:#444}
.metric,.summary-box,th{
  background:#eee;
  color:#111}
.metric .label,th,.overview-list dt{
  color:#444}
.board-wrap{
  max-width:400px}
.table-wrap{
  overflow:visible}
.chart-scroll{
  overflow:visible}
.trend{
  width:100%!important}
}

</style>
<style>
.open-help{padding:24px;margin-bottom:24px;overflow-wrap:anywhere}
.open-help p{color:var(--muted);margin:12px 0}
[hidden]{display:none!important}
</style>
</head>
<body>
<div class="app">
<section id="open-help" class="card open-help" aria-labelledby="open-help-title">
<h2 id="open-help-title">这是一份交互式围棋报告 / Interactive Go report</h2>
<p>如果棋盘或按钮无法操作，请使用浏览器（如 Edge、Chrome）打开。</p>
<p>如果使用浏览器打开后仍无法操作，请检查浏览器是否已开启 JavaScript。</p>
<p>If the board or buttons do not respond, please open the report in a browser, such as Edge or Chrome.</p>
<p>If the report still does not respond after opening it in a browser, check whether JavaScript is enabled.</p>
</section>
<header class="header">
<div>
<div class="brand">RECURGO / GAME REPORT</div>
<h1 id="report-title">
</h1>
<p class="subtitle" id="game-subtitle">
</p>
</div>
<select id="language-select" aria-label="Language">
<option value="zh">中文</option>
<option value="en">English</option>
</select>
</header>
<main id="report-content" hidden>
<div class="workspace">
<section class="card" aria-labelledby="board-title">
<div class="card-title">
<h2 id="board-title" data-i18n="board">
</h2>
<span class="badge" id="position-label">
</span>
</div>
<div class="board-wrap">
<svg id="board" class="board" viewBox="0 0 620 620" role="img">
</svg>
</div>
<div class="nav">
<button id="first-move" data-i18n-title="first">|◀</button>
<button id="previous-move" data-i18n-title="previous">◀</button>
<input id="move-number" type="number" min="0" step="1" aria-label="Move number">
<span id="move-total" class="muted small">
</span>
<button id="next-move" data-i18n-title="next">▶</button>
<button id="last-move" data-i18n-title="last">▶|</button>
</div>
<input id="move-slider" class="slider" type="range" min="0" step="1" aria-label="Move navigation">
<div class="branch">
<label for="branch-select" data-i18n="branch">
</label>
<select id="branch-select">
</select>
</div>
<p id="board-detail" class="position-help">
</p>
</section>
<section class="card" aria-labelledby="candidate-heading">
<div class="card-title">
<h2 id="candidate-heading" data-i18n="candidates">
</h2>
<span id="position-status" class="badge">
</span>
</div>
<p class="position-help" id="candidate-context">
</p>
<div class="metric-row">
<div class="metric">
<div class="label" data-i18n="blackWinrate">
</div>
<div class="value num" id="black-winrate">
</div>
</div>
<div class="metric">
<div class="label" data-i18n="blackScore">
</div>
<div class="value num" id="black-score">
</div>
</div>
<div class="metric">
<div class="label" data-i18n="visits">
</div>
<div class="value num" id="position-visits">
</div>
</div>
</div>
<div class="table-wrap">
<table id="candidate-table">
<thead>
<tr>
<th data-i18n="rank">
</th>
<th data-i18n="point">
</th>
<th data-i18n="winrate">
</th>
<th data-i18n="score">
</th>
<th data-i18n="visits">
</th>
<th data-i18n="humanPolicy">
</th>
<th data-i18n="variation">
</th>
</tr>
</thead>
<tbody id="candidate-body">
</tbody>
</table>
</div>
<div id="pv-controls" class="pv" hidden>
<p id="pv-label">
</p>
<p id="pv-warning" class="small pv-warning">
</p>
<div class="nav">
<button id="pv-prev" data-i18n="pvPrevious">
</button>
<button id="pv-next" data-i18n="pvNext">
</button>
<button id="pv-exit" data-i18n="pvExit">
</button>
</div>
</div>
<div id="move-review" class="move-review">
</div>
<p class="mobile-note" data-i18n="savedOnly">
</p>
</section>
</div>
<section class="card review-card" aria-labelledby="review-title">
<div class="review-head">
<h2 id="review-title" data-i18n="fullReview">
</h2>
<div class="scope">
<label for="scope-select" data-i18n="scope">
</label>
<select id="scope-select">
<option value="all" data-i18n="whole">
</option>
<option value="opening" data-i18n="opening">
</option>
<option value="middle" data-i18n="middle">
</option>
<option value="endgame" data-i18n="endgame">
</option>
</select>
</div>
</div>
<div class="tabs" role="tablist" aria-label="Review sections">
<button id="tab-trend" role="tab" aria-controls="panel-trend" data-panel="trend" data-i18n="trend">
</button>
<button id="tab-quality" role="tab" aria-controls="panel-quality" data-panel="quality" data-i18n="quality">
</button>
<button id="tab-problems" role="tab" aria-controls="panel-problems" data-panel="problems" data-i18n="problems">
</button>
<button id="tab-match" role="tab" aria-controls="panel-match" data-panel="match" data-i18n="match">
</button>
<button id="tab-overview" role="tab" aria-controls="panel-overview" data-panel="overview" data-i18n="overview">
</button>
</div>
<div id="panel-trend" class="panel" role="tabpanel" aria-labelledby="tab-trend">
<div class="chart-toolbar">
<label>
<span data-i18n="horizontal">
</span>
<select id="zoom-x">
<option value="1">1×</option>
<option value="2">2×</option>
<option value="4">4×</option>
<option value="8">8×</option>
</select>
</label>
<label>
<span data-i18n="vertical">
</span>
<select id="zoom-y">
<option value="1">1×</option>
<option value="2">2×</option>
<option value="4">4×</option>
</select>
</label>
<button id="reset-zoom" data-i18n="reset">
</button>
</div>
<div id="trend-scroll" class="chart-scroll">
<svg id="trend-chart" class="trend" role="img">
</svg>
</div>
<div id="trend-detail" class="chart-detail" aria-live="polite">
</div>
<p class="chart-note" data-i18n="trendHelp">
</p>
</div>
<div id="panel-quality" class="panel" role="tabpanel" aria-labelledby="tab-quality" hidden>
<div id="quality-chart" class="quality-grid">
</div>
<p class="chart-note" data-i18n="completeOnly">
</p>
</div>
<div id="panel-problems" class="panel" role="tabpanel" aria-labelledby="tab-problems" hidden>
<p id="problem-summary" class="muted small">
</p>
<div class="table-wrap">
<table>
<thead>
<tr>
<th data-i18n="move">
</th>
<th data-i18n="side">
</th>
<th data-i18n="point">
</th>
<th data-i18n="grade">
</th>
<th data-i18n="winrateLoss">
</th>
<th data-i18n="scoreLoss">
</th>
<th data-i18n="goTo">
</th>
</tr>
</thead>
<tbody id="problem-body">
</tbody>
</table>
</div>
<p class="chart-note" data-i18n="completeOnly">
</p>
</div>
<div id="panel-match" class="panel" role="tabpanel" aria-labelledby="tab-match" hidden>
<div id="match-summary" class="summary-grid">
</div>
<div class="table-wrap">
<table>
<thead>
<tr>
<th data-i18n="move">
</th>
<th data-i18n="side">
</th>
<th data-i18n="point">
</th>
<th data-i18n="bestMove">
</th>
<th data-i18n="matchResult">
</th>
<th data-i18n="grade">
</th>
<th data-i18n="goTo">
</th>
</tr>
</thead>
<tbody id="match-body">
</tbody>
</table>
</div>
<p class="chart-note" data-i18n="completeOnly">
</p>
</div>
<div id="panel-overview" class="panel" role="tabpanel" aria-labelledby="tab-overview" hidden>
<div id="coverage-summary" class="summary-grid">
</div>
<div id="overview-side-summary" class="summary-grid" style="margin-top:12px">
</div>
<dl id="overview-content" class="overview-list">
</dl>
<p id="legacy-note" class="chart-note" hidden>
</p>
</div>
</section>
</main>
<footer class="footer" id="report-footer">
</footer>
</div>
<script id="report-data" type="application/json">__REPORT_JSON__</script>
<script>
'use strict';
(() => {
  const report=JSON.parse(document.getElementById('report-data').textContent);
  const nodes=report.nodes, game=report.game, source=report.source, $=id=>document.getElementById(id);
  let language=report.language==='en'?'en':'zh',activeTab='trend',scope='all',pv=null,pvStep=0;
  const text={
    zh:{
      board:'逐手棋盘',candidates:'当前局面 · 下一手候选',branch:'变化路线',black:'黑方',white:'白方',move:'手数',side:'行棋方',point:'落点',rank:'顺位',winrate:'胜率',score:'目差',visits:'访问量',humanPolicy:'人类偏好',variation:'参考变化',viewPV:'查看',noPV:'未保存',blackWinrate:'黑方胜率',blackScore:'黑方目差',fullReview:'全盘复盘',scope:'范围',whole:'全盘',opening:'布局（1–60 手）',middle:'中盘（61–160 手）',endgame:'官子（161 手后）',trend:'胜率走势',quality:'着法质量',problems:'问题手',match:'吻合度',overview:'总览',horizontal:'横向',vertical:'纵向',reset:'还原',first:'第一手 / 初始局面',previous:'上一手',next:'下一手',last:'最后一手',initial:'初始局面',position:'第 {n} 手后',toPlay:'下一手：{side}。候选胜率与目差采用{side}视角。',complete:'分析完成',partial:'分析未完成',winrateOnly:'仅保存胜率',missing:'尚无分析',emptyCandidates:'此局面尚无可用的已保存候选。',savedOnly:'仅查看导出时保存的分析；变化回放不会启动 AI 或计算新的胜率。',pvPrevious:'上一步',pvNext:'下一步',pvExit:'返回实战',pvLabel:'候选 {move} · 参考变化 {step}/{total} 步',pvTruncated:'已保存变化仅显示可合法回放的部分。',captures:'提子：黑 {black} · 白 {white}',pass:'停一手',grade:'分类',winrateLoss:'胜率损失（百分点）',scoreLoss:'目差损失（目）',goTo:'查看局面',bestMove:'AI 首选',matchResult:'吻合',topMatch:'首选吻合',threeMatch:'前三吻合',noMatch:'未吻合',reviewTitle:'本手评价',reviewInitial:'初始局面尚无实战落子评价。',reviewMissing:'本手分析不完整，暂不判定着法等级。',reviewText:'{side} {move} · {grade} · 胜率损失 {loss} 个百分点 · 目差损失 {score} 目 · AI 首选 {best}',trendHelp:'点击或轻触曲线跳到对应手数；缺失分析处断开，空心点表示未完成分析。',trendDetail:'第 {n} 手 · 黑方胜率 {winrate} · {status}',completeOnly:'着法统计仅包含落子前后分析均完整的棋步；未分析棋步不会被计为“正常”。',noReviews:'当前范围暂无完整着法评价。',noProblems:'当前范围暂无已确认的问题手。',problemSummary:'黑方问题手 {black} · 白方问题手 {white}',analyzedMoves:'完整评价 {n} 手',bestRate:'首选吻合率 {rate}',threeRate:'前三吻合率 {rate}',streak:'最长连续好手 {n} 手',good:'好手',normal:'正常',dubious:'疑问手',bad:'坏手',blunder:'严重失误',completePositions:'完整分析局面',visibleWinrates:'已有胜率局面',reviewedMoves:'完整着法评价',scopePositions:'当前路线与范围',engine:'分析引擎',budget:'目标访问量 / 局面',rules:'规则',komi:'贴目',blackKomi:'黑贴 {n} 目',whiteKomi:'白贴 {n} 目',noKomi:'不贴目',players:'对局者',result:'结果',unknown:'未记录',mainLine:'主线',variationLine:'分支 {n}',lineMoves:'{label} · {n} 手',lineFork:' · 第 {n} 手 {move}',footer:'RecurGO {version} · 独立交互报告 · 无需联网或启动 RecurGO',legacy:'此报告使用旧版来源记录；无法完整核实当时的配置标识。',averageWinrate:'平均胜率损失 {n} 个百分点',averageScore:'平均目差损失 {n} 目',notFinished:'未记录结果',boardAria:'围棋棋盘，{size} 路，{position}',branchHelp:'只切换已保存的棋谱分支',positionVisits:'实际访问量',noPoints:'当前范围暂无胜率数据',reportTitle:'围棋分析报告'
    }
    ,
    en:{
      board:'Move-by-move board',candidates:'Current position · Next-move candidates',branch:'Variation',black:'Black',white:'White',move:'Move',side:'Player',point:'Point',rank:'Rank',winrate:'Win rate',score:'Score lead',visits:'Visits',humanPolicy:'Human policy',variation:'Saved PV',viewPV:'View',noPV:'Not saved',blackWinrate:'Black win rate',blackScore:'Black score lead',fullReview:'Full-game review',scope:'Scope',whole:'Whole game',opening:'Opening (moves 1–60)',middle:'Middle game (61–160)',endgame:'Endgame (161 onward)',trend:'Win-rate trend',quality:'Move quality',problems:'Problem moves',match:'Match rate',overview:'Overview',horizontal:'Horizontal',vertical:'Vertical',reset:'Reset',first:'First / initial position',previous:'Previous move',next:'Next move',last:'Last move',initial:'Initial position',position:'After move {n}',toPlay:'Next: {side}. Candidate win rates and scores are from {side}’s perspective.',complete:'Analysis complete',partial:'Analysis incomplete',winrateOnly:'Win rate only',missing:'Not analyzed',emptyCandidates:'No usable saved candidates for this position.',savedOnly:'Saved analysis only. PV playback does not start an AI or calculate new evaluations.',pvPrevious:'Previous step',pvNext:'Next step',pvExit:'Return to game',pvLabel:'Candidate {move} · Saved PV {step}/{total}',pvTruncated:'Only the legally replayable part of the saved PV is shown.',captures:'Captures: Black {black} · White {white}',pass:'Pass',grade:'Grade',winrateLoss:'Win-rate loss (pp)',scoreLoss:'Score loss (points)',goTo:'View position',bestMove:'AI top move',matchResult:'Match',topMatch:'Top move',threeMatch:'Top three',noMatch:'No match',reviewTitle:'Played move',reviewInitial:'The initial position has no played-move evaluation.',reviewMissing:'Analysis for this move is incomplete; no grade is assigned.',reviewText:'{side} {move} · {grade} · Win-rate loss {loss} pp · Score loss {score} · AI top move {best}',trendHelp:'Click or tap the chart to jump to a move. Gaps mean missing data; hollow points mean incomplete analysis.',trendDetail:'Move {n} · Black win rate {winrate} · {status}',completeOnly:'Move statistics include only moves with complete analysis before and after. Missing analysis is never counted as “Normal”.',noReviews:'No complete move evaluations in this scope.',noProblems:'No confirmed problem moves in this scope.',problemSummary:'Black problem moves {black} · White problem moves {white}',analyzedMoves:'{n} fully evaluated moves',bestRate:'Top-move match {rate}',threeRate:'Top-three match {rate}',streak:'Longest good-move streak: {n}',good:'Good',normal:'Normal',dubious:'Dubious',bad:'Bad',blunder:'Blunder',completePositions:'Fully analyzed positions',visibleWinrates:'Positions with win rates',reviewedMoves:'Fully evaluated moves',scopePositions:'Selected line and scope',engine:'Engine',budget:'Target visits / position',rules:'Rules',komi:'Komi',blackKomi:'Black gives {n} points',whiteKomi:'White gives {n} points',noKomi:'No komi',players:'Players',result:'Result',unknown:'Not recorded',mainLine:'Main line',variationLine:'Variation {n}',lineMoves:'{label} · {n} moves',lineFork:' · Move {n}: {move}',footer:'RecurGO {version} · Standalone interactive report · No network or running RecurGO needed',legacy:'This report uses legacy source records; the original configuration identity cannot be fully verified.',averageWinrate:'Average win-rate loss: {n} pp',averageScore:'Average score loss: {n} points',notFinished:'Result not recorded',boardAria:'{size}×{size} Go board, {position}',branchHelp:'Switch between saved game variations',positionVisits:'Actual visits',noPoints:'No win-rate data in this scope',reportTitle:'Go analysis report'
    }
  }
  ;
  function t(key,values={
  }
  ){
    let value=text[language][key]||key;
    for(const [name,replacement]of Object.entries(values))value=value.replaceAll('{'+name+'}',String(replacement));
    return value;
  }
  const number=(value,digits=1)=>typeof value==='number'&&Number.isFinite(value)?value.toFixed(digits):'—';
  const percent=value=>typeof value==='number'&&Number.isFinite(value)?number(value)+'%':'—';
  const side=color=>t(color==='W'?'white':'black');
  const moveName=move=>String(move).toLowerCase()==='pass'?t('pass'):String(move||'—');
  const gradeKeys={
    '好手':'good','正常':'normal','疑问手':'dubious','坏手':'bad','严重失误':'blunder'
  }
  ;
  const gradeName=grade=>gradeKeys[grade]?t(gradeKeys[grade]):'—';
  const grades=Object.keys(gradeKeys);
  const ns='http://www.w3.org/2000/svg';
  function element(tag,content,className){
    const e=document.createElement(tag);
    if(content!==undefined)e.textContent=String(content);
    if(className)e.className=className;
    return e;
  }
  function svgElement(tag,attrs={
  }
  ,content){
    const e=document.createElementNS(ns,tag);
    for(const [key,value]of Object.entries(attrs))e.setAttribute(key,String(value));
    if(content!==undefined)e.textContent=String(content);
    return e;
  }
  function put(id,value){
    $(id).textContent=String(value);
  }
  // v1.2.0.dev2: show game rules and compensation in reader-facing language.
  function ruleName(){
    const names={
      chinese:['中国规则','Chinese rules'],
      'chinese-ogs':['中国规则（OGS）','Chinese rules (OGS)'],
      japanese:['日本规则','Japanese rules'],
      korean:['韩国规则','Korean rules'],
      aga:['美国围棋协会（AGA）规则','American Go Association (AGA) rules'],
      'tromp-taylor':['Tromp–Taylor 规则','Tromp–Taylor rules'],
      'new-zealand':['新西兰规则','New Zealand rules']
    };
    const raw=String(game.rules||'').trim(),key=raw.toLowerCase();
    const name=Object.hasOwn(names,key)?names[key]:null;
    return name?name[language==='zh'?0:1]:raw||t('unknown');
  }
  function komiDescription(){
    if(!Number.isFinite(game.komi))return t('unknown');
    if(game.komi===0)return t('noKomi');
    return t(game.komi>0?'blackKomi':'whiteKomi',{n:Math.abs(game.komi)});
  }
  function pathTo(id){
    const path=[],seen=new Set();
    while(id!==null&&nodes[id]&&!seen.has(id)){
      seen.add(id);
      path.unshift(id);
      id=nodes[id].parentId;
    }
    return path;
  }
  function pathThrough(id){
    const path=pathTo(id),seen=new Set(path);
    while(path.length){
      const children=nodes[path[path.length-1]].children||[],next=children.find(value=>nodes[value]&&!seen.has(value));
      if(!next)break;
      seen.add(next);
      path.push(next);
    }
    return path;
  }
  const mainLine=pathThrough(report.rootId);
  let line=Array.isArray(report.defaultLine)&&report.defaultLine.length?report.defaultLine.filter(id=>nodes[id]):mainLine;
  if(!line.length)line=mainLine;
  let currentId=line.includes(report.currentId)?report.currentId:line[0];
  const leaves=Object.values(nodes).filter(n=>!(n.children||[]).some(id=>nodes[id]));
  function current(){
    return nodes[currentId];
  }
  function inScope(n){
    return scope==='all'||(scope==='opening'&&n.moveNumber>=1&&n.moveNumber<=60)||(scope==='middle'&&n.moveNumber>=61&&n.moveNumber<=160)||(scope==='endgame'&&n.moveNumber>=161);
  }
  function scopedNodes(){
    return line.map(id=>nodes[id]).filter(inScope);
  }
  function fullReviews(){
    return scopedNodes().filter(n=>n.review&&n.review.complete&&gradeKeys[n.review.grade]);
  }
  function analysisStatus(n){
    return n.analysis?n.analysis.status:'missing';
  }
  function positionName(n){
    return n.parentId===null?t('initial'):t('position',{
      n:n.moveNumber
    }
    );
  }
  function candidates(){
    const items=current().analysis?.candidates||[];
    return items.length&&items[0].order===0?items:[];
  }
  function clearPV(){
    pv=null;
    pvStep=0;
  }
  function navigate(id){
    if(!nodes[id])return;
    if(!line.includes(id))line=pathThrough(id);
    currentId=id;
    clearPV();
    render();
  }
  function navigateIndex(index){
    navigate(line[Math.max(0,Math.min(line.length-1,index))]);
  }
  function byMove(value){
    const wanted=Number(value);
    if(!Number.isFinite(wanted))return;
    let closest=0;
    for(let i=1;
    i<line.length;
    i++)if(Math.abs(nodes[line[i]].moveNumber-wanted)<Math.abs(nodes[line[closest]].moveNumber-wanted))closest=i;
    navigateIndex(closest);
  }
  function gtpPoint(move){
    if(!move||String(move).toLowerCase()==='pass')return null;
    const match=/^([A-HJ-Z])(\d+)$/i.exec(move);
    if(!match)return null;
    const x='ABCDEFGHJKLMNOPQRSTUVWXYZ'.indexOf(match[1].toUpperCase()),y=game.size-Number(match[2]);
    return x>=0&&x<game.size&&y>=0&&y<game.size?{
      x,y
    }
    :null;
  }
  function renderBoard(){
    const n=current(), frame=pv&&pvStep>0?pv.pv[pvStep-1]:null,stones=frame?frame.stones:n.stones,svg=$('board'),size=game.size,step=560/(size-1),start=30;
    svg.replaceChildren();
    svg.setAttribute('aria-label',t('boardAria',{
      size,position:positionName(n)
    }
    ));
    svg.append(svgElement('rect',{
      x:0,y:0,width:620,height:620,fill:'#dfb779'
    }
    ));
    for(let i=0;
    i<size;
    i++){
      const p=start+i*step;
      svg.append(svgElement('line',{
        x1:start,y1:p,x2:590,y2:p,stroke:'#60482c','stroke-width':1.1
      }
      ));
      svg.append(svgElement('line',{
        x1:p,y1:start,x2:p,y2:590,stroke:'#60482c','stroke-width':1.1
      }
      ));
      const font=Math.min(14,step*.45);
      svg.append(svgElement('text',{
        x:p,y:611,'text-anchor':'middle',fill:'#57402a','font-size':font
      }
      ,'ABCDEFGHJKLMNOPQRSTUVWXYZ'[i]));
      svg.append(svgElement('text',{
        x:12,y:p+font*.32,'text-anchor':'middle',fill:'#57402a','font-size':font
      }
      ,size-i));
    }
    const edge=size>=13?3:2,center=(size-1)/2;
    const stars=size===19?[edge,center,size-1-edge]:[edge,size-1-edge];
    for(const x of stars)for(const y of stars)svg.append(svgElement('circle',{
      cx:start+x*step,cy:start+y*step,r:Math.max(2.5,step*.09),fill:'#60482c'
    }
    ));
    if(size!==19&&Number.isInteger(center))svg.append(svgElement('circle',{
      cx:start+center*step,cy:start+center*step,r:Math.max(2.5,step*.09),fill:'#60482c'
    }
    ));
    (stones||[]).forEach((stone,i)=>{
      if(stone!==1&&stone!==2)return;
      const x=i%size,y=Math.floor(i/size);
      svg.append(svgElement('circle',{
        cx:start+x*step,cy:start+y*step,r:step*.455,fill:stone===1?'#181b20':'#faf9f5',stroke:stone===1?'#05070a':'#b5b4ae','stroke-width':1.4
      }
      ));
    }
    );
    const last=frame?frame.lastMove:gtpPoint(n.move);
    if(last)svg.append(svgElement('circle',{
      cx:start+last.x*step,cy:start+last.y*step,r:step*.17,fill:'none',stroke:'#f06d5e','stroke-width':2.5
    }
    ));
    if(!pv)candidates().forEach((c,index)=>{
      if(!Number.isInteger(c.x)||!Number.isInteger(c.y))return;
      const group=svgElement('g',{
        class:'candidate-point',tabindex:0,role:'button','aria-label':t('variation')+' '+moveName(c.move),'data-candidate':index
      }
      );
      group.append(svgElement('circle',{
        cx:start+c.x*step,cy:start+c.y*step,r:step*.41,fill:index===0?'#168a76':'#2869a7',stroke:'#d3fff2','stroke-width':1.5
      }
      ));
      group.append(svgElement('text',{
        x:start+c.x*step,y:start+c.y*step+step*.14,'text-anchor':'middle','font-size':step*.44,'font-weight':700,fill:'#fff'
      }
      ,c.order+1));
      group.onclick=()=>showPV(index);
      group.onkeydown=e=>{
        if(e.key==='Enter'||e.key===' '){
          e.preventDefault();
          showPV(index);
        }
      }
      ;
      svg.append(group);
    }
    );
    put('board-detail',frame?t('pvLabel',{
      move:moveName(pv.move),step:pvStep,total:pv.pv.length
    }
    ):t('captures',{
      black:n.blackCaptures,white:n.whiteCaptures
    }
    ));
  }
  function renderNavigation(){
    const n=current(),index=line.indexOf(currentId);
    put('position-label',positionName(n));
    $('move-number').min=nodes[line[0]].moveNumber;
    $('move-number').max=nodes[line[line.length-1]].moveNumber;
    $('move-number').value=n.moveNumber;
    put('move-total','/ '+nodes[line[line.length-1]].moveNumber);
    $('move-slider').max=line.length-1;
    $('move-slider').value=index;
    for(const id of ['first-move','previous-move'])$(id).disabled=index===0;
    for(const id of ['next-move','last-move'])$(id).disabled=index===line.length-1;
    const branch=$('branch-select');
    branch.replaceChildren();
    leaves.forEach((leaf,index)=>{
      const path=pathTo(leaf.id),main=leaf.id===mainLine[mainLine.length-1];
      let label=t('lineMoves',{
        label:main?t('mainLine'):t('variationLine',{
          n:index+1
        }
        ),n:leaf.moveNumber
      }
      );
      if(!main){
        const fork=path.find((id,i)=>mainLine[i]!==id);
        if(fork)label+=t('lineFork',{
          n:nodes[fork].moveNumber,move:moveName(nodes[fork].move)
        }
        );
      }
      const option=element('option',label);
      option.value=leaf.id;
      branch.append(option);
    }
    );
    branch.value=line[line.length-1];
    branch.disabled=leaves.length<=1;
    branch.title=t('branchHelp');
  }
  function showPV(index){
    const candidate=candidates()[index];
    if(!candidate)return;
    if(!candidate.pv?.length){
      put('candidate-context',t('noPV')+' · '+moveName(candidate.move));
      return;
    }
    pv=candidate;
    pvStep=1;
    renderBoard();
    renderCandidates();
  }
  function renderCandidates(){
    const n=current(),a=n.analysis,status=analysisStatus(n);
    put('candidate-context',t('toPlay',{
      side:side(n.toPlay)
    }
    ));
    put('black-winrate',percent(a?.blackWinrate));
    put('black-score',number(a?.blackScoreLead));
    put('position-visits',a&&Number.isFinite(a.visits)?a.visits.toLocaleString(language==='zh'?'zh-CN':'en-US'):'—');
    put('position-status',t(status));
    $('position-status').className='badge '+(status==='complete'?'complete':status==='partial'?'partial':'missing');
    const body=$('candidate-body');
    body.replaceChildren();
    const items=candidates();
    if(!items.length){
      const row=element('tr'),cell=element('td',t('emptyCandidates'),'empty');
      cell.colSpan=7;
      row.append(cell);
      body.append(row);
    }
    else items.forEach((c,index)=>{
      const row=element('tr',undefined,'clickable'+(pv===c?' selected':''));
      row.dataset.candidate=String(index);
      const rank=element('td',c.order+1,c.order===0?'best':'');
      row.append(rank,element('td',moveName(c.move)),element('td',percent(c.winrate)),element('td',number(c.scoreLead)),element('td',Number.isFinite(c.visits)?c.visits:'—'),element('td',percent(c.humanPolicy)));
      const cell=element('td'),button=element('button',c.pv?.length?t('viewPV'):t('noPV'));
      button.disabled=!c.pv?.length;
      button.onclick=e=>{
        e.stopPropagation();
        showPV(index);
      }
      ;
      cell.append(button);
      row.append(cell);
      row.onclick=()=>showPV(index);
      body.append(row);
    }
    );
    $('pv-controls').hidden=!pv;
    if(pv){
      put('pv-label',t('pvLabel',{
        move:moveName(pv.move),step:pvStep,total:pv.pv.length
      }
      ));
      put('pv-warning',pv.pvTruncated?t('pvTruncated'):'');
      $('pv-prev').disabled=pvStep===0;
      $('pv-next').disabled=pvStep===pv.pv.length;
    }
    const review=n.review;
    put('move-review',!n.parentId?t('reviewInitial'):!review?.complete?t('reviewMissing'):t('reviewTitle')+' · '+t('reviewText',{
      side:side(review.color),move:moveName(review.move),grade:gradeName(review.grade),loss:number(review.winrateLoss),score:number(review.scoreLoss),best:moveName(review.bestMove)
    }
    ));
  }
  function trendDetail(n){
    put('trend-detail',t('trendDetail',{
      n:n.moveNumber,winrate:percent(n.analysis?.blackWinrate),status:t(analysisStatus(n))
    }
    ));
  }
  function renderTrend(){
    const svg=$('trend-chart'),scroll=$('trend-scroll'),list=scopedNodes(),width=Math.max(300,scroll.clientWidth||600)*Number($('zoom-x').value),height=270,left=46,right=18,top=16,bottom=38,chartW=width-left-right,chartH=height-top-bottom;
    svg.replaceChildren();
    svg.style.width=width+'px';
    svg.style.height=height+'px';
    svg.setAttribute('viewBox','0 0 '+width+' '+height);
    svg.setAttribute('aria-label',t('trend')+' · '+t('blackWinrate'));
    const zoom=Number($('zoom-y').value),range=100/zoom,rawCenter=current().analysis?.blackWinrate,center=Math.min(100-range/2,Math.max(range/2,Number.isFinite(rawCenter)?rawCenter:50)),low=center-range/2,high=center+range/2;
    const first=list.length?list[0].moveNumber:0,last=list.length?list[list.length-1].moveNumber:first+1;
    const x=value=>left+(value-first)/Math.max(1,last-first)*chartW,y=value=>top+(high-value)/range*chartH;
    for(let i=0;
    i<=4;
    i++){
      const v=low+range*i/4,p=y(v);
      svg.append(svgElement('line',{
        x1:left,y1:p,x2:width-right,y2:p,stroke:'#344352','stroke-width':1
      }
      ));
      svg.append(svgElement('text',{
        x:left-8,y:p+4,'text-anchor':'end',fill:'#a7b7c7','font-size':11
      }
      ,Math.round(v)+'%'));
    }
    const ticks=Math.max(2,Math.min(12,Math.floor(width/80)));
    for(let i=0;
    i<=ticks;
    i++){
      const value=Math.round(first+(last-first)*i/ticks),p=x(value);
      svg.append(svgElement('line',{
        x1:p,y1:top,x2:p,y2:height-bottom,stroke:'#293643','stroke-width':1
      }
      ));
      svg.append(svgElement('text',{
        x:p,y:height-17,'text-anchor':'middle',fill:'#a7b7c7','font-size':11
      }
      ,value));
    }
    const defs=svgElement('defs'),clip=svgElement('clipPath',{
      id:'trend-clip'
    }
    );
    clip.append(svgElement('rect',{
      x:left,y:top,width:chartW,height:chartH
    }
    ));
    defs.append(clip);
    svg.append(defs);
    const series=svgElement('g',{
      'clip-path':'url(#trend-clip)'
    }
    );
    svg.append(series);
    let previous=null;
    list.forEach(n=>{
      const value=n.analysis?.blackWinrate;
      if(!Number.isFinite(value)){
        previous=null;
        return;
      }
      const p={
        x:x(n.moveNumber),y:y(value)
      }
      ;
      if(previous)series.append(svgElement('line',{
        x1:previous.x,y1:previous.y,x2:p.x,y2:p.y,stroke:'#70b7ff','stroke-width':1.8
      }
      ));
      if(value>=low&&value<=high)series.append(svgElement('circle',{
        cx:p.x,cy:p.y,r:n.id===currentId?5:3.2,fill:n.analysis.status==='partial'?'#1b2530':'#7eacf5',stroke:n.id===currentId?'#57d2bc':'#b8d5ff','stroke-width':n.id===currentId?2.5:1,'data-node-id':n.id
      }
      ));
      previous=p;
    }
    );
    if(list.some(n=>n.id===currentId))svg.append(svgElement('line',{
      x1:x(current().moveNumber),y1:top,x2:x(current().moveNumber),y2:height-bottom,stroke:'#57d2bc','stroke-width':1,'stroke-dasharray':'4 4'
    }
    ));
    if(!list.some(n=>Number.isFinite(n.analysis?.blackWinrate)))svg.append(svgElement('text',{
      x:width/2,y:height/2,'text-anchor':'middle',fill:'#a7b7c7','font-size':14
    }
    ,t('noPoints')));
    const nodeAt=e=>{
      if(!list.length)return null;
      const bounds=svg.getBoundingClientRect(),local=(e.clientX-bounds.left)*width/bounds.width,wanted=first+(local-left)/chartW*(last-first);
      return list.reduce((best,n)=>Math.abs(n.moveNumber-wanted)<Math.abs(best.moveNumber-wanted)?n:best,list[0]);
    }
    ;
    svg.onclick=e=>{
      const n=nodeAt(e);
      if(n)navigate(n.id);
    }
    ;
    svg.onpointermove=e=>{
      if(e.pointerType==='mouse'){
        const n=nodeAt(e);
        if(n)trendDetail(n);
      }
    }
    ;
    svg.onpointerleave=()=>trendDetail(current());
    trendDetail(current());
  }
  function metrics(color,reviews){
    const subset=reviews.filter(n=>n.review.color===color),count=subset.length;
    let streak=0,longest=0;
    for(const n of scopedNodes().filter(n=>n.color===color)){
      streak=n.review?.complete&&n.review.grade==='好手'?streak+1:0;
      longest=Math.max(longest,streak);
    }
    const avg=key=>{
      const values=subset.map(n=>n.review[key]).filter(Number.isFinite);
      return values.length?values.reduce((a,b)=>a+b,0)/values.length:null;
    }
    ;
    return{
      count,best:count?100*subset.filter(n=>n.review.matchesBest).length/count:null,three:count?100*subset.filter(n=>n.review.matchesTopThree).length/count:null,longest,winrate:avg('winrateLoss'),score:avg('scoreLoss'),counts:Object.fromEntries(grades.map(g=>[g,subset.filter(n=>n.review.grade===g).length]))
    }
    ;
  }
  function renderQuality(reviews){
    const root=$('quality-chart');
    root.replaceChildren();
    for(const color of ['B','W']){
      const stats=metrics(color,reviews),box=element('div',undefined,'quality-side');
      box.append(element('h3',side(color)+' · '+t('analyzedMoves',{
        n:stats.count
      }
      )));
      const max=Math.max(1,...Object.values(stats.counts));
      for(const g of grades){
        const row=element('div',undefined,'bar-row'),track=element('div',undefined,'bar-track'),bar=element('div',undefined,'bar-fill');
        bar.style.width=(100*stats.counts[g]/max)+'%';
        track.append(bar);
        row.append(element('span',gradeName(g)),track,element('span',stats.counts[g],'num'));
        box.append(row);
      }
      root.append(box);
    }
  }
  function addJump(row,node){
    const cell=element('td'),button=element('button',t('goTo'));
    button.dataset.nodeId=node.id;
    button.onclick=e=>{
      e.stopPropagation();
      navigate(node.id);
      $('board-title').scrollIntoView({
        behavior:'smooth',block:'start'
      }
      );
    }
    ;
    cell.append(button);
    row.append(cell);
    row.className='clickable'+(node.id===currentId?' selected':'');
    row.onclick=()=>navigate(node.id);
    row.dataset.nodeId=node.id;
  }
  function emptyRow(body,message,columns){
    const row=element('tr'),cell=element('td',message,'empty');
    cell.colSpan=columns;
    row.append(cell);
    body.append(row);
  }
  function renderProblems(reviews){
    const list=reviews.filter(n=>['疑问手','坏手','严重失误'].includes(n.review.grade)),body=$('problem-body');
    body.replaceChildren();
    put('problem-summary',t('problemSummary',{
      black:list.filter(n=>n.review.color==='B').length,white:list.filter(n=>n.review.color==='W').length
    }
    ));
    for(const n of list){
      const r=n.review,row=element('tr');
      row.append(element('td',n.moveNumber),element('td',side(r.color)),element('td',moveName(r.move)),element('td',gradeName(r.grade),'problem'),element('td',number(r.winrateLoss)),element('td',number(r.scoreLoss)));
      addJump(row,n);
      body.append(row);
    }
    if(!list.length)emptyRow(body,t('noProblems'),7);
  }
  function renderMatch(reviews){
    const summary=$('match-summary'),body=$('match-body');
    summary.replaceChildren();
    body.replaceChildren();
    for(const color of ['B','W']){
      const m=metrics(color,reviews),box=element('div',undefined,'summary-box');
      box.append(element('h3',side(color)),element('p',t('analyzedMoves',{
        n:m.count
      }
      )),element('p',t('bestRate',{
        rate:percent(m.best)
      }
      )),element('p',t('threeRate',{
        rate:percent(m.three)
      }
      )),element('p',t('streak',{
        n:m.longest
      }
      )));
      summary.append(box);
    }
    for(const n of reviews){
      const r=n.review,row=element('tr');
      row.append(element('td',n.moveNumber),element('td',side(r.color)),element('td',moveName(r.move)),element('td',moveName(r.bestMove)),element('td',t(r.matchesBest?'topMatch':r.matchesTopThree?'threeMatch':'noMatch'),r.matchesBest?'good':''),element('td',gradeName(r.grade),r.grade==='好手'?'streak':''));
      addJump(row,n);
      body.append(row);
    }
    if(!reviews.length)emptyRow(body,t('noReviews'),7);
  }
  function renderOverview(reviews){
    const positions=scopedNodes(),complete=positions.filter(n=>n.analysis?.status==='complete').length,withRate=positions.filter(n=>Number.isFinite(n.analysis?.blackWinrate)).length,moves=positions.filter(n=>n.parentId!==null).length;
    const cover=$('coverage-summary');
    cover.replaceChildren();
    for(const [key,value]of [['completePositions',complete+' / '+positions.length],['visibleWinrates',withRate+' / '+positions.length],['reviewedMoves',reviews.length+' / '+moves],['scopePositions',$('scope-select').selectedOptions[0].textContent]]){
      const box=element('div',undefined,'summary-box');
      box.append(element('p',t(key)),element('h3',value));
      cover.append(box);
    }
    const summaries=$('overview-side-summary');
    summaries.replaceChildren();
    for(const color of ['B','W']){
      const m=metrics(color,reviews),box=element('div',undefined,'summary-box');
      box.append(element('h3',side(color)),element('p',grades.map(g=>gradeName(g)+' '+m.counts[g]).join(' · ')),element('p',t('averageWinrate',{
        n:number(m.winrate)
      }
      )),element('p',t('averageScore',{
        n:number(m.score)
      }
      )));
      summaries.append(box);
    }
    const details=$('overview-content');
    details.replaceChildren();
    const entries=[['players',(game.blackPlayer||t('unknown'))+' / '+(game.whitePlayer||t('unknown'))],['rules',ruleName()],['komi',komiDescription()],['result',game.result||t('notFinished')],['engine',source.engineVersion||t('unknown')],['budget',source.maxVisits]];
    for(const [key,value]of entries)details.append(element('dt',t(key)),element('dd',value));
    $('legacy-note').hidden=!source.legacy;
    put('legacy-note',t('legacy'));
  }
  function renderTabs(){
    document.querySelectorAll('[data-panel]').forEach(button=>{
      const active=button.dataset.panel===activeTab;
      button.setAttribute('aria-selected',String(active));
      $('panel-'+button.dataset.panel).hidden=!active;
    }
    );
  }
  function render(){
    document.documentElement.lang=language==='zh'?'zh-CN':'en';
    document.querySelectorAll('[data-i18n]').forEach(e=>e.textContent=t(e.dataset.i18n));
    document.querySelectorAll('[data-i18n-title]').forEach(e=>{
      e.title=t(e.dataset.i18nTitle);
      e.setAttribute('aria-label',e.title);
    }
    );
    $('language-select').value=language;
    put('report-title',game.name||t('reportTitle'));
    document.title=(game.name||t('reportTitle'))+' · RecurGO';
    put('game-subtitle',game.size+' × '+game.size+' · '+(game.blackPlayer||side('B'))+' / '+(game.whitePlayer||side('W'))+' · '+(game.result||t('notFinished')));
    put('report-footer',t('footer',{
      version:report.appVersion
    }
    ));
    renderNavigation();
    renderBoard();
    renderCandidates();
    renderTabs();
    if(activeTab==='trend')renderTrend();
    const reviews=fullReviews();
    renderQuality(reviews);
    renderProblems(reviews);
    renderMatch(reviews);
    renderOverview(reviews);
  }
  $('first-move').onclick=()=>navigateIndex(0);
  $('last-move').onclick=()=>navigateIndex(line.length-1);
  $('previous-move').onclick=()=>navigateIndex(line.indexOf(currentId)-1);
  $('next-move').onclick=()=>navigateIndex(line.indexOf(currentId)+1);
  $('move-slider').oninput=e=>navigateIndex(Number(e.target.value));
  $('move-number').onchange=e=>byMove(e.target.value);
  $('branch-select').onchange=e=>{
    const oldMove=current().moveNumber;
    line=pathTo(e.target.value);
    byMove(oldMove);
  }
  ;
  $('pv-prev').onclick=()=>{
    pvStep=Math.max(0,pvStep-1);
    renderBoard();
    renderCandidates();
  }
  ;
  $('pv-next').onclick=()=>{
    pvStep=Math.min(pv.pv.length,pvStep+1);
    renderBoard();
    renderCandidates();
  }
  ;
  $('pv-exit').onclick=()=>{
    clearPV();
    renderBoard();
    renderCandidates();
  }
  ;
  $('language-select').onchange=e=>{
    language=e.target.value;
    render();
  }
  ;
  $('scope-select').onchange=e=>{
    scope=e.target.value;
    render();
  }
  ;
  $('zoom-x').onchange=renderTrend;
  $('zoom-y').onchange=renderTrend;
  $('reset-zoom').onclick=()=>{
    $('zoom-x').value='1';
    $('zoom-y').value='1';
    $('trend-scroll').scrollLeft=0;
    renderTrend();
  }
  ;
  document.querySelectorAll('[data-panel]').forEach(button=>button.onclick=()=>{
    activeTab=button.dataset.panel;
    renderTabs();
    if(activeTab==='trend')renderTrend();
  }
  );
  document.addEventListener('keydown',e=>{
    if(e.target.closest('input,select,textarea,button,[contenteditable=true]'))return;
    if(e.key==='ArrowLeft'||e.key==='ArrowRight'){
      e.preventDefault();
      if(pv){
        pvStep=Math.max(0,Math.min(pv.pv.length,pvStep+(e.key==='ArrowRight'?1:-1)));
        renderBoard();
        renderCandidates();
      }
      else navigateIndex(line.indexOf(currentId)+(e.key==='ArrowRight'?1:-1));
    }
  }
  );
  let resizeTimer;
  window.addEventListener('resize',()=>{
    clearTimeout(resizeTimer);
    resizeTimer=setTimeout(()=>{
      if(activeTab==='trend')renderTrend();
    }
    ,80);
  }
  );
  try{
    $('report-content').hidden=false;
    render();
    $('open-help').hidden=true;
  }catch(error){
    $('report-content').hidden=true;
    console.error(error);
  }
}
)();
</script>
</body></html>
'''
