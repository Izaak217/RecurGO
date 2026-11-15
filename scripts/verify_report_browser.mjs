/**
 * v1.2.0.dev1: exercise an exported report with an isolated, offline Chrome.
 * Usage: node scripts/verify_report_browser.mjs report.html [new-output-directory]
 * No dependencies, downloads, user browser profiles, or output cleanup.
 */
import {spawn} from 'node:child_process';
import {mkdir, readFile, realpath, writeFile} from 'node:fs/promises';
import {dirname, isAbsolute, relative, resolve, sep} from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';

const projectRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const chromePath = process.env.RECURGO_QA_CHROME ||
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const wait = milliseconds => new Promise(done => setTimeout(done, milliseconds));

function assert(value, message) {
  if (!value) throw new Error(message);
}

function insideProject(path) {
  const child = relative(projectRoot, path);
  return child !== '' && !child.startsWith(`..${sep}`) && child !== '..' && !isAbsolute(child);
}

class CDP {
  constructor(socket) {
    this.socket = socket;
    this.sequence = 0;
    this.pending = new Map();
    this.handlers = new Map();
    socket.addEventListener('message', event => {
      const message = JSON.parse(event.data);
      if (message.id) {
        const command = this.pending.get(message.id);
        if (!command) return;
        this.pending.delete(message.id);
        clearTimeout(command.timeout);
        if (message.error) command.reject(new Error(JSON.stringify(message.error)));
        else command.resolve(message.result);
      } else {
        for (const handler of this.handlers.get(message.method) || []) {
          handler(message.params);
        }
      }
    });
    socket.addEventListener('close', () => {
      for (const command of this.pending.values()) {
        clearTimeout(command.timeout);
        command.reject(new Error('Chrome DevTools connection closed'));
      }
      this.pending.clear();
    });
  }

  static async connect(url) {
    const socket = new WebSocket(url);
    await new Promise((done, reject) => {
      const timer = setTimeout(() => reject(new Error('DevTools connection timed out')), 10000);
      socket.addEventListener('open', () => { clearTimeout(timer); done(); }, {once: true});
      socket.addEventListener('error', () => {
        clearTimeout(timer);
        reject(new Error('DevTools connection failed'));
      }, {once: true});
    });
    return new CDP(socket);
  }

  on(name, handler) {
    const handlers = this.handlers.get(name) || [];
    handlers.push(handler);
    this.handlers.set(name, handlers);
  }

  send(method, params = {}) {
    const id = ++this.sequence;
    return new Promise((resolveCommand, reject) => {
      const timeout = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error(`DevTools command timed out: ${method}`));
      }, 15000);
      this.pending.set(id, {resolve: resolveCommand, reject, timeout});
      this.socket.send(JSON.stringify({id, method, params}));
    });
  }

  async evaluate(expression) {
    const response = await this.send('Runtime.evaluate', {
      expression, returnByValue: true, awaitPromise: true, userGesture: true,
    });
    if (response.exceptionDetails) {
      throw new Error(response.exceptionDetails.exception?.description ||
        response.exceptionDetails.text);
    }
    return response.result?.value;
  }

  close() { this.socket.close(); }
}

