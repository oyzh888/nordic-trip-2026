"""视频转码 + 调色：把相机原片转成「谁都能播、颜色正常」的 H.264。原片一个字节都不动，另存一份（R2 的 g/<h>.mp4）。

为什么要转：
  · 编码：Canon R5 / 大疆 / 新 iPhone 录的是 H.265（HEVC），Windows 上的 Chrome、很多安卓机放不了；H.264 到处都能放
  · 颜色：R5 开 Canon Log 3 录的画面是「灰」的 —— Log 是给后期调色留余地的曲线，不是给人直接看的；
    HDR（PQ / HLG）在普通屏幕上也是发白发灰。要套一个转换，才是正常观看的颜色
  · 尺寸：8K 的 H.264 手机基本解不动，新版长边最多 4K（3840）

怎么判断是哪一种（plan）：
  · color_transfer = smpte2084 → 'pq'（HDR PQ，R5 的「HDR PQ」模式）→ 色调映射到 SDR
  · color_transfer = arib-std-b67 → 'hlg'（iPhone 的 HDR 视频）→ 色调映射到 SDR
  · 佳能拍的、10-bit 4:2:2 的 HEVC、画面「没有真正的黑」（最暗 0.5% 的像素都不低于 4%）→ Canon Log 3
    —— R5 只有开 Canon Log / HDR PQ 时才录 10-bit 4:2:2 HEVC（HDR PQ 上一条已经认出来了）；手机和无人机都是 4:2:0。
    「是佳能」看三处任一：MP4 的品牌里有佳能自己的 CAEP、元数据里的相机是 Canon、文件名和这个人传过的佳能照片同一个前缀。
    别的牌子的 10-bit Log（S-Log / V-Log / F-Log）套佳能的表会调坏，所以不是佳能的只转码不调色。
    最暗像素那一条是第二道保险：Log 3 的 0% 黑在 ~7% 处，一段有真黑的片子不会是 Log。
    色域：color_primaries = bt2020 → 'clog3-2020'（佳能 BT.2020 → BT.709 WideDR），否则 → 'clog3-cg'（Cinema Gamut → Canon 709）
  · 其它不是 H.264 的（HEVC / ProRes / AV1 / VP9…）或 10-bit 的 → 'transcode'：只转码，不动颜色
  · 已经是 8-bit H.264 的普通视频 → 'none'：不用转（iPhone 经 Safari 选图上来的就是这样），省空间

LUT 是佳能官网的（canon.com「Canon lookup table」，版权归佳能，不进仓库）：setup_gpu.sh 装到 LUT_DIR。
文件名里的 FF = 输入全范围、输出全范围（佳能 ReadMe：「Input range N: Narrow, F: Full」）。
「输入全范围」的意思是：喂给它的 RGB = 文件里存的码值 ÷ 1023，**不做电视电平展开**。
这是量出来的，不是猜的：这张表的中性轴在输入 ≈ 0.12 处才开始离开 0（= Canon Log 3 的 0% 黑，码值 128/1023），
18% 灰（Log 3 码值 0.331）出来是 0.411（Rec.709 里 18% 灰正是 ≈ 0.409）。要是按电视电平展开再喂，18% 灰会变成 0.375，整体偏暗。
所以 Log 片子解码时强制按全范围读（in_range=pc），查完表再按普通视频（BT.709 电视电平）编码。
"""
import json
import os
import subprocess
from pathlib import Path

LUT_DIR = Path(os.environ.get('CANON_LUT_DIR', '/mnt/localssd/photos-cache/lut'))
LUTS = {
    'clog3-cg': 'canon-lut-canon709-202508/65grid-3dlut/CinemaGamut_CanonLog3-to-Canon709_65_Ver.1.0.cube',
    'clog3-2020': 'canon-lut-202510/3dlut/65grid-3dlut/full-to-full-range/BT2020_CanonLog3-to-BT709_WideDR_65_FF_Ver.2.0.cube',
}
LABEL = {'none': '不用转', 'transcode': 'H.264（颜色不变）', 'clog3-cg': 'H.264 · Canon Log 3 → Canon 709',
         'clog3-2020': 'H.264 · Canon Log 3（BT.2020）→ BT.709', 'pq': 'H.264 · HDR PQ → SDR', 'hlg': 'H.264 · HDR HLG → SDR'}
MAX_SIDE = 3840
THREADS = int(os.environ.get('TRANSCODE_THREADS', '12'))     # 留几个核给照片分析


def probe(path):
    r = subprocess.run(['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', '-show_streams', str(path)],
                       capture_output=True, text=True, timeout=300)
    info = json.loads(r.stdout or '{}')
    vs = next((s for s in info.get('streams', []) if s.get('codec_type') == 'video'), None)
    aus = next((s for s in info.get('streams', []) if s.get('codec_type') == 'audio'), None)
    return info, vs, aus


def darkest(path, vs):
    """原片（不调色）里抽几帧，最暗 0.5% 像素的亮度（0–1，电视电平已展开）。Log 素材没有真正的黑"""
    dur = float(vs.get('duration') or 0) or 3
    vals = []
    for t in (min(1, dur / 4), dur / 2, dur * 0.8):
        r = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{t:.2f}', '-i', str(path), '-frames:v', '1',
                            '-vf', 'scale=320:-2:out_range=pc,format=gray', '-f', 'rawvideo', '-'], capture_output=True, timeout=120)
        if r.stdout:
            import numpy as np
            a = np.frombuffer(r.stdout, np.uint8).astype(float) / 255
            vals.append(float(np.percentile(a, 0.5)))
    return min(vals) if vals else None


