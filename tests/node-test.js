const core = require(process.argv[2]);
const fs = require('fs'), path = require('path');
const dir = process.argv[3];
(async () => {
  const datasets = [];
  for (const f of fs.readdirSync(dir).filter(n => /\.zip$/i.test(n)).sort()) {
    const buf = fs.readFileSync(path.join(dir, f));
    const ab = buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength);
    const t0 = Date.now();
    const dss = await core.loadClaimFile(f, ab);
    for (const ds of dss) {
      const orders = ds.cases.reduce((n, c) => n + c.orders.length, 0);
      console.log(f, 't1=' + ds.totals.t1, 't3=' + ds.totals.t3, 'cases', ds.cases.length, 't37=' + ds.totals.t37, 'orders', orders, (Date.now() - t0) + 'ms');
      datasets.push(ds);
    }
  }
  console.log('sample names:', datasets[0].cases.slice(0, 8).map(c => c.fields.d49).join(' '));
  const opts = { idMode: 'code', nameMode: 'mask', birthMode: 'year', staffMode: 'code' };
  const tables = core.buildTables(datasets, opts);
  console.log('stats', tables.stats);
  console.log('case cols:', tables.cases.columns.map(c => c.label).join(' | '));
  console.log('order cols:', tables.orders.columns.map(c => c.label).join(' | '));
  const csv = core.toCsv(tables.cases);
  console.log(csv.split('\r\n').slice(0, 4).join('\n'));
  console.log(core.toCsv(tables.orders).split('\r\n').slice(0, 3).join('\n'));
  console.log(core.toCsv(tables.totals).split('\r\n').slice(0, 3).join('\n'));
  // leak checks
  const allIds = new Set(); const allNames = new Set(); const allStaff = new Set();
  for (const ds of datasets) for (const c of ds.cases) { allIds.add(c.fields.d3); if (c.fields.d49) allNames.add(c.fields.d49.trim()); allStaff.add(c.fields.d30); }
  const cells = new Set();
  for (const t of [tables.cases, tables.orders]) for (const r of t.rows) for (const v of Object.values(r)) cells.add(String(v));
  let leaks = 0; for (const id of allIds) if (id && cells.has(id)) leaks++;
  let nleaks = 0; for (const n of allNames) if (n && cells.has(n)) nleaks++;
  let sleaks = 0; for (const s of allStaff) if (s && cells.has(s)) sleaks++;
  console.log('unique ids', allIds.size, 'id leaks', leaks, 'name leaks', nleaks, 'staff leaks', sleaks);
  console.log('age test', core.ageAt('0580929', '1140124'), core.maskName('王小明'), core.maskName('歐陽小明'), core.maskName('A'));
  // age mode + blank mode
  const t2 = core.buildTables(datasets.slice(0, 1), { idMode: 'blank', nameMode: 'blank', birthMode: 'age', staffMode: 'blank' });
  console.log('blank cols:', t2.cases.columns.map(c => c.label).join(' | '));
  console.log(core.toCsv(t2.cases).split('\r\n')[1]);
  // zip roundtrip
  const enc = new TextEncoder();
  const zipBlob = await core.buildZip([{ name: '就醫紀錄.csv', data: enc.encode(csv) }, { name: '說明.txt', data: enc.encode(core.readmeText(opts, tables.stats)) }]);
  const zab = await zipBlob.arrayBuffer();
  const back = await core.readZip(zab);
  console.log('zip roundtrip', back.map(e => e.name + ':' + e.data.length), 'orig', enc.encode(csv).length);
  fs.writeFileSync(path.join(process.argv[4], 'out.zip'), Buffer.from(zab));
  fs.writeFileSync(path.join(process.argv[4], 'cases.csv'), csv);
  fs.writeFileSync(path.join(process.argv[4], 'readme.txt'), core.readmeText(opts, tables.stats));
})().catch(e => { console.error('FAIL', e); process.exit(1); });
