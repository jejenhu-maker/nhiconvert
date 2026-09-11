// 用 Node 測試核心邏輯：解析所有 zip、去識別化、檢查輸出沒有殘留身分證／姓名／醫師代號、zip 打包回讀。
// 用法：node tests/node-test.js out/core.js <申報檔資料夾> <輸出資料夾>
const core = require(require('path').resolve(process.argv[2]));
const fs = require('fs'), path = require('path');
const dir = process.argv[3], outDir = process.argv[4] || '.';
(async () => {
  const datasets = [];
  for (const f of fs.readdirSync(dir).filter(n => /\.zip$/i.test(n)).sort()) {
    const buf = fs.readFileSync(path.join(dir, f));
    const ab = buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength);
    const t0 = Date.now();
    let dss;
    try { dss = await core.loadClaimFile(f, ab); } catch (e) { console.log(f, 'skip:', e.message); continue; }
    for (const ds of dss) {
      const orders = ds.cases.reduce((n, c) => n + c.orders.length, 0);
      console.log(f, 't1=' + ds.totals.t1, 't3=' + ds.totals.t3, 'cases', ds.cases.length, 't37=' + ds.totals.t37, 'orders', orders, (Date.now() - t0) + 'ms');
      datasets.push(ds);
    }
  }
  const opts = { idMode: 'code', nameMode: 'mask', birthMode: 'year', staffMode: 'code' };
  const tables = core.buildTables(datasets, opts);
  console.log('stats', tables.stats);
  console.log('output files:', tables.files.map(f => f.flat.name).join(', '), '+', tables.totals.name);
  console.log('flat cols:', tables.files[0].flat.columns.map(c => c.label).join(' | '));
  const firstCsv = core.toCsv(tables.files[0].flat);
  console.log(firstCsv.split('\r\n').slice(0, 3).join('\n'));

  // 洩漏檢查：原始身分證、姓名、醫事人員代號不得出現在任何輸出儲存格
  const allIds = new Set(), allNames = new Set(), allStaff = new Set();
  for (const ds of datasets) for (const c of ds.cases) {
    allIds.add(c.fields.d3); if (c.fields.d49) allNames.add(c.fields.d49.trim()); allStaff.add(c.fields.d30);
    for (const o of c.orders) if (o.p16) allStaff.add(o.p16);
  }
  const cells = new Set();
  for (const f of tables.files) for (const t of [f.flat, f.cases, f.orders]) for (const r of t.rows) for (const v of Object.values(r)) cells.add(String(v));
  const count = (set) => { let n = 0; for (const x of set) if (x && cells.has(x)) n++; return n; };
  console.log('unique ids', allIds.size, 'id leaks', count(allIds), 'name leaks', count(allNames), 'staff leaks', count(allStaff));
  console.log('age test', core.ageAt('0580929', '1140124'), core.maskName('王小明'), core.maskName('歐陽小明'), core.maskName('A'));

  // 其他模式
  const t2 = core.buildTables(datasets.slice(0, 1), { idMode: 'blank', nameMode: 'blank', birthMode: 'age', staffMode: 'blank' });
  console.log('blank-mode cols:', t2.files[0].cases.columns.map(c => c.label).join(' | '));

  // zip 打包回讀
  const enc = new TextEncoder();
  const zipBlob = await core.buildZip([{ name: tables.files[0].flat.name, data: enc.encode(firstCsv) }, { name: '說明.txt', data: enc.encode(core.readmeText(opts, tables.stats)) }]);
  const zab = await zipBlob.arrayBuffer();
  const back = await core.readZip(zab);
  console.log('zip roundtrip', back.map(e => e.name + ':' + e.data.length), 'orig', enc.encode(firstCsv).length);
  fs.writeFileSync(path.join(outDir, 'out.zip'), Buffer.from(zab));
})().catch(e => { console.error('FAIL', e); process.exit(1); });
