/**
 * 流式 ZIP（只存不压）—— 在 Worker 里把 R2 对象直接拼成一个 zip 流下载
 *
 * 为什么能做到「零 CPU」：zip 需要每个文件的 CRC32 和大小写在文件头里。
 * 一般的流式 zip 只能边读边算 CRC（Worker 要把几个 GB 的视频逐字节过一遍，CPU 必超），
 * 或者用 data descriptor 把 CRC 放到文件后面（很多解压器支持得不好）。
 * 这里 CRC32 在**上传时由浏览器顺手算好**存进库（它反正要逐块算 SHA-256），
 * 所以下载时每个文件头都是事先就能写出来的 —— Worker 只做字节搬运，
 * 而且**总长度能提前算出来** → 浏览器下载条能显示真实进度和剩余时间。
 *
 * 照片/视频本来就是压缩格式，再 deflate 一遍几乎省不了空间，只存不压是对的。
 * 超过 4 GB 的文件或整个包超过 4 GB 时自动写 ZIP64 扩展（macOS / Windows / unzip 都认）。
 */

const U32 = 0xFFFFFFFF;
const enc = new TextEncoder();

function dos(dt) {
  // dt: 'YYYY-MM-DDTHH:MM:SS'（本地墙钟时间）→ DOS 时间/日期
  const m = /^(\d{4})-(\d\d)-(\d\d)T(\d\d):(\d\d):(\d\d)/.exec(dt || '');
  if (!m) return { time: 0, date: (1 << 5) | 1 };            // 1980-01-01
  const [Y, Mo, D, h, mi, s] = m.slice(1).map(Number);
  return { time: (h << 11) | (mi << 5) | (s >> 1), date: ((Math.max(Y, 1980) - 1980) << 9) | (Mo << 5) | D };
}

/** entries: [{name, size, crc, mtime}] → 每个条目的 header 字节 + 中央目录 + 总长度 */
export function zipPlan(entries, { force64 = false } = {}) {
  let off = 0;
  const locals = [], cds = [];
  for (const e of entries) {
    const name = enc.encode(e.name);
    const big = force64 || e.size >= U32;
    const { time, date } = dos(e.mtime);
    // —— 本地文件头 ——
    const lx = big ? 20 : 0;
    const lh = new DataView(new ArrayBuffer(30 + name.length + lx));
    lh.setUint32(0, 0x04034b50, true);
    lh.setUint16(4, big ? 45 : 20, true);
    lh.setUint16(6, 0x0800, true);                       // bit 11：文件名是 UTF-8（中文名不乱码）
    lh.setUint16(8, 0, true);                            // method 0 = store
    lh.setUint16(10, time, true); lh.setUint16(12, date, true);
    lh.setUint32(14, e.crc >>> 0, true);
    lh.setUint32(18, big ? U32 : e.size, true);
    lh.setUint32(22, big ? U32 : e.size, true);
    lh.setUint16(26, name.length, true);
    lh.setUint16(28, lx, true);
    new Uint8Array(lh.buffer).set(name, 30);
    if (big) {
      const p = 30 + name.length;
      lh.setUint16(p, 0x0001, true); lh.setUint16(p + 2, 16, true);
      lh.setBigUint64(p + 4, BigInt(e.size), true); lh.setBigUint64(p + 12, BigInt(e.size), true);
    }
    const local = new Uint8Array(lh.buffer);
    // —— 中央目录条目 ——
    const offBig = force64 || off >= U32;
    const xs = (big ? 16 : 0) + (offBig ? 8 : 0);
    const cx = xs ? 4 + xs : 0;
    const ch = new DataView(new ArrayBuffer(46 + name.length + cx));
    ch.setUint32(0, 0x02014b50, true);
    ch.setUint16(4, 45, true); ch.setUint16(6, (big || offBig) ? 45 : 20, true);
    ch.setUint16(8, 0x0800, true); ch.setUint16(10, 0, true);
    ch.setUint16(12, time, true); ch.setUint16(14, date, true);
    ch.setUint32(16, e.crc >>> 0, true);
    ch.setUint32(20, big ? U32 : e.size, true); ch.setUint32(24, big ? U32 : e.size, true);
    ch.setUint16(28, name.length, true); ch.setUint16(30, cx, true);
    ch.setUint32(42, offBig ? U32 : off, true);
    new Uint8Array(ch.buffer).set(name, 46);
    if (cx) {
      let p = 46 + name.length;
      ch.setUint16(p, 0x0001, true); ch.setUint16(p + 2, xs, true); p += 4;
      if (big) { ch.setBigUint64(p, BigInt(e.size), true); ch.setBigUint64(p + 8, BigInt(e.size), true); p += 16; }
      if (offBig) ch.setBigUint64(p, BigInt(off), true);
    }
    locals.push(local); cds.push(new Uint8Array(ch.buffer));
    off += local.length + e.size;
  }
  const cdOff = off, cdSize = cds.reduce((a, b) => a + b.length, 0);
  const need64 = force64 || cdOff >= U32 || cdSize >= U32 || entries.length >= 0xFFFF;
  const tail = [];
  if (need64) {
    const z = new DataView(new ArrayBuffer(56 + 20));
    z.setUint32(0, 0x06064b50, true); z.setBigUint64(4, 44n, true);
    z.setUint16(12, 45, true); z.setUint16(14, 45, true);
    z.setBigUint64(24, BigInt(entries.length), true); z.setBigUint64(32, BigInt(entries.length), true);
    z.setBigUint64(40, BigInt(cdSize), true); z.setBigUint64(48, BigInt(cdOff), true);
    z.setUint32(56, 0x07064b50, true); z.setBigUint64(64, BigInt(cdOff + cdSize), true); z.setUint32(72, 1, true);
    tail.push(new Uint8Array(z.buffer));
  }
  const eo = new DataView(new ArrayBuffer(22));
  eo.setUint32(0, 0x06054b50, true);
  const n16 = need64 ? 0xFFFF : entries.length;
  eo.setUint16(8, n16, true); eo.setUint16(10, n16, true);
  eo.setUint32(12, need64 ? U32 : cdSize, true); eo.setUint32(16, need64 ? U32 : cdOff, true);
  tail.push(new Uint8Array(eo.buffer));
  const total = off + cdSize + tail.reduce((a, b) => a + b.length, 0);
  return { locals, cds, tail, total };
}

/** 顺序写：本地头 → 文件字节（open(i) 返回 ReadableStream）→ … → 中央目录 → 结尾 */
export async function zipWrite(writable, plan, open) {
  const w = writable.getWriter();
  try {
    for (let i = 0; i < plan.locals.length; i++) {
      await w.write(plan.locals[i]);
      const body = await open(i);
      const r = body.getReader();
      for (;;) { const { done, value } = await r.read(); if (done) break; await w.write(value); }
    }
    for (const c of plan.cds) await w.write(c);
    for (const t of plan.tail) await w.write(t);
    await w.close();
  } catch (e) {
    try { await w.abort(e); } catch { /* 客户端已经断开 */ }
  }
}

/** 给文件名去重：同一个 zip 里两个 IMG_0001.JPG 会互相覆盖 */
export function uniqueNames(names) {
  const seen = new Map();
  return names.map(n => {
    const k = n.toLowerCase();
    const c = seen.get(k) || 0; seen.set(k, c + 1);
    if (!c) return n;
    const dot = n.lastIndexOf('.');
    const slash = n.lastIndexOf('/');
    return dot > slash ? `${n.slice(0, dot)} (${c + 1})${n.slice(dot)}` : `${n} (${c + 1})`;
  });
}
