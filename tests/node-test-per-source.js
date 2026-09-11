const core = require(process.argv[2]); const fs = require('fs'), path = require('path'); const dir = process.argv[3];
(async () => {
  const datasets = [];
  for (const f of ['TOTFA-11401.zip', 'TOTFA-11402.zip']) {
    const buf = fs.readFileSync(path.join(dir, f)); const ab = buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength);
    for (const ds of await core.loadClaimFile(f, ab)) datasets.push(ds);
  }
  const t = core.buildTables(datasets, { idMode: 'code', nameMode: 'mask', birthMode: 'year', staffMode: 'code' });
  console.log('stats', t.stats);
  for (const f of t.files) {
    const flatExpected = f.cases.rows.filter((r, i) => datasets.find(d => d.source === f.source).cases[i].orders.length === 0).length + f.orders.rows.length;
    console.log(f.stem, '|', f.flat.name, f.flat.rows.length, 'expected', flatExpected, '|', f.cases.name, f.cases.rows.length, '|', f.orders.name, f.orders.rows.length);
  }
  console.log('flat cols', t.files[0].flat.columns.length, '=', t.files[0].cases.columns.length, '+', t.files[0].flat.columns.length - t.files[0].cases.columns.length);
  const csv = core.toCsv(t.files[0].flat).split('\r\n');
  console.log(csv[0]); console.log(csv[1]); console.log(csv[2]);
  // same patient across files gets same code?
  const idToCode = new Map(); let mismatch = 0;
  for (const ds of datasets) { const f = t.files.find(x => x.source === ds.source); ds.cases.forEach((c, i) => { const code = f.cases.rows[i]['病人代碼']; if (idToCode.has(c.fields.d3) && idToCode.get(c.fields.d3) !== code) mismatch++; idToCode.set(c.fields.d3, code); }); }
  console.log('cross-file code mismatches', mismatch, 'totals rows', t.totals.rows.length, t.totals.name);
  console.log(core.sourceStem ? '' : 'stem via files:', t.files.map(f => f.stem).join(','));
})().catch(e => { console.error('FAIL', e); process.exit(1); });
