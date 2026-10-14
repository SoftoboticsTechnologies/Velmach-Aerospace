// Fills index.html with the English strings from js/i18n.js so the home page is complete,
// readable HTML before (and without) JavaScript. Run after editing home strings in js/i18n.js:
//   node tools/prerender-home.mjs          (writes index.html)
//   node tools/prerender-home.mjs --check  (exit 1 if index.html is out of date or a key is missing)
// Markup: data-t="dotted.key" sets the element's text; data-t-attr="attr:key;attr2:key2" sets attributes.
// At runtime js/home.js applies the same keys for the visitor's language.
import { readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import vm from 'node:vm';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const file = join(root, 'index.html');
const ctx = { window: {} };
vm.runInNewContext(readFileSync(join(root, 'js/i18n.js'), 'utf8'), ctx);
const D = ctx.window.VM_I18N;
const get = (o, k) => k.split('.').reduce((v, p) => (v == null ? v : v[p]), o);
const esc = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const escAttr = s => esc(s).replace(/"/g, '&quot;');

const src = readFileSync(file, 'utf8');
const problems = [], used = new Set();
const check = (k, where) => {
  used.add(k);
  for (const l of ['en', 'ar']) {
    const v = get(D[l], k);
    if (typeof v !== 'string') problems.push(`${l}: "${k}" is ${v === undefined ? 'missing' : typeof v} (${where})`);
  }
  return get(D.en, k);
};

// text content: element with data-t whose content is plain text
let out = src.replace(/(<([a-z0-9]+)\b[^>]*?\sdata-t="([^"]+)"[^>]*>)([^<]*)(<\/\2>)/g,
  (m, open, tag, key, _old, close) => { const v = check(key, '<' + tag + '>'); return typeof v === 'string' ? open + esc(v) + close : m; });
// attributes
out = out.replace(/<[a-z0-9]+\b[^>]*\sdata-t-attr="([^"]+)"[^>]*>/g, tagSrc => {
  const spec = /data-t-attr="([^"]+)"/.exec(tagSrc)[1];
  for (const pair of spec.split(';')) {
    const [attr, key] = pair.split(':');
    const v = check(key, attr + '=');
    if (typeof v !== 'string') continue;
    const re = new RegExp('(\\s' + attr + '=")[^"]*(")');
    tagSrc = re.test(tagSrc) ? tagSrc.replace(re, '$1' + escAttr(v) + '$2') : tagSrc.replace(/\sdata-t-attr=/, ` ${attr}="${escAttr(v)}" data-t-attr=`);
  }
  return tagSrc;
});
// elements with data-t that contain markup would not be filled: report them
for (const m of out.matchAll(/<([a-z0-9]+)\b[^>]*\sdata-t="([^"]+)"[^>]*>(?=[^<]*<(?!\/\1>))/g)) problems.push(`"${m[2]}" on <${m[1]}> contains child elements`);

// list items present in the dictionary but missing from the markup (e.g. a 7th industry added later)
for (const list of ['eco', 'whys', 'steps', 'trusts', 'industries', 'regions', 'docs', 'aog_req']) {
  D.en[list].forEach((_, i) => { if (![...used].some(k => k === `${list}.${i}` || k.startsWith(`${list}.${i}.`))) problems.push(`"${list}.${i}" exists in js/i18n.js but is not on the home page`); });
}

if (process.argv.includes('--check')) {
  if (out !== src) problems.push('index.html is out of date: run node tools/prerender-home.mjs');
} else if (out !== src) { writeFileSync(file, out); console.log('index.html updated'); }
else console.log('index.html already up to date');
if (problems.length) { console.error(problems.map(p => '  - ' + p).join('\n')); process.exitCode = 1; }
else console.log(used.size + ' keys OK in en and ar');
