const fs = require('fs');
const https = require('https');
const out = process.argv[2], urls = process.argv.slice(3);
function tryNext(i) {
  if (i >= urls.length) { console.error('ALL FAILED'); process.exit(1); }
  const url = urls[i];
  console.log('trying ' + url);
  const req = https.get(url, { headers: { 'User-Agent': 'Mozilla/5.0' }, timeout: 20000 }, res => {
    if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
      res.resume(); return tryRedirect(res.headers.location, i);
    }
    if (res.statusCode !== 200) { console.error('HTTP ' + res.statusCode); return tryNext(i + 1); }
    const f = fs.createWriteStream(out);
    res.pipe(f);
    f.on('finish', () => f.close(() => { console.log('DONE ' + fs.statSync(out).size + ' bytes'); }));
  });
  req.on('timeout', () => { req.destroy(new Error('timeout')); });
  req.on('error', e => { console.error(String(e)); tryNext(i + 1); });
}
function tryRedirect(loc, i) {
  const req = https.get(loc, { headers: { 'User-Agent': 'Mozilla/5.0' }, timeout: 20000 }, res => {
    if (res.statusCode !== 200) { console.error('HTTP ' + res.statusCode); return tryNext(i + 1); }
    const f = fs.createWriteStream(out);
    res.pipe(f);
    f.on('finish', () => f.close(() => { console.log('DONE ' + fs.statSync(out).size + ' bytes'); }));
  });
  req.on('timeout', () => { req.destroy(new Error('timeout')); });
  req.on('error', e => { console.error(String(e)); tryNext(i + 1); });
}
tryNext(0);
