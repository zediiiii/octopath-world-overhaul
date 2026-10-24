"""Make the "k" glyph for big damage numbers -> src/data/damage_k.bin (dev only).

The battle damage font (UiTX_Battle_DamageFont_atlas) is 10 digit columns x 5 colour rows
with no letters. src/damage_k.py widens it to 20 columns and puts a "k" in column 10; this
script draws that column once, so the build needs only the standard library.

Each colour row's look is measured from its own digits: the colour at every depth inside
the glyph edge (outline, rim, fill gradient) for every height, and the drop shadow (offset,
falloff, colour). A Times New Roman Bold Italic "k" (same narrow italic serif build as the
digits) is then painted with those measurements, at the x2 atlas's resolution, and halved
for the x1 atlas. Both strips are DXT5-compressed (Pillow) and stored zlib-packed.

    python dev/make_damage_k.py [preview.png]      (needs pillow, numpy, scipy)
"""
import io
import os
import struct
import sys
import zlib

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import damage_k  # noqa: E402
import pak  # noqa: E402
import paths  # noqa: E402

FONT = r"C:\Windows\Fonts\timesbi.ttf"
SS = 4                      # supersampling of the x2 atlas while painting
BG = (0x2e, 0x2c, 0x2b)     # colour the atlas keeps under fully transparent pixels
K_HEIGHT = 0.78             # the k's ink height / the digits' (a full-height k is too wide)
K_WIDTH = 0.80              # horizontal squeeze, to the digits' narrow build
BOLD = 1.0                  # x2 px added around the font's strokes: the digits are heavier