async function main() {
  assert(process.argv[2], 'Provide the exported HTML path.');
  const input = await realpath(resolve(process.argv[2]));
  assert(insideProject(input), 'The QA report must be inside this project.');
  const stamp = `${new Date().toISOString().replace(/[:.]/g, '-')}-${process.pid}`;
  const output = resolve(process.argv[3] || resolve(projectRoot, 'build', `report-browser-${stamp}`));
  assert(insideProject(output), 'The QA output directory must be inside this project.');
  let ancestor = dirname(output);
  while (true) {
    try {
      const actual = await realpath(ancestor);
      assert(actual === projectRoot || insideProject(actual),
        'The QA output must not pass through a link outside this project.');
      break;
    } catch (error) {
      if (error.code !== 'ENOENT') throw error;
      ancestor = dirname(ancestor);
    }
  }
  await mkdir(dirname(output), {recursive: true});
  // Exclusive directory creation prevents overwriting a previous run or profile.
  await mkdir(output);
  const profile = resolve(output, 'chrome-profile');
  const temp = resolve(output, 'temp');
  const local = resolve(profile, 'AppData', 'Local');
  const roaming = resolve(profile, 'AppData', 'Roaming');
  await Promise.all([profile, temp, local, roaming].map(path => mkdir(path, {recursive: true})));
  const results = {
    report: input, output, browserExecutable: chromePath, startedAt: new Date().toISOString(),
    checks: [], skipped: [], exceptions: [], consoleErrors: [], externalRequests: [], screenshots: [],
  };
  let chrome;
  let page;
  let browser;
  let browserOutput = '';
  let browserError = '';
  try {
    chrome = spawn(chromePath, [
      '--headless=new', '--remote-debugging-port=0', `--user-data-dir=${profile}`,
      '--no-first-run', '--no-default-browser-check', '--disable-background-networking',
      '--disable-component-update', '--disable-sync', '--disable-default-apps',
      '--metrics-recording-only', '--disable-breakpad', '--disable-crash-reporter',
      '--window-size=1440,1000', 'about:blank',
    ], {
      cwd: output, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'],
      env: {...process.env, TEMP: temp, TMP: temp, USERPROFILE: profile,
        LOCALAPPDATA: local, APPDATA: roaming},
    });
    chrome.stdout.on('data', value => { browserOutput += value; });
    chrome.stderr.on('data', value => { browserError += value; });
    let spawnFailure;
    chrome.on('error', error => { spawnFailure = error; });
    let port;
    const deadline = Date.now() + 20000;
    while (!port && Date.now() < deadline) {
      if (spawnFailure) throw spawnFailure;
      if (chrome.exitCode !== null) throw new Error(`Chrome exited: ${chrome.exitCode}`);
      try {
        port = Number((await readFile(resolve(profile, 'DevToolsActivePort'), 'utf8')).split('\n')[0]);
      } catch {
        await wait(100);
      }
    }
    assert(port, 'Chrome did not expose its project-local DevTools port.');
    const version = await (await fetch(`http://127.0.0.1:${port}/json/version`)).json();
    browser = await CDP.connect(version.webSocketDebuggerUrl);
    results.browser = version.Browser;
    results.browserVersion = await browser.send('Browser.getVersion');
    const target = await (await fetch(`http://127.0.0.1:${port}/json/new?about:blank`, {
      method: 'PUT',
    })).json();
    page = await CDP.connect(target.webSocketDebuggerUrl);
    page.on('Runtime.exceptionThrown', event => {
      results.exceptions.push(event.exceptionDetails.exception?.description || event.exceptionDetails.text);
    });
    page.on('Runtime.consoleAPICalled', event => {
      if (event.type === 'error') {
        results.consoleErrors.push(event.args.map(arg => arg.value ?? arg.description ?? arg.type).join(' '));
      }
    });
    page.on('Network.requestWillBeSent', event => {
      if (/^https?:\/\//i.test(event.request.url)) results.externalRequests.push(event.request.url);
    });
    await page.send('Runtime.enable');
    await page.send('Page.enable');
    await page.send('Network.enable');
    await page.send('Network.setBlockedURLs', {urls: ['http://*', 'https://*']});
    await page.send('Network.emulateNetworkConditions', {
      offline: true, latency: 0, downloadThroughput: 0, uploadThroughput: 0,
    });
    await page.send('Emulation.setDeviceMetricsOverride', {
      width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false,
    });
    await page.send('Emulation.setScriptExecutionDisabled', {value: true});
    const navigation = await page.send('Page.navigate', {url: pathToFileURL(input).href});
    assert(!navigation.errorText, `File navigation failed: ${navigation.errorText}`);
    await until(page, 'document.readyState === "complete"', 'report document load');
    await verifyStaticHelp(page, results, output, false);
    await page.send('Emulation.setDeviceMetricsOverride', {
      width: 390, height: 844, deviceScaleFactor: 1, mobile: true,
    });
    await verifyStaticHelp(page, results, output, true);
    await page.send('Emulation.setDeviceMetricsOverride', {
      width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false,
    });
    await page.send('Emulation.setScriptExecutionDisabled', {value: false});
    await page.send('Page.reload', {ignoreCache: true});
    await until(page, `document.readyState === 'complete' &&
      document.getElementById('open-help')?.hidden &&
      document.getElementById('report-content')?.hidden === false`, 'report recovery after enabling JavaScript');
    results.checks.push('JavaScript restored: report visible and static opening help hidden');
    await wait(150);

    await exercise(page, results, output, false);
    await page.send('Emulation.setDeviceMetricsOverride', {
      width: 390, height: 844, deviceScaleFactor: 1, mobile: true,
    });
    await page.send('Emulation.setTouchEmulationEnabled', {enabled: true, maxTouchPoints: 5});
    await wait(150);
    await exercise(page, results, output, true);

    assert(results.exceptions.length === 0,
      `JavaScript exceptions: ${JSON.stringify(results.exceptions)}`);
    assert(results.consoleErrors.length === 0,
      `JavaScript console errors: ${JSON.stringify(results.consoleErrors)}`);
    assert(results.externalRequests.length === 0,
      `External network dependencies: ${JSON.stringify(results.externalRequests)}`);
    results.checks.push('no JavaScript exceptions or console errors', 'no external network requests', 'offline local file');
    results.passed = true;
  } catch (error) {
    results.passed = false;
    results.error = error.stack || String(error);
    if (page) {
      try { await screenshot(page, output, 'failure.png', results); } catch { /* Preserve original failure. */ }
    }
  } finally {
    if (browser) {
      try { await browser.send('Browser.close'); } catch { /* Chrome may close before answering. */ }
      browser.close();
    }
    if (page) page.close();
    if (chrome) {
      for (let attempt = 0; attempt < 30 && chrome.exitCode === null; attempt++) await wait(100);
      // This handle belongs exclusively to the child launched above, never an existing browser.
      if (chrome.exitCode === null) chrome.kill();
    }
    results.completedAt = new Date().toISOString();
    await writeFile(resolve(output, 'chrome.stdout.log'), browserOutput, {flag: 'wx'});
    await writeFile(resolve(output, 'chrome.stderr.log'), browserError, {flag: 'wx'});
    await writeFile(resolve(output, 'results.json'), JSON.stringify(results, null, 2), {flag: 'wx'});
    console.log(JSON.stringify(results, null, 2));
  }
  if (!results.passed) process.exitCode = 1;
}

async function until(page, expression, label) {
  for (let attempt = 0; attempt < 60; attempt++) {
    if (await page.evaluate(expression)) return;
    await wait(100);
  }
  throw new Error(`Timed out waiting for ${label}`);
}

async function screenshot(page, directory, name, results) {
  const image = await page.send('Page.captureScreenshot', {format: 'png', captureBeyondViewport: false});
  const path = resolve(directory, name);
  await writeFile(path, Buffer.from(image.data, 'base64'), {flag: 'wx'});
  results.screenshots.push(path);
}

async function verifyStaticHelp(page, results, output, mobile) {
  const label = mobile ? 'mobile' : 'desktop';
  const state = await page.evaluate(`(() => {
    const help=document.getElementById('open-help'),content=document.getElementById('report-content');
    return {helpVisible:!!help&&!help.hidden&&getComputedStyle(help).display!=='none',
      reportHidden:!!content&&content.hidden&&getComputedStyle(content).display==='none',
      text:help?.textContent||'',width:document.documentElement.clientWidth,
      scrollWidth:document.documentElement.scrollWidth};
  })()`);
  assert(state.helpVisible, `${label}: JavaScript-disabled opening help is not visible`);
  assert(state.reportHidden, `${label}: JavaScript-disabled report body should be hidden`);
  for (const required of ['使用浏览器（如 Edge、Chrome）打开', 'browser, such as Edge or Chrome', 'JavaScript']) {
    assert(state.text.includes(required), `${label}: opening help omits ${required}`);
  }
  assert(state.scrollWidth <= state.width + 1, `${label}: opening help overflows horizontally`);
  results.checks.push(`${label}: JavaScript disabled shows browser/app guidance and hides report body`);
  await screenshot(page, output, `${label}-javascript-disabled.png`, results);
}

async function clickElement(page, selector, mobile = false) {
  const point = await page.evaluate(`(async () => {
    const element = document.querySelector(${JSON.stringify(selector)});
    if (!element) throw new Error('Missing control: ' + ${JSON.stringify(selector)});
    element.scrollIntoView({block: 'center', inline: 'center', behavior: 'instant'});
    await new Promise(done => requestAnimationFrame(() => requestAnimationFrame(done)));
    const rect = element.getBoundingClientRect();
    if (!rect.width || !rect.height) throw new Error('Hidden control: ' + ${JSON.stringify(selector)});
    return {x: rect.left + rect.width / 2, y: rect.top + rect.height / 2};
  })()`);
  if (mobile) {
    await page.send('Input.dispatchTouchEvent', {
      type: 'touchStart', touchPoints: [{...point, radiusX: 2, radiusY: 2, force: 1}],
    });
    await page.send('Input.dispatchTouchEvent', {type: 'touchEnd', touchPoints: []});
  } else {
    await page.send('Input.dispatchMouseEvent', {type: 'mouseMoved', ...point});
    await page.send('Input.dispatchMouseEvent', {
      type: 'mousePressed', ...point, button: 'left', clickCount: 1,
    });
    await page.send('Input.dispatchMouseEvent', {
      type: 'mouseReleased', ...point, button: 'left', clickCount: 1,
    });
  }
  await wait(35);
}

async function setControl(page, selector, value) {
  await page.evaluate(`(() => {
    const element = document.querySelector(${JSON.stringify(selector)});
    if (!element) throw new Error('Missing control: ' + ${JSON.stringify(selector)});
    element.value = ${JSON.stringify(String(value))};
    element.dispatchEvent(new Event('input', {bubbles: true}));
    element.dispatchEvent(new Event('change', {bubbles: true}));
  })()`);
  await wait(20);
}

async function exercise(page, results, output, mobile) {
  const label = mobile ? 'mobile' : 'desktop';
  // Viewer-specific interactions are deliberately kept together for easy review.
  const structure = await page.evaluate(`(() => ({
    viewport: innerWidth,
    width: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth,
    tabs: [...document.querySelectorAll('[role="tab"]')].map(el => ({id: el.id, text: el.textContent})),
    title: document.title
  }))()`);
  assert(structure.scrollWidth <= structure.width + 1,
    `${label}: document overflows horizontally (${structure.scrollWidth} > ${structure.width})`);
  assert(structure.tabs.length === 5, `${label}: expected five review tabs, got ${structure.tabs.length}`);
  results.checks.push(`${label}: responsive layout`, `${label}: five review tabs`);
  results[`${label}Structure`] = structure;
  for (const tab of structure.tabs) {
    assert(tab.id, `${label}: tab needs a stable id`);
    await clickElement(page, `#${tab.id}`, mobile);
    const tabState = await page.evaluate(`(() => {
      const tab = document.getElementById(${JSON.stringify(tab.id)});
      const panel = document.getElementById(tab.getAttribute('aria-controls'));
      return {selected: tab.getAttribute('aria-selected'),
        visible: !!panel && !panel.hidden && getComputedStyle(panel).display !== 'none',
        width: document.documentElement.clientWidth, scrollWidth: document.documentElement.scrollWidth};
    })()`);
    assert(tabState.selected === 'true' && tabState.visible,
      `${label}: tab ${tab.id} did not activate its panel`);
    assert(tabState.scrollWidth <= tabState.width + 1,
      `${label}: tab ${tab.id} causes horizontal document overflow`);
  }
  results.checks.push(`${label}: all review tabs activate`);
  await clickElement(page, `#${structure.tabs[0].id}`, mobile);

  const data = await page.evaluate(`(() => {
    const report = JSON.parse(document.getElementById('report-data').textContent);
    const line = report.defaultLine.map(id => report.nodes[id]);
    const pvNode = line.find(node => node.analysis?.candidates.some(candidate => candidate.pv?.length > 1));
    const absentNode = line.find(node => !node.analysis || node.analysis.status !== 'complete');
    const withCandidates = line.filter(node => node.analysis?.candidates.length);
    return {first: line[0].moveNumber, second: line[1]?.moveNumber,
      last: line.at(-1).moveNumber, middle: line[Math.floor(line.length / 2)].moveNumber,
      mainLeaf: line.at(-1).id,
      pvMove: pvNode?.moveNumber,
      screenshotMove: withCandidates[Math.floor(withCandidates.length/2)]?.moveNumber,
      pvIndex: pvNode?.analysis.candidates.findIndex(candidate => candidate.pv?.length > 1),
      absentMove: absentNode?.moveNumber, name: report.game.name};
  })()`);
  const moveNumber = () => page.evaluate("Number(document.getElementById('move-number').value)");
  await clickElement(page, '#first-move', mobile);
  assert(await moveNumber() === data.first, `${label}: first-move navigation failed`);
  if (data.second !== undefined) {
    await clickElement(page, '#next-move', mobile);
    assert(await moveNumber() === data.second, `${label}: next-move navigation failed`);
    await clickElement(page, '#previous-move', mobile);
    assert(await moveNumber() === data.first, `${label}: previous-move navigation failed`);
    await setControl(page, '#move-slider', 1);
    assert(await moveNumber() === data.second, `${label}: move slider navigation failed`);
  }
  await clickElement(page, '#last-move', mobile);
  assert(await moveNumber() === data.last, `${label}: last-move navigation failed`);
  await setControl(page, '#move-number', data.middle);
  assert(await moveNumber() === data.middle, `${label}: move-number navigation failed`);
  results.checks.push(`${label}: first/previous/next/last, move input and slider navigation`);

  const leaves = await page.evaluate(`(() => {
    const report=JSON.parse(document.getElementById('report-data').textContent);
    return [...document.querySelector('#branch-select').options]
      .map(option=>({id:option.value,move:report.nodes[option.value].moveNumber}));
  })()`);
  const alternate = leaves.find(leaf => leaf.id !== data.mainLeaf);
  if (alternate) {
    await setControl(page, '#branch-select', alternate.id);
    await clickElement(page, '#last-move', mobile);
    assert(await moveNumber() === alternate.move, `${label}: alternate branch did not navigate`);
    assert(await page.evaluate("document.getElementById('branch-select').value") === alternate.id,
      `${label}: branch selection was not retained`);
    await setControl(page, '#branch-select', data.mainLeaf);
    results.checks.push(`${label}: branch selection and navigation`);
  } else results.skipped.push(`${label}: no alternate branch in sample`);

  if (data.pvMove !== undefined) {
    await setControl(page, '#move-number', data.pvMove);
    const originalBoard = await page.evaluate("document.getElementById('board').innerHTML");
    await clickElement(page, `#candidate-body tr[data-candidate="${data.pvIndex}"] button`, mobile);
    assert(await page.evaluate("!document.getElementById('pv-controls').hidden"),
      `${label}: candidate PV did not open`);
    const firstPV = await page.evaluate("document.getElementById('pv-label').textContent");
    assert(await page.evaluate("document.getElementById('board').innerHTML") !== originalBoard,
      `${label}: candidate PV did not update the board`);
    await clickElement(page, '#pv-next', mobile);
    assert(await page.evaluate("document.getElementById('pv-label').textContent") !== firstPV,
      `${label}: PV next step failed`);
    await clickElement(page, '#pv-prev', mobile);
    assert(await page.evaluate("document.getElementById('pv-label').textContent") === firstPV,
      `${label}: PV previous step failed`);
    await clickElement(page, '#pv-exit', mobile);
    assert(await page.evaluate("document.getElementById('pv-controls').hidden"),
      `${label}: candidate PV did not exit`);
    assert(await page.evaluate("document.getElementById('board').innerHTML") === originalBoard,
      `${label}: exiting PV did not restore the actual position`);
    const boardMarker = `#board g[data-candidate="${data.pvIndex}"]`;
    if (await page.evaluate(`!!document.querySelector(${JSON.stringify(boardMarker)})`)) {
      await clickElement(page, boardMarker, mobile);
      assert(await page.evaluate("!document.getElementById('pv-controls').hidden"),
        `${label}: board candidate marker did not open its variation`);
      await clickElement(page, '#pv-exit', mobile);
      results.checks.push(`${label}: candidate marker on board opens its variation`);
    }
    await clickElement(page, `#candidate-body tr[data-candidate="${data.pvIndex}"] button`, mobile);
    await clickElement(page, '#last-move', mobile);
    assert(await page.evaluate("document.getElementById('pv-controls').hidden"),
      `${label}: normal navigation retained a stale candidate PV`);
    results.checks.push(`${label}: candidate variation next/previous/exit and navigation reset`);
  } else results.skipped.push(`${label}: no multi-step candidate variation in sample`);

  if (data.absentMove !== undefined) {
    await setControl(page, '#move-number', data.absentMove);
    assert(await page.evaluate("!document.getElementById('position-status').classList.contains('complete')"),
      `${label}: incomplete analysis displayed as complete`);
    results.checks.push(`${label}: incomplete analysis is explicitly marked`);
  }

  for (const scope of ['opening', 'middle', 'endgame', 'all']) {
    await setControl(page, '#scope-select', scope);
    assert(await page.evaluate("document.getElementById('scope-select').value") === scope,
      `${label}: scope ${scope} failed`);
    await clickElement(page, '#tab-overview', mobile);
    assert(await page.evaluate("!document.getElementById('panel-overview').hidden"),
      `${label}: overview did not render after scope change`);
    const content = await page.evaluate(`(() => {
      const report=JSON.parse(document.getElementById('report-data').textContent);
      const scope=${JSON.stringify(scope)};
      const inScope=n=>scope==='all'||(scope==='opening'&&n.moveNumber>=1&&n.moveNumber<=60)
        ||(scope==='middle'&&n.moveNumber>=61&&n.moveNumber<=160)||(scope==='endgame'&&n.moveNumber>=161);
      const nodes=report.defaultLine.map(id=>report.nodes[id]).filter(inScope);
      const reviews=nodes.filter(n=>n.review?.complete && ['好手','正常','疑问手','坏手','严重失误'].includes(n.review.grade));
      const expected=[nodes.filter(n=>n.analysis?.status==='complete').length+' / '+nodes.length,
        nodes.filter(n=>Number.isFinite(n.analysis?.blackWinrate)).length+' / '+nodes.length,
        reviews.length+' / '+nodes.filter(n=>n.parentId!==null).length];
      const actual=[...document.querySelectorAll('#coverage-summary h3')].slice(0,3).map(el=>el.textContent);
      const rows=[...document.querySelectorAll('#problem-body tr[data-node-id],#match-body tr[data-node-id]')];
      return {expected,actual,rowsInScope:rows.every(el=>inScope(report.nodes[el.dataset.nodeId]))};
    })()`);
    assert(JSON.stringify(content.expected) === JSON.stringify(content.actual),
      `${label}: ${scope} overview counts differ: ${JSON.stringify(content)}`);
    assert(content.rowsInScope, `${label}: ${scope} contains moves outside the requested range`);
  }
  results.checks.push(`${label}: all/opening/middle/endgame scope counts and filtered rows`);
  await clickElement(page, '#tab-trend', mobile);
  const point = await page.evaluate(`(() => {
    const report=JSON.parse(document.getElementById('report-data').textContent);
    const points=[...document.querySelectorAll('#trend-chart circle[data-node-id]')];
    const circle=points[Math.floor(points.length/2)];
    const id=circle?.dataset.nodeId;
    return id ? {id,move:report.nodes[id].moveNumber} : null;
  })()`);
  if (point) {
    await clickElement(page, `#trend-chart circle[data-node-id="${point.id}"]`, mobile);
    assert(await moveNumber() === point.move, `${label}: chart point did not navigate to its move`);
    results.checks.push(`${label}: win-rate chart ${mobile ? 'touch' : 'click'} navigates the board`);
  } else results.skipped.push(`${label}: no win-rate points in sample`);
  await setControl(page, '#zoom-x', '2');
  await setControl(page, '#zoom-y', '2');
  await clickElement(page, '#reset-zoom', mobile);
  assert(await page.evaluate("document.getElementById('zoom-x').value === '1' && document.getElementById('zoom-y').value === '1'"),
    `${label}: chart reset did not restore both zoom controls`);
  results.checks.push(`${label}: chart zoom and reset`);

  for (const tab of ['problems', 'match']) {
    await clickElement(page, `#tab-${tab}`, mobile);
    const body = tab === 'problems' ? 'problem-body' : 'match-body';
    const row = await page.evaluate(`(() => {
      const report=JSON.parse(document.getElementById('report-data').textContent);
      const row=document.querySelector('#${body} tr[data-node-id]');
      return row ? {id:row.dataset.nodeId,move:report.nodes[row.dataset.nodeId].moveNumber} : null;
    })()`);
    if (row) {
      await clickElement(page, `#${body} tr[data-node-id="${row.id}"] button`, mobile);
      assert(await moveNumber() === row.move, `${label}: ${tab} row did not navigate`);
      results.checks.push(`${label}: ${tab} records navigate the board`);
    } else results.skipped.push(`${label}: no ${tab} records in sample`);
  }

  await setControl(page, '#language-select', 'en');
  assert(await page.evaluate("document.documentElement.lang") === 'en', `${label}: English switch failed`);
  assert(await page.evaluate("document.getElementById('tab-trend').textContent") === 'Win-rate trend',
    `${label}: English tab text was not translated`);
  await setControl(page, '#language-select', 'zh');
  assert(await page.evaluate("document.documentElement.lang") === 'zh-CN', `${label}: Chinese switch failed`);
  results.checks.push(`${label}: Chinese/English language switch`);
  await clickElement(page, '#tab-trend', mobile);
  assert(await page.evaluate("document.getElementById('tab-trend').getAttribute('aria-selected')") === 'true',
    `${label}: restoring the trend tab failed`);
  await setControl(page, '#move-number', data.screenshotMove ?? data.middle);
  const finalWidth = await page.evaluate('({width:document.documentElement.clientWidth,scroll:document.documentElement.scrollWidth})');
  assert(finalWidth.scroll <= finalWidth.width + 1,
    `${label}: interaction caused horizontal document overflow`);
  await page.evaluate("document.querySelectorAll('.table-wrap,.tabs').forEach(el=>el.scrollLeft=0); window.scrollTo({top:0,behavior:'instant'})");
  await screenshot(page, output, `${label}.png`, results);
  if (mobile) {
    await page.evaluate("document.getElementById('candidate-heading').scrollIntoView({block:'start',behavior:'instant'})");
    await screenshot(page, output, `${label}-candidates.png`, results);
  }
  for (const tab of structure.tabs) {
    await clickElement(page, `#${tab.id}`, mobile);
    await page.evaluate("document.querySelectorAll('.table-wrap').forEach(el=>el.scrollLeft=0)");
    await page.evaluate("document.getElementById('review-title').scrollIntoView({block:'start',behavior:'instant'})");
    await screenshot(page, output, `${label}-${tab.id}.png`, results);
  }
  await clickElement(page, '#tab-trend', mobile);
}

main().catch(error => {
  console.error(error.stack || String(error));
  process.exitCode = 1;
});
