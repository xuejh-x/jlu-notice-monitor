import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import { Workbook } from '@oai/artifact-tool';

const docs = path.resolve(import.meta.dirname, '..');
const evidence = import.meta.dirname;
const summary = JSON.parse(await fs.readFile(path.join(evidence, 'summary.json'), 'utf8'));
const checks = [];
for (const name of ['jlu-site-inventory.csv', 'jlu-compatibility-report.csv']) {
  const bytes = await fs.readFile(path.join(docs, name));
  assert.equal(bytes.subarray(0, 3).toString('hex'), 'efbbbf', 'UTF-8 BOM');
  const workbook = await Workbook.fromCSV(bytes.toString('utf8').replace(/^\uFEFF/, ''), { sheetName: 'Audit' });
  const sheet = workbook.worksheets.getItem('Audit');
  const values = sheet.getUsedRange().values;
  const header = values[0];
  const rows = values.slice(1);
  const field = (row, name) => row[header.indexOf(name)];
  assert.equal(new Set(header).size, header.length, 'unique headers');
  for (const row of rows) assert.equal(row.length, header.length, 'rectangular CSV');
  if (name.includes('compatibility')) {
    assert.equal(rows.length, summary.distinct_columns);
    const urls = rows.map(r => field(r, 'column_url'));
    assert.equal(new Set(urls).size, urls.length, 'no duplicate column URLs');
    const statuses = {};
    for (const row of rows) {
      const status = field(row, 'status');
      statuses[status] = (statuses[status] || 0) + 1;
      assert.ok(field(row, 'checked_at'), 'check timestamp required');
      assert.ok(field(row, 'reason'), 'reason required');
      assert.equal(field(row, 'support_status'), field(row, 'configured_source') ? '既有正式配置；本轮回归结果' : '未登记支持；仅审计结果');
      await fs.access(path.resolve(docs, '..', field(row, 'evidence_file')));
    }
    assert.deepEqual(statuses, summary.compatibility_states, 'status totals reconcile');
    assert.equal(summary.columns_checked + summary.columns_unchecked + summary.no_adaptation_needed, rows.length);
  } else {
    const counts = {};
    for (const row of rows) {
      const type = field(row, 'record_type');
      counts[type] = (counts[type] || 0) + 1;
    }
    assert.equal(counts.institution, summary.institution_rows);
    assert.equal(counts.site, summary.site_seed_urls);
    assert.equal(counts.column, summary.distinct_columns);
  }
  const inspected = await workbook.inspect({ kind: 'region', sheetId: 'Audit', range: 'A1:F3', maxChars: 500, tableMaxRows: 3, tableMaxCols: 6 });
  checks.push({ file: name, rows: rows.length, columns: header.length, imported_by: 'Artifact Tool Workbook.fromCSV', status: 'passed', inspection: inspected.ndjson });
}
await fs.writeFile(path.join(evidence, 'csv-verification.json'), JSON.stringify({ time: new Date().toISOString(), checks }, null, 2));
console.log(JSON.stringify(checks.map(({ inspection, ...check }) => check)));
