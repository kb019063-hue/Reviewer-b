/*
 * UI regression tests for the WebView page (test/ui).
 *
 * The page is executed in jsdom against a stub `AnneNative` bridge, so these run
 * without a device or an APK. They cover the behaviours that broke in 1.0.1:
 *   - app labels rendered as TEXT, never parsed as HTML (bridge-injection safety)
 *   - sweep/automation banners only claim what the bridge actually reported
 *   - keep-alive persistence, sweep-scope toggle
 *   - async cache scan: progress streaming, callback rendering, no blocking call
 *   - every way to cancel a run (banner tap, in-app resume)
 *
 *   npm ci && npm test
 */
const fs = require('fs');
const { JSDOM, VirtualConsole } = require('jsdom');

const path = require('path');
const html = fs.readFileSync(
  path.join(__dirname, '..', '..', 'anne-control-apk', 'src', 'main', 'assets', 'index.html'), 'utf8');

const EVIL = '<img src=x onerror="window.__pwned=1">';
const calls = [];
let cacheMode = 'needs';

const bloatPayload = () => ([
  { pkg: 'com.huawei.search', title: 'Huawei HiSearch', category: 'c', tier: 'safe', impact: 'High',
    desc: 'd', state: 'active', cacheMb: 3.2 },
  { pkg: 'com.evil.app', title: EVIL, category: 'c', tier: 'safe', impact: 'Low',
    desc: EVIL, state: 'active', cacheMb: -1 },
  { pkg: 'com.booking', title: 'Booking', category: 'c', tier: 'safe', impact: 'Low',
    desc: 'd', state: 'disabled', cacheMb: -1 }
]);

const cachePayload = () => cacheMode === 'error'
  ? { needsUsageAccess: false, error: true, message: 'Storage stats unavailable.', items: [] }
  : cacheMode === 'needs'
  ? { needsUsageAccess: true, items: [] }
  : { needsUsageAccess: false, totalCacheMb: 812.4, scannedApps: 96, items: [
      { pkg: 'com.whatsapp', label: 'WhatsApp', cacheMb: 210.5, totalMb: 900 },
      { pkg: 'com.evil.app', label: EVIL, cacheMb: 88.1, totalMb: 300 } ] };


