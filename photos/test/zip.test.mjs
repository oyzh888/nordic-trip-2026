// zip.js 单元测试：生成的 zip 必须能被 Python zipfile（逐个校验 CRC）和 `unzip -t` 通过，
// 普通模式和强制 ZIP64 模式各一次。用法：node test/zip.test.mjs <输出目录>
import { zipPlan, zipWrite, uniqueNames } from '../src/zip.js';
import { writeFileSync, mkdirSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { randomBytes } from 'node:crypto';

const T = new Uint32Array(256).map((_, n) => { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1; return c >>> 0; });
const crc32 = u8 => { let c = ~0 >>> 0; for (const b of u8) c = T[(c ^ b) & 0xFF] ^ (c >>> 8); return ~c >>> 0; };

const out = process.argv[2] || 'test/out'; mkdirSync(out, { recursive: true });
const files = [
  ['09-25/IMG_0001.JPG', randomBytes(300_000)],
  ['09-25/IMG_0001.JPG', randomBytes(1234)],            // 同名 → 必须被改名，否则解压时互相覆盖
  ['09-27/极光 视频.mov', randomBytes(2_500_000)],        // 中文 + 空格文件名（UTF-8 标志位）
  ['10-01/empty.txt', new Uint8Array(0)],
];
const names = uniqueNames(files.map(f => f[0]));
let fails = 0;
for (const force64 of [false, true]) {
  const entries = files.map(([, b], i) => ({ name: names[i], size: b.length, crc: crc32(b), mtime: '2026-09-27T22:14:05' }));
  const plan = zipPlan(entries, { force64 });
  const chunks = [];
  const ws = new WritableStream({ write(c) { chunks.push(Buffer.from(c)); } });
  await zipWrite(ws, plan, async i => new Blob([files[i][1]]).stream());
  const buf = Buffer.concat(chunks);
  const p = `${out}/t${force64 ? 64 : 32}.zip`; writeFileSync(p, buf);
  const lenOk = buf.length === plan.total;
  const py = execFileSync('python3', ['-c', `
import zipfile,sys,hashlib
z=zipfile.ZipFile(sys.argv[1]); bad=z.testzip()
print('names', [i.filename for i in z.infolist()])
print('dates', {i.date_time for i in z.infolist()})
print('testzip', bad)`, p]).toString();
  let unz = ''; try { unz = execFileSync('unzip', ['-t', p]).toString().trim().split('\n').pop(); } catch (e) { unz = 'FAIL ' + e.stdout; }
  const ok = lenOk && /testzip None/.test(py) && /No errors/.test(unz) && py.includes('IMG_0001 (2).JPG') && py.includes('极光 视频.mov') && py.includes('(2026, 9, 27, 22, 14, 4)');
  if (!ok) fails++;
  console.log(`${ok ? 'PASS' : 'FAIL'} force64=${force64} size=${buf.length} predicted=${plan.total}\n${py}  unzip: ${unz}`);
}
process.exit(fails ? 1 : 0);