def decode_dxt5(data, w, h):
    b = np.frombuffer(data, np.uint8).reshape(h // 4, w // 4, 16).astype(np.int64)
    a0, a1 = b[..., 0], b[..., 1]
    abits = sum(b[..., 2 + i] << (8 * i) for i in range(6))
    pal = np.zeros(b.shape[:2] + (8,), np.int64)
    pal[..., 0], pal[..., 1] = a0, a1
    gt = a0 > a1
    for i in range(2, 8):
        pal[..., i] = np.where(gt, ((8 - i) * a0 + (i - 1) * a1) // 7,
                               ((6 - i) * a0 + (i - 1) * a1) // 5 if i < 6 else (0 if i == 6 else 255))
    c0 = b[..., 8] | (b[..., 9] << 8)
    c1 = b[..., 10] | (b[..., 11] << 8)
    rgb = lambda c: np.stack([((c >> 11) & 31) * 255 // 31, ((c >> 5) & 63) * 255 // 63,
                              (c & 31) * 255 // 31], -1)
    C0, C1 = rgb(c0), rgb(c1)
    cp = np.stack([C0, C1, (2 * C0 + C1) // 3, (C0 + 2 * C1) // 3], -2)
    cbits = b[..., 12] | (b[..., 13] << 8) | (b[..., 14] << 16) | (b[..., 15] << 24)
    out = np.zeros((h, w, 4), np.uint8)
    for k in range(16):
        py, px = divmod(k, 4)
        ai = (abits >> (3 * k)) & 7
        ci = (cbits >> (2 * k)) & 3
        out[py::4, px::4, 3] = np.take_along_axis(pal, ai[..., None], -1)[..., 0]
        out[py::4, px::4, :3] = np.take_along_axis(cp, ci[..., None, None].repeat(3, -1), -2)[..., 0, :]
    return out


def encode_dxt5(img):
    buf = io.BytesIO()
    Image.fromarray(img, "RGBA").save(buf, "DDS", pixel_format="DXT5")
    d = buf.getvalue()
    return d[128:]                                    # skip the DDS header


BINS = 24                   # distance profiles: half-pixel bins, zero from 12 px out


def profile(dist, value, mask):
    """Mean of value per half-pixel bin of dist over mask; empty bins interpolated."""
    b = np.round(dist[mask] * 2).astype(int)
    keep = b < BINS
    s = np.bincount(b[keep], value[mask][keep], BINS)
    n = np.bincount(b[keep], None, BINS)
    x = np.nonzero(n)[0]
    prof = np.interp(np.arange(BINS), x, s[x] / n[x]) if len(x) else np.zeros(BINS)
    low = np.nonzero(prof < 0.03)[0]
    prof[low[0] if len(low) else -1:] = 0            # drop the faint, noisy tail
    return prof


def curve(prof, dist):
    return np.interp(dist * 2, np.arange(len(prof)), prof, right=0)


def row_style(band):
    """Measure one colour row (x2 atlas band, h x 1024 x 4) -> style dict."""
    a = band[..., 3].astype(float) / 255
    rgb = band[..., :3].astype(float)
    sil = (a > 0.5) & (rgb.max(-1) > 0x50)
    sil = ndimage.binary_opening(sil)
    depth = ndimage.distance_transform_edt(sil)
    h = band.shape[0]
    maxd = int(depth.max()) + 2
    # colour per (height, depth): the median over a 9-pixel band of heights. A median keeps
    # the outline / fill boundary sharp where a mean would smear it over several pixels.
    lut = np.zeros((h, maxd, 3))
    have = np.zeros((h, maxd), bool)
    ys, xs = np.nonzero(sil & (a > 0.98))
    di = np.clip(np.round(depth[ys, xs]).astype(int), 0, maxd - 1)
    lum = rgb[ys, xs].sum(-1)
    for d in range(maxd):
        sel = np.nonzero(di == d)[0]
        sel = sel[np.argsort(ys[sel])]
        yd = ys[sel]
        for y in range(h):
            lo, hi = np.searchsorted(yd, [y - 4, y + 5])
            if hi > lo:
                band_ = sel[lo:hi]
                pick = band_[np.argsort(lum[band_])[(hi - lo) // 2]]
                lut[y, d], have[y, d] = rgb[ys[pick], xs[pick]], True
    idx = ndimage.distance_transform_edt(~have, return_distances=False, return_indices=True)
    lut = lut[idx[0], idx[1]]
    # shadow: outside the glyph, alpha = a soft halo around it combined with a drop shadow
    # (the glyph shifted by s); each a function of distance, fitted per shift
    out = ~sil
    d0 = ndimage.distance_transform_edt(~sil)
    best = None
    for sx in range(0, 9):
        for sy in range(0, 9):
            d1 = ndimage.distance_transform_edt(~np.roll(np.roll(sil, sy, 0), sx, 1))
            halo = profile(d0, a, out & (d1 > 8))
            rest = 1 - (1 - a) / np.maximum(1 - curve(halo, d0), 1e-3)
            drop = profile(d1, np.clip(rest, 0, 1), out)
            model = 1 - (1 - curve(halo, d0)) * (1 - curve(drop, d1))
            err = ((a[out] - model[out]) ** 2).sum()
            if best is None or err < best[0]:
                best = (err, sx, sy, halo, drop)
    _e, sx, sy, halo, drop = best
    sm = out & (a > 0.3)
    shadow_rgb = (rgb[sm] * a[sm][:, None]).sum(0) / a[sm].sum()
    ys, xs = np.nonzero(sil)
    return dict(lut=lut, shift=(sx, sy), halo=halo, drop=drop, shadow_rgb=shadow_rgb,
                top=ys.min(), bottom=ys.max())


def digit_boxes(band):
    """Silhouette x-extent of every digit cell in a x2 band -> [(left, right)] cell-relative."""
    a = band[..., 3] > 128
    out = []
    for c in range(10):
        x0, x1 = int(round(c * 102.4)), int(round((c + 1) * 102.4))
        cols = np.nonzero(a[:, x0:x1].any(0))[0]
        out.append((cols.min() + x0 - c * 102.4, cols.max() + x0 - c * 102.4))
    return out


def k_mask(height_px, width_scale):
    """Supersampled fill mask of the k: its ink spans height_px (x2 pixels) top to bottom."""
    font = ImageFont.truetype(FONT, 400)
    im = Image.new("L", (600, 600), 0)
    ImageDraw.Draw(im).text((100, 50), "k", font=font, fill=255)
    m = np.array(im)
    ys, xs = np.nonzero(m > 127)
    m = m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    s = height_px * SS / m.shape[0]
    im = Image.fromarray(m).resize((max(1, round(m.shape[1] * s * width_scale)),
                                    round(m.shape[0] * s)), Image.LANCZOS)
    return np.array(im).astype(float) / 255


def paint(style, mask, ox, oy, cell_h, outline):
    """Paint the k into a supersampled cell -> float RGBA (cell_h*SS x 128*SS x 4)."""
    H, W = int(np.ceil(cell_h)) * SS, 128 * SS
    fill = np.zeros((H, W))
    mh, mw = mask.shape
    fill[oy:oy + mh, ox:ox + mw] = mask
    inside_fill = fill > 0.5
    # glyph silhouette = fill grown by the outline width; depth measured from its edge
    grow = ndimage.distance_transform_edt(~inside_fill) / SS
    sil = grow <= BOLD + outline
    depth = ndimage.distance_transform_edt(sil) / SS
    lut = style["lut"]
    yy = np.clip((np.arange(H) / SS).astype(int), 0, lut.shape[0] - 1)[:, None].repeat(W, 1)
    dd = np.clip(depth, 0, lut.shape[1] - 1)
    d0 = np.floor(dd).astype(int)
    d1 = np.minimum(d0 + 1, lut.shape[1] - 1)
    t = (dd - d0)[..., None]
    col = lut[yy, d0] * (1 - t) + lut[yy, d1] * t
    sx, sy = style["shift"]
    d1 = ndimage.distance_transform_edt(~np.roll(np.roll(sil, sy * SS, 0), sx * SS, 1)) / SS
    d0 = ndimage.distance_transform_edt(~sil) / SS
    sa = 1 - (1 - curve(style["halo"], d0)) * (1 - curve(style["drop"], d1))
    rgba = np.zeros((H, W, 4))
    rgba[..., :3] = np.where(sil[..., None], col, style["shadow_rgb"])
    rgba[..., 3] = np.where(sil, 1.0, sa)
    return rgba


def downsample(rgba, f):
    h, w = rgba.shape[0] // f * f, rgba.shape[1] // f * f
    r = rgba[:h, :w]
    pm = r[..., :3] * r[..., 3:4]
    pm = pm.reshape(h // f, f, w // f, f, 3).mean((1, 3))
    a = r[..., 3].reshape(h // f, f, w // f, f).mean((1, 3))
    rgb = np.where(a[..., None] > 1e-4, pm / np.maximum(a[..., None], 1e-4), BG)
    return np.concatenate([rgb, a[..., None]], -1)


def main():
    base = pak.Pak(paths.base_pak())
    x2 = decode_dxt5(damage_k.texture_mips(base.read(damage_k.TEXTURES[1] + ".uexp"))[0],
                     1024, 1024)
    boxes = np.array([digit_boxes(x2[int(round(r * 204.8)):int(round((r + 1) * 204.8))])
                      for r in range(5)])
    left, right = boxes[..., 0].mean(), boxes[..., 1].mean()
    styles = []
    for r in range(5):
        y0, y1 = int(round(r * 204.8)), int(round((r + 1) * 204.8))
        styles.append(row_style(x2[y0:y1]))
    outline = 4.75
    strip = np.zeros((1024, 128, 4))
    strip[..., :3] = BG
    for r, st in enumerate(styles):
        y0, y1 = int(round(r * 204.8)), int(round((r + 1) * 204.8))
        ink_h = st["bottom"] - st["top"] + 1 - 2 * (outline + BOLD)
        mask = k_mask(ink_h * K_HEIGHT, K_WIDTH)
        ox = int(((left + right) / 2 - 2) * SS - mask.shape[1] / 2)
        # keep the outline and shadow inside the cell (x2: 102.4 px; the shadow fades ~4 px)
        ox = min(ox, int((99 - BOLD - outline - st["shift"][0] - 4) * SS) - mask.shape[1])
        oy = int((st["bottom"] + 1 - outline - BOLD) * SS) - mask.shape[0]   # on the digits' baseline
        cell = downsample(paint(st, mask, ox, oy, y1 - y0, outline), SS)
        strip[y0:y1] = cell[:y1 - y0]
    # nothing may spill past the cell's right edge (x2: 102.4 px) into the empty columns
    assert strip[:, 100:, 3].max() < 0.02, strip[:, 100:, 3].max()
    strip[:, 100:, 3] = 0
    strip[..., :3] = np.where(strip[..., 3:4] > 0, strip[..., :3], BG)
    s2 = np.clip(np.round(np.concatenate([strip[..., :3], strip[..., 3:] * 255], -1)), 0, 255).astype(np.uint8)
    s1f = downsample(strip, 2)
    s1 = np.clip(np.round(np.concatenate([s1f[..., :3], s1f[..., 3:] * 255], -1)), 0, 255).astype(np.uint8)
    b1, b2 = encode_dxt5(s1), encode_dxt5(s2)
    assert len(b1) == 16 * 128 * 16 and len(b2) == 32 * 256 * 16
    with open(damage_k.GLYPH, "wb") as f:
        f.write(zlib.compress(struct.pack("<II", len(b1), len(b2)) + b1 + b2, 9))
    print("wrote", damage_k.GLYPH, os.path.getsize(damage_k.GLYPH), "bytes;",
          "shadow shifts", [s["shift"] for s in styles])
    if len(sys.argv) > 1:
        # preview: the x2 atlas row with its new k column, on a dark background
        prev = np.concatenate([x2[:, :1024], decode_dxt5(b2, 128, 1024)], 1)
        im = Image.fromarray(prev, "RGBA")
        bg = Image.new("RGBA", im.size, (40, 40, 90, 255))
        bg.alpha_composite(im)
        bg.save(sys.argv[1])


if __name__ == "__main__":
    main()