const native = {
  getDashboardJson: () => JSON.stringify({
    model: native.__supportedDevice === false ? 'Other model' : 'ANE-LX1',
    supportedDevice: native.__supportedDevice !== false,
    manufacturer: 'HUAWEI', displayBuild: 'ANE-LX1 9.1.0', androidRelease: '9',
    permissions: { usageAccess: true, accessibility: false, accessibilityStale: true,
                   writeSettings: true, batteryExemption: false },
    ram: { totalMb: 3768, availMb: 1234, usedMb: 2534, cachedMb: 500, swapTotalMb: 512, swapUsedMb: 76, lowMemory: false },
    storage: { totalGb: 32, freeGb: 14.2, usedGb: 17.8, percentUsed: 56 },
    battery: { level: 82, tempC: 31.2, voltageMv: 4095, source: 'USB', health: 'Good' },
    settings: { fontScale: 1, windowAnimScale: 0.5, screenTimeoutSec: 60 }
  }),
  sweepBackgroundRamJson: () => JSON.stringify({ ok: true, requestedCount: 7, freedMb: -3, availMb: 1000, scope: 'bloat+apps' }),
  getKeepAliveJson: () => JSON.stringify({
    sweepAllApps: true,
    curated: [{ pkg: 'com.huawei.search', label: 'Huawei HiSearch', kept: false, curated: true }],
    others: [{ pkg: 'com.whatsapp', label: 'WhatsApp', kept: false, curated: false },
             { pkg: 'com.evil.app', label: EVIL, kept: false, curated: false }]
  }),
  setKeepAlive: (p, k) => { calls.push(['setKeepAlive', p, k]); return true; },
  setSweepAllApps: (a) => { calls.push(['setSweepAllApps', a]); return true; },
  getHuaweiBloatListJson: () => JSON.stringify(bloatPayload()),
  scanBloatListAsync: () => {
    calls.push(['scanBloatListAsync']);
    setTimeout(() => { if (native.__win.onBloatScan) native.__win.onBloatScan(bloatPayload()); }, 5);
  },
  getTopCacheAppsJson: () => { calls.push(['getTopCacheAppsJson']); return JSON.stringify(cachePayload()); },
  scanCachesAsync: () => {
    calls.push(['scanCachesAsync']);
    setTimeout(() => {
      if (native.__win.onScanProgress) native.__win.onScanProgress('cache', 8, 150);
      native.__win.__progressText = native.__doc.getElementById('cacheListContainer').textContent;
      setTimeout(() => { if (native.__win.onCacheScan) native.__win.onCacheScan(cachePayload()); }, 5);
    }, 5);
  },
  startAutomation: (mode, csv) => {
    calls.push(['startAutomation', mode, csv]);
    if (native.__supportedDevice === false) {
      return JSON.stringify({ ok: false, unsupportedDevice: true,
        message: 'Automation is limited to Huawei ANE-LX1 running Android 9 / EMUI 9.1.' });
    }
    return JSON.stringify({ ok: false, needsAccessibility: true, serviceListed: true });
  },
  stopAutomation: () => { calls.push(['stopAutomation']); },
  getAutomationStatusJson: () => JSON.stringify(native.__running
    ? { running: true, currentIndex: 2, totalCount: 9, succeededCount: 2 }
    : { running: false }),
  consumeRunSummaryJson: () => JSON.stringify({ available: true, message: 'Done: 3 succeeded, 1 skipped, 0 failed of 4 apps.' }),
  openPermissionScreen: (t) => calls.push(['openPerm', t]),
  openAppInfo: (p) => calls.push(['openAppInfo', p]),
  beginThemeFolderSelection: () => calls.push(['beginThemeFolderSelection']),
  getSupportReportJson: () => JSON.stringify({
    device: { manufacturer: 'HUAWEI', model: 'ANE-LX1', androidRelease: '9', emuiBuild: 'ANE-LX1 9.1.0' },
    app: { versionName: '1.0.4', packageName: 'com.annecontrol.p20lite' },
    themes: { managerInstalled: true, lastInspection: { themeName: 'Clarity 9', importStatus: 'preview_ready' } },
    privacy: 'No serial, IMEI, Android ID, contacts, personal files, or installed-app list.'
  }),
  setCompactFontScale: (scale) => { calls.push(['setCompactFontScale', scale]); return true; },
  restoreOriginalFontScale: () => { calls.push(['restoreOriginalFontScale']); return true; },
  invalidateScanCaches: () => calls.push(['invalidate']),
  copyToClipboard: () => {}, shareText: (title, text) => calls.push(['shareText', title, text]), openDialerCode: () => {},
  importHuaweiTheme: () => calls.push(['importHuaweiTheme'])
};

const vc = new VirtualConsole();
vc.on('jsdomError', (e) => { if (!/Not implemented/.test(e.message)) console.log('JSDOM ERROR:', e.message); });

const dom = new JSDOM(html, {
  runScripts: 'dangerously',
  pretendToBeVisual: true,
  virtualConsole: vc,
  beforeParse(window) {
    window.AnneNative = native;
    window.scrollTo = () => {};
    window.__calls = calls;
    native.__win = window;     // stub closures must reach back into the jsdom window
    native.__doc = window.document;
  }
});

const { window } = dom;
const doc = window.document;
const sleep = (ms) => new Promise(r => setTimeout(r, ms));

let pass = 0, fail = 0;
function ok(name, cond, extra) {
  if (cond) { pass++; console.log('  PASS  ' + name); }
  else { fail++; console.log('  FAIL  ' + name + (extra ? ' :: ' + extra : '')); }
}
function banner() { return doc.getElementById('statusToast').textContent; }