def is_canon(info, cam=None, canon_name=False):
    f = info.get('format', {}) if info else {}
    tags = {k.lower(): str(v) for k, v in (f.get('tags') or {}).items()}
    brands = (tags.get('major_brand', '') + ' ' + tags.get('compatible_brands', '')).upper()
    return 'CAEP' in brands or (cam or '').lower().startswith('canon') or bool(canon_name)


def plan_for(path, vs=None, info=None, cam=None, canon_name=False):
    """→ (plan, 说明)。cam / canon_name：worker 从库里知道的「这台相机是谁」「文件名像不像这个人的佳能照片」"""
    if vs is None:
        info, vs, _ = probe(path)
    if not vs:
        return 'none', '没有视频轨'
    codec, pix, trc = vs.get('codec_name'), vs.get('pix_fmt') or '', vs.get('color_transfer') or ''
    if trc == 'smpte2084':
        return 'pq', 'HDR PQ'
    if trc == 'arib-std-b67':
        return 'hlg', 'HDR HLG'
    tenbit = '10' in pix or '12' in pix
    if codec == 'hevc' and '422' in pix and tenbit:
        dk = darkest(path, vs)
        if dk is not None and dk >= 0.04 and not is_canon(info, cam, canon_name):
            return 'transcode', f'10-bit 4:2:2 HEVC、像 Log，但看不出是佳能拍的 —— 只转码，不套佳能的 LUT'
        if dk is not None and dk >= 0.04:
            gamut = 'clog3-2020' if vs.get('color_primaries') == 'bt2020' else 'clog3-cg'
            if (LUT_DIR / LUTS[gamut]).exists():
                return gamut, f'10-bit 4:2:2 HEVC，最暗处 {dk:.0%}（没有真黑 → Canon Log）'
            return 'transcode', f'像 Canon Log，但没找到 LUT（{LUTS[gamut]}）—— 只转码'
        return 'transcode', f'10-bit 4:2:2 HEVC，但最暗处 {dk if dk is None else f"{dk:.0%}"}（有真黑，不像 Log）—— 只转码'
    if codec != 'h264' or tenbit:
        return 'transcode', f'{codec} {pix}'
    return 'none', '已经是 8-bit H.264'


def color_vf(plan, vs):
    """调色这一段滤镜（输出 BT.709 电视电平的 YUV）；'transcode' / 'none' 只做像素格式转换"""
    if plan in LUTS:
        # 展开成全范围 16-bit RGB（按片子自己的矩阵：BT.2020 片子要用 bt2020 矩阵）→ 查表 → BT.709 电视电平
        m = 'bt2020' if vs.get('color_space', '').startswith('bt2020') or plan == 'clog3-2020' else 'bt709'
        lut = str(LUT_DIR / LUTS[plan]).replace(':', r'\:')
        return (f"scale=in_color_matrix={m}:in_range=pc:out_range=pc,format=gbrp16le,"
                f"lut3d=file='{lut}':interp=tetrahedral,scale=out_color_matrix=bt709:out_range=tv,format=yuv420p")
    if plan in ('pq', 'hlg'):
        tin = 'smpte2084' if plan == 'pq' else 'arib-std-b67'
        return (f"zscale=tin={tin}:t=linear:npl=100:min=bt2020nc:pin=bt2020,format=gbrpf32le,zscale=p=bt709,"
                f"tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv,format=yuv420p")
    return 'format=yuv420p'


def size_vf(vs):
    w, h = int(vs.get('width') or 0), int(vs.get('height') or 0)
    if max(w, h) <= MAX_SIDE:
        return None
    return f"scale='if(gte(iw,ih),{MAX_SIDE},-2)':'if(gte(iw,ih),-2,{MAX_SIDE})'"


def convert(src, dst, plan, vs, aus):
    """原片 → H.264 新版（保留拍摄时间 / GPS 等元数据和旋转）。返回 ffmpeg 用时（秒）"""
    import time
    vf = ','.join(x for x in (size_vf(vs), color_vf(plan, vs)) if x)
    a = ['-c:a', 'copy'] if aus and aus.get('codec_name') == 'aac' else (['-c:a', 'aac', '-b:a', '192k'] if aus else ['-an'])
    t = time.time()
    r = subprocess.run(['ffmpeg', '-v', 'error', '-y', '-threads', str(THREADS), '-i', str(src), '-map', '0:v:0', '-map', '0:a:0?',
                        '-vf', vf, '-c:v', 'libx264', '-preset', 'medium', '-crf', '19', '-profile:v', 'high',
                        '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709', '-color_range', 'tv',
                        *a, '-map_metadata', '0', '-movflags', '+faststart+use_metadata_tags', '-threads', str(THREADS), str(dst)],
                       capture_output=True, text=True, timeout=6 * 3600)
    if r.returncode:
        raise RuntimeError('ffmpeg: ' + r.stderr[-400:])
    return time.time() - t