(async () => {
  await sleep(400); // let the deferred keep-alive load run

  console.log('\n[1] dashboard');
  ok('RAM value rendered from bridge', doc.getElementById('ramAvailTxt').textContent === '1234 MB',
     doc.getElementById('ramAvailTxt').textContent);
  ok('model label rendered', doc.getElementById('topModelLabel').textContent.includes('ANE-LX1'));
  ok('home explains it cannot repair EMUI or install updates',
     /cannot repair EMUI bugs, install system updates/i.test(doc.querySelector('.hero-card').textContent));
  ok('home does not claim elevated or system-level access',
     !/elevated system access|direct system-level control|higher access switches/i.test(html));
  ok('permission card explains Android still limits the app',
     /not root or system-level access/i.test(doc.querySelectorAll('#tab-boost .card')[1].textContent));
  ok('stale accessibility shows "Restart service"',
     doc.getElementById('permAccBtn').textContent === 'Restart service',
     doc.getElementById('permAccBtn').textContent);
  ok('battery rendered', doc.getElementById('batLvlTxt').textContent === '82%');

  console.log('\n[1b] Huawei theme import');
  window.switchTab('themes');
  ok('theme importer explains local .hwt selection',
     /\.hwt/i.test(doc.getElementById('tab-themes').textContent));
  ok('theme importer leaves final apply to Huawei Themes',
     /you still confirm apply/i.test(doc.getElementById('tab-themes').textContent));
  doc.getElementById('btnImportTheme').click();
  ok('theme button starts native preview selection',
     calls.some(c => c[0] === 'importHuaweiTheme'));
  window.onThemePreview(JSON.stringify({
    ok: true, fileName: 'Clarity9-EMUI91.hwt', fileBytes: 123456, themeName: 'Clarity 9',
    version: '1.0.0', font: 'Clarity Sans', previewMime: 'image/png', previewImageBase64: 'aW1n',
    checks: [{ name: 'HWT/ZIP readable', ok: true, detail: '12 entries checked' }],
    notice: 'Structural scan only; not applied.'
  }));
  ok('preview card appears after local package inspection',
     !doc.getElementById('themePreviewCard').classList.contains('hidden'));
  ok('preview identifies the theme and selected archive',
     /Clarity 9/.test(doc.getElementById('themePreviewName').textContent) &&
     /Clarity9-EMUI91.hwt/.test(doc.getElementById('themePreviewMeta').textContent));
  ok('preview uses packaged artwork, not HTML',
     doc.getElementById('themePreviewImage').src.indexOf('data:image/png;base64,aW1n') === 0);
  ok('structural check is rendered as text',
     /HWT\/ZIP readable/.test(doc.getElementById('themeCheckList').textContent));
  doc.getElementById('btnInstallTheme').click();
  ok('import is gated behind preview and starts folder picker',
     calls.some(c => c[0] === 'beginThemeFolderSelection'));
  window.onThemeImportComplete();
  ok('completion tells user to apply in Huawei Themes', /Huawei Themes/.test(banner()));

  window.generateSupportReport();
  ok('support report is shown locally',
     !doc.getElementById('supportReportPanel').classList.contains('hidden') &&
     /ANE-LX1/.test(doc.getElementById('supportReportText').textContent));
  const supportReport = JSON.parse(doc.getElementById('supportReportText').textContent);
  ok('report schema omits direct-identifier fields',
     !('imei' in supportReport) && !('serial' in supportReport) && !('androidId' in supportReport));
  doc.getElementById('btnShareReport').click();
  ok('sharing is explicit and uses Android share sheet',
     calls.some(c => c[0] === 'shareText' && /device and theme report/i.test(c[1])));
  window.switchTab('boost');

  console.log('\n[2] honest sweep reporting');
  doc.getElementById('btnSweep').click();
  await sleep(200);
  ok('banner reports requested count', banner().includes('7 apps'), banner());
  ok('banner shows real negative delta', banner().includes('-3 MB'), banner());
  ok('banner no longer fabricates 16 MB', !banner().includes('16 MB'), banner());
  ok('button re-enabled after sweep', !doc.getElementById('btnSweep').disabled);
  ok('button label restored',
     doc.getElementById('btnSweep').textContent === 'Request background cleanup',
     doc.getElementById('btnSweep').textContent);

  console.log('\n[3] keep-alive list + injection safety');
  const keepBox = doc.getElementById('keepListContainer');
  ok('keep list rendered rows', keepBox.querySelectorAll('.pkg-name').length >= 3,
     String(keepBox.querySelectorAll('.pkg-name').length));
  ok('NO html parsed from app label', keepBox.querySelector('img') === null);
  ok('evil label present as literal text',
     Array.from(keepBox.querySelectorAll('.pkg-name')).some(n => n.textContent === EVIL));
  ok('window.__pwned never set', window.__pwned === undefined);
  ok('no inline onclick generated by data', keepBox.querySelectorAll('[onclick]').length === 0);

  const whatsappRow = Array.from(keepBox.children).find(r =>
    r.querySelector && r.querySelector('.pkg-name') && r.querySelector('.pkg-name').textContent === 'WhatsApp');
  ok('WhatsApp appears in keep-alive list (i.e. killable)', !!whatsappRow);
  if (whatsappRow) {
    const btn = whatsappRow.querySelector('button');
    btn.click();
    await sleep(20);
    ok('toggling keep calls bridge with pkg',
       calls.some(c => c[0] === 'setKeepAlive' && c[1] === 'com.whatsapp' && c[2] === true),
       JSON.stringify(calls.filter(c => c[0] === 'setKeepAlive')));
    ok('row label flips to Kept alive',
       Array.from(keepBox.querySelectorAll('button')).some(b => b.textContent === 'Kept alive'));
  }

  doc.getElementById('scope-bloat').click();
  await sleep(20);
  ok('scope toggle persists', calls.some(c => c[0] === 'setSweepAllApps' && c[1] === false));

  console.log('\n[4] bloat list');
  window.switchTab('bloat');
  await sleep(50);
  const bloatBox = doc.getElementById('bloatContainer');
  ok('bloat cards rendered', bloatBox.querySelectorAll('.pkg-card').length === 3,
     String(bloatBox.querySelectorAll('.pkg-card').length));
  ok('no html from catalog title', bloatBox.querySelector('img') === null);
  ok('no inline onclick in cards', bloatBox.querySelectorAll('[onclick]').length === 0);
  const firstCard = bloatBox.querySelector('.pkg-card');
  const autoDisable = Array.from(firstCard.querySelectorAll('button')).find(b => b.textContent === 'Auto-Disable');
  ok('Auto-Disable button present for active app', !!autoDisable);
  if (autoDisable) {
    autoDisable.click();
    ok('disable action asks for confirmation',
       !doc.getElementById('confirmBackdrop').classList.contains('hidden'));
    ok('confirmation lists the package being changed',
       doc.getElementById('confirmTargets').textContent.includes('com.huawei.search'));
    const startsBeforeCancel = calls.filter(c => c[0] === 'startAutomation').length;
    autoDisable.click();
    doc.getElementById('cancelActionBtn').click();
    ok('cancel dismisses the modal without starting work',
       calls.filter(c => c[0] === 'startAutomation').length === startsBeforeCancel);
    autoDisable.click();
    doc.getElementById('confirmActionBtn').click();
    await sleep(20);
    ok('confirmed action starts automation with the right package',
       calls.some(c => c[0] === 'startAutomation' && c[1] === 'disable' && c[2] === 'com.huawei.search'));
  }

  console.log('\n[5] accessibility failure is surfaced, not faked');
  ok('banner says nothing was started', /not running/i.test(banner()), banner());
  ok('banner does not claim success', !/Running on/.test(banner()), banner());

  console.log('\n[6] cache tab with no usage access keeps no stale items');
  calls.length = 0;
  window.switchTab('cache');
  await sleep(200);
  ok('usage-access card shown',
     !doc.getElementById('cacheNeedPermCard').classList.contains('hidden'));
  window.autoCleanTopCaches();
  await sleep(300);
  ok('auto-clean asks for the permission instead of running',
     calls.some(c => c[0] === 'openPerm' && c[1] === 'usage'));
  ok('auto-clean did NOT start an automation', !calls.some(c => c[0] === 'startAutomation'));

  console.log('\n[6b] async cache scan with progress');
  calls.length = 0;
  cacheMode = 'items';
  window.switchTab('cache');
  await sleep(200);
  ok('uses the async scanner, not the blocking call',
     calls.some(c => c[0] === 'scanCachesAsync') && !calls.some(c => c[0] === 'getTopCacheAppsJson'),
     JSON.stringify(calls));
  ok('progress was streamed to the page', /8 of 150 apps/.test(window.__progressText || ''),
     window.__progressText);
  const cacheBox = doc.getElementById('cacheListContainer');
  ok('cache rows rendered from the callback', cacheBox.querySelectorAll('.pkg-card').length === 2,
     String(cacheBox.querySelectorAll('.pkg-card').length));
  ok('header reports scanned count',
     /812.4 MB \(96 apps scanned\)/.test(doc.getElementById('totalCacheHeader').textContent),
     doc.getElementById('totalCacheHeader').textContent);
  ok('no html from cache labels', cacheBox.querySelector('img') === null);

  calls.length = 0;
  window.autoCleanTopCaches();
  await sleep(250);
  ok('auto-clean asks for confirmation after scan',
     !doc.getElementById('confirmBackdrop').classList.contains('hidden'));
  doc.getElementById('confirmActionBtn').click();
  await sleep(30);
  ok('confirmed auto-clean starts with scanned packages',
     calls.some(c => c[0] === 'startAutomation' && c[1] === 'clear_cache' && c[2].includes('com.whatsapp')),
     JSON.stringify(calls.filter(c => c[0] === 'startAutomation')));

  console.log('\n[6c] cache scan errors are not reported as empty caches');
  cacheMode = 'error';
  window.switchTab('cache');
  await sleep(120);
  ok('scan error is visible', /Storage stats unavailable/.test(doc.getElementById('cacheListContainer').textContent));
  calls.length = 0;
  window.autoCleanTopCaches();
  await sleep(120);
  ok('error does not start automation or ask for Usage Access',
     !calls.some(c => c[0] === 'startAutomation' || (c[0] === 'openPerm' && c[1] === 'usage')));
  cacheMode = 'needs';

  console.log('\n[7] resume shows the run summary once');
  const before = banner();
  window.onAnneResume();
  await sleep(30);
  ok('summary banner shown', banner().includes('3 succeeded'), banner());
  ok('summary replaced the previous banner', banner() !== before);

  console.log('\n[7b] in-flight run offers a tappable stop');
  native.__running = true;
  window.onAnneResume();
  await sleep(20);
  ok('banner reports progress', /Run in progress \(3\/9\)/.test(banner()), banner());
  ok('banner is tappable', !!doc.getElementById('statusToast').onclick);
  doc.getElementById('statusToast').click();
  await sleep(20);
  ok('tapping the banner stops the run', calls.some(c => c[0] === 'stopAutomation'));
  native.__running = false;

  console.log('\n[8] banner timer race');
  let cleared = 0;
  const realClear = window.clearTimeout;
  window.clearTimeout = function(t) { cleared++; return realClear.call(window, t); };
  window.showBanner('first');
  window.showBanner('second');
  window.clearTimeout = realClear;
  ok('second banner cancels the first timer', cleared >= 1, 'clearTimeout calls: ' + cleared);
  ok('latest banner text wins', banner() === 'second', banner());

  console.log('\n[9] system font scale can be restored');
  window.restoreFontScale();
  ok('restore action reaches native bridge', calls.some(c => c[0] === 'restoreOriginalFontScale'));
  ok('restore action confirms previous value', /previous system text scale/.test(banner()));

  console.log('\n[10] unsupported device gate is explained');
  native.__supportedDevice = false;
  window.refreshDashboard();
  ok('dashboard warns this is the wrong model', /automation is disabled/i.test(banner()), banner());
  window.startAutomation('disable', ['com.huawei.search']);
  doc.getElementById('confirmActionBtn').click();
  ok('bridge rejection explains the supported target', /ANE-LX1/.test(banner()), banner());

  console.log('\n----------------------------------------');
  console.log(`  ${pass} passed, ${fail} failed`);
  process.exit(fail ? 1 : 0);
})().catch(e => { console.error('HARNESS ERROR', e); process.exit(2); });
