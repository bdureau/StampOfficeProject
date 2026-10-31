"""
Excel Album Importer (.xls)
---------------------------
Converts the old "Album de Timbres" stamp albums made with Excel/VBA
(BIFF8 .xls files) into Stamp Album pages.

In these workbooks, each album page is a CHART SHEET named PAGE-xx. The content
is not stored in cells but in the Office drawing layer (OfficeArt):
  - a full-page rectangle               -> page border (replaced by the app's border)
  - one group per stamp, containing:
        description (above the box), "Format WxH" box, picture,
        number and value (below the box)
  - free text boxes                     -> year, copyright, page number, texts

The file is read directly (olefile + BIFF8/OfficeArt decoding): Excel is not
required. Only extra dependency:  pip install olefile

Author: Boris du Reau
"""
import re
import struct
from dataclasses import dataclass, field

PX_PER_MM = 96.0 / 25.4
SPRC = 4000.0          # chart sheet anchors are in 1/4000 of the printable area


def mm(v):
    return float(v) * PX_PER_MM


# ============================================================================
# 1. BIFF8 reading
# ============================================================================

def _read_records(data: bytes):
    recs, pos = [], 0
    while pos + 4 <= len(data):
        t, ln = struct.unpack_from('<HH', data, pos)
        recs.append((pos, t, data[pos + 4:pos + 4 + ln]))
        pos += 4 + ln
    return recs


def _xl_string(d: bytes, off: int, cch: int = None, len_bytes: int = 1) -> str:
    if cch is None:
        cch = d[off] if len_bytes == 1 else struct.unpack_from('<H', d, off)[0]
        off += len_bytes
    flags = d[off]
    off += 1
    if flags & 0x08:          # rich text runs count
        off += 2
    if flags & 0x04:          # far east data size
        off += 4
    if flags & 0x01:
        return d[off:off + 2 * cch].decode('utf-16le', errors='replace')
    return d[off:off + cch].decode('latin-1', errors='replace')


# ============================================================================
# 2. OfficeArt reading
# ============================================================================

@dataclass
class ArtRec:
    rtype: int
    inst: int
    data: bytes = b''
    children: list = field(default_factory=list)


def _art_records(b: bytes, off: int = 0, end: int = None):
    end = len(b) if end is None else end
    out = []
    while off + 8 <= end:
        vi, rtype, ln = struct.unpack_from('<HHI', b, off)
        ver, inst = vi & 0xF, vi >> 4
        body_end = min(off + 8 + ln, end)
        if ver == 0xF:
            out.append(ArtRec(rtype, inst, children=_art_records(b, off + 8, body_end)))
        else:
            out.append(ArtRec(rtype, inst, data=b[off + 8:body_end]))
        off = off + 8 + ln
    return out


def _opt_props(rec: ArtRec) -> dict:
    props = {}
    for k in range(rec.inst):
        if k * 6 + 6 > len(rec.data):
            break
        pid, val = struct.unpack_from('<HI', rec.data, k * 6)
        props[pid & 0x3FFF] = val
    return props


@dataclass
class TextInfo:
    text: str = ''
    align: str = 'left'          # left / center / right
    font: tuple = None           # (family, size in pt, bold, italic)


@dataclass
class Shape:
    shape_type: int
    rect: tuple                  # (x1, y1, x2, y2) in 1/4000 units of the printable area
    text: TextInfo = None
    blip: int = 0                # index (1..n) of the picture in the BLIP store
    is_group: bool = False
    children: list = field(default_factory=list)
    line_width: int = 0          # EMU


# ============================================================================
# 3. Intermediate album model
# ============================================================================

@dataclass
class StampData:
    desc: str
    nbr: str
    value: str
    w_mm: float
    h_mm: float
    cx_mm: float                 # centre of the stamp box on the sheet (mm)
    cy_mm: float
    image: bytes = b''


@dataclass
class LabelData:
    text: str
    kind: str                    # textLabel / labelYear / labelCopyRight / labelPageNbr
    x_mm: float
    y_mm: float
    w_mm: float
    align: str
    font: tuple


@dataclass
class ImageData:
    image: bytes
    x_mm: float
    y_mm: float
    w_mm: float
    h_mm: float


@dataclass
class PageData:
    name: str
    portrait: bool
    paper: str
    has_border: bool
    frame: tuple = None          # Excel frame rectangle (mm), used to map onto the app's border
    stamps: list = field(default_factory=list)
    labels: list = field(default_factory=list)
    images: list = field(default_factory=list)


# ============================================================================
# 4. Workbook parsing
# ============================================================================

class XlsAlbumReader:
    """Decode an "Album de Timbres" .xls workbook into a list of PageData."""

    def __init__(self, file_path: str):
        import olefile
        ole = olefile.OleFileIO(file_path)
        stream = 'Workbook' if ole.exists('Workbook') else 'Book'
        self.recs = _read_records(ole.openstream(stream).read())
        ole.close()
        self.index = {p: i for i, (p, t, d) in enumerate(self.recs)}
        self.fonts = []
        self.blips = []
        self.sheets = []
        self.warnings = []
        self._read_globals()

    # ---------------------------------------------------------------- globals
    def _read_globals(self):
        dgg = b''
        collecting = False
        for pos, t, d in self.recs:
            if t == 0x0085:                                     # BOUNDSHEET
                bof, _vis, typ = struct.unpack_from('<IBB', d, 0)
                self.sheets.append((bof, typ, _xl_string(d, 6)))
            elif t == 0x0031:                                   # FONT
                height, grbit, _icv, weight = struct.unpack_from('<HHHH', d, 0)
                name = _xl_string(d, 14)
                self.fonts.append((name, height / 20.0, weight >= 700, bool(grbit & 0x02)))
            elif t == 0x00EB:                                   # MSODRAWINGGROUP
                dgg += d
                collecting = True
                continue
            elif t == 0x003C and collecting:                    # CONTINUE
                dgg += d
                continue
            elif t == 0x000A:                                   # end of the globals substream
                break
            collecting = False
        if dgg:
            self._read_blip_store(dgg)

    def _read_blip_store(self, dgg: bytes):
        for top in _art_records(dgg):
            for rec in top.children:
                if rec.rtype != 0xF001:                         # BStoreContainer
                    continue
                for fbse in rec.children:
                    self.blips.append(self._decode_fbse(fbse))

    @staticmethod
    def _decode_fbse(fbse: ArtRec) -> bytes:
        d = fbse.data
        if len(d) < 36:
            return b''
        cb_name = d[33]
        off = 36 + cb_name
        if off + 8 > len(d):
            return b''                                      # picture stored outside the stream (not supported)
        vi, btype, ln = struct.unpack_from('<HHI', d, off)
        inst = vi >> 4
        body = d[off + 8:off + 8 + ln]
        if btype in (0xF01D, 0xF01E, 0xF01F, 0xF029, 0xF02A):  # JPEG, PNG, DIB, TIFF, JPEG CMYK
            two_uids = {0xF01D: (0x46B, 0x6E3), 0xF02A: (0x6E3,), 0xF01E: (0x6E1,),
                        0xF01F: (0x7A9,), 0xF029: (0x6E5,)}.get(btype, ())
            skip = 16 + (16 if inst in two_uids else 0) + 1
            img = body[skip:]
            if btype == 0xF01F:                              # DIB -> BMP
                img = b'BM' + struct.pack('<IHHI', 14 + len(img), 0, 0, 14 + 40) + img
            return img
        if btype in (0xF01A, 0xF01B):                        # compressed EMF / WMF
            import zlib
            skip = 16 + (16 if inst in (0x3D5, 0x217) else 0) + 34
            try:
                return zlib.decompress(body[skip:])
            except zlib.error:
                return b''
        return b''

    # ---------------------------------------------------------------- sheets
    def _substream(self, bof):
        i = self.index[bof]
        out, depth = [], 0
        while i < len(self.recs):
            _p, t, d = self.recs[i]
            out.append((t, d))
            if t == 0x0809:
                depth += 1
            elif t == 0x000A:
                depth -= 1
                if depth == 0:
                    break
            i += 1
        return out

    def _font(self, ifnt):
        if ifnt >= 4:
            ifnt -= 1                                       # font index 4 does not exist in BIFF
        if 0 <= ifnt < len(self.fonts):
            return self.fonts[ifnt]
        return None

    def _sheet_drawing(self, sub):
        """Concatenate the sheet's MSODRAWING records and collect the TXO records in order."""
        dg = b''
        txos = []
        last = None
        i = 0
        while i < len(sub):
            t, d = sub[i]
            if t == 0x00EC:
                dg += d
                last = 'dg'
            elif t == 0x003C and last == 'dg':
                dg += d
            elif t == 0x01B6:                               # TXO
                grbit = struct.unpack_from('<H', d, 0)[0]
                cch = struct.unpack_from('<H', d, 10)[0]
                align = {2: 'center', 3: 'right'}.get((grbit >> 1) & 0x7, 'left')
                text, font = '', None
                j = i + 1
                if cch and j < len(sub) and sub[j][0] == 0x003C:
                    c = sub[j][1]
                    text = (c[1:1 + 2 * cch].decode('utf-16le', errors='replace') if c[0] & 1
                            else c[1:1 + cch].decode('latin-1', errors='replace'))
                    j += 1
                    if j < len(sub) and sub[j][0] == 0x003C and len(sub[j][1]) >= 8:
                        font = self._font(struct.unpack_from('<H', sub[j][1], 2)[0])
                        j += 1
                txos.append(TextInfo(text.replace('\r', '\n'), align, font))
                i = j
                last = 'txo'
                continue
            else:
                last = None
            i += 1
        return dg, txos

    def _build_shapes(self, records, txos, counter):
        """Turn the SpgrContainer into a tree of Shape objects with absolute coordinates."""
        shapes = []
        for rec in records:
            if rec.rtype == 0xF003:                         # SpgrContainer (group)
                header = rec.children[0] if rec.children else None
                grp = self._read_sp(header, txos, counter) if header else None
                spgr = None
                if header:
                    for c in header.children:
                        if c.rtype == 0xF009 and len(c.data) >= 16:
                            spgr = struct.unpack_from('<iiii', c.data, 0)
                kids = self._build_shapes(rec.children[1:], txos, counter)
                if grp is None:
                    continue
                if grp.rect is None or spgr is None or spgr == (0, 0, 0, 0):
                    shapes.extend(kids)                     # root group
                    continue
                grp.is_group = True
                grp.children = [self._to_parent(k, spgr, grp.rect) for k in kids]
                shapes.append(grp)
            elif rec.rtype == 0xF004:                       # SpContainer
                sp = self._read_sp(rec, txos, counter)
                if sp is not None and sp.rect is not None:
                    shapes.append(sp)
        return shapes

    def _to_parent(self, shape, spgr, prect):
        sx1, sy1, sx2, sy2 = spgr
        px1, py1, px2, py2 = prect
        fx = (px2 - px1) / float(sx2 - sx1 or 1)
        fy = (py2 - py1) / float(sy2 - sy1 or 1)
        x1, y1, x2, y2 = shape.rect
        shape.rect = (px1 + (x1 - sx1) * fx, py1 + (y1 - sy1) * fy,
                      px1 + (x2 - sx1) * fx, py1 + (y2 - sy1) * fy)
        # Children of a sub-group are expressed in the same space as the
        # sub-group itself: apply the same transformation to them.
        for k in shape.children:
            self._to_parent(k, spgr, prect)
        return shape

    def _read_sp(self, spcont, txos, counter):
        shape_type, rect, text, blip, line = 0, None, None, 0, 0
        for c in spcont.children:
            if c.rtype == 0xF00A:                           # Sp
                shape_type = c.inst
            elif c.rtype == 0xF00B:                         # Opt
                props = _opt_props(c)
                blip = props.get(0x104, 0)
                line = props.get(0x1CB, 0)
            elif c.rtype == 0xF010 and len(c.data) >= 18:   # ClientAnchor (chart sheet)
                rect = struct.unpack_from('<iiii', c.data, 2)
            elif c.rtype == 0xF00F and len(c.data) >= 16:   # ChildAnchor
                rect = struct.unpack_from('<iiii', c.data, 0)
            elif c.rtype == 0xF00D:                         # ClientTextbox
                if counter[0] < len(txos):
                    text = txos[counter[0]]
                counter[0] += 1
        return Shape(shape_type, rect, text, blip, line_width=line)

    # ---------------------------------------------------------------- pages
    def read_pages(self):
        pages = []
        for bof, typ, name in self.sheets:
            sub = self._substream(bof)
            page = self._read_page(name, sub)
            if page is not None:
                pages.append(page)

        # Natural order PAGE-01, PAGE-02, ..., PAGE-12, PAGE-12A, ... (tabs are often reversed)
        def key(p):
            return [int(t) if t.isdigit() else t.lower() for t in re.split(r'(\d+)', p.name)]
        if pages and all(re.match(r'(?i)^page', p.name) for p in pages):
            pages.sort(key=key)
        return pages

    def _read_page(self, name, sub):
        margins = {0x26: 19.0, 0x27: 10.0, 0x28: 10.0, 0x29: 10.0}
        portrait, paper = True, 'A4'
        chart_w = chart_h = None
        for t, d in sub:
            if t in margins and len(d) >= 8:
                margins[t] = struct.unpack('<d', d[:8])[0] * 25.4
            elif t == 0x00A1 and len(d) >= 12:              # SETUP
                paper_id, _s, _st, _fw, _fh, opt = struct.unpack_from('<HHHHHH', d, 0)
                if not opt & 0x04:                          # fNoPls = 0 -> values are valid
                    portrait = bool(opt & 0x02)
                    paper = 'Letter' if paper_id == 1 else 'A4'
            elif t == 0x1002 and len(d) >= 16 and chart_w is None:   # CHART (size in points)
                _x, _y, w, h = struct.unpack_from('<iiii', d, 0)
                chart_w, chart_h = w / 65536.0 * 25.4 / 72.0, h / 65536.0 * 25.4 / 72.0

        dg, txos = self._sheet_drawing(sub)
        if not dg:
            return None
        counter = [0]
        shapes = []
        for top in _art_records(dg):
            if top.rtype == 0xF002:                         # DgContainer
                for c in top.children:
                    if c.rtype == 0xF003:
                        shapes += self._build_shapes([c], txos, counter)
        if not shapes:
            return None

        paper_w, paper_h = (215.9, 279.4) if paper == 'Letter' else (210.0, 297.0)
        if not portrait:
            paper_w, paper_h = paper_h, paper_w
        left, right, top, bottom = margins[0x26], margins[0x27], margins[0x28], margins[0x29]
        area_w = chart_w or (paper_w - left - right)
        area_h = chart_h or (paper_h - top - bottom)

        def to_mm(rect):
            x1, y1, x2, y2 = rect
            return (left + x1 / SPRC * area_w, top + y1 / SPRC * area_h,
                    left + x2 / SPRC * area_w, top + y2 / SPRC * area_h)

        page = PageData(name, portrait, paper, has_border=False)
        self._page_name = name
        for sh in shapes:
            x1, y1, x2, y2 = sh.rect
            if x1 >= SPRC or y1 >= SPRC or x2 <= 0 or y2 <= 0:
                continue                                    # shape parked outside the page
            r = to_mm(sh.rect)
            if sh.is_group:
                st = self._group_to_stamp(sh, to_mm)
                if st is not None:
                    page.stamps.append(st)
                else:
                    self._loose_shapes(sh.children, to_mm, page)
                continue
            if self._is_page_frame(sh):
                page.has_border = True
                page.frame = r
                continue
            self._loose_shapes([sh], to_mm, page)
        return page

    @staticmethod
    def _is_page_frame(sh):
        x1, y1, x2, y2 = sh.rect
        no_text = sh.text is None or not sh.text.text.strip()
        return no_text and sh.blip == 0 and (x2 - x1) > 0.9 * SPRC and (y2 - y1) > 0.9 * SPRC

    def _loose_shapes(self, shapes, to_mm, page):
        for sh in shapes:
            r = to_mm(sh.rect)
            if sh.blip:
                img = self.blips[sh.blip - 1] if sh.blip - 1 < len(self.blips) else b''
                if img:
                    page.images.append(ImageData(img, r[0], r[1], r[2] - r[0], r[3] - r[1]))
            elif sh.text is not None and sh.text.text.strip():
                text = sh.text.text.strip('\n')
                page.labels.append(LabelData(text, self._label_kind(text), r[0], r[1],
                                             r[2] - r[0], sh.text.align, sh.text.font))

    @staticmethod
    def _label_kind(text):
        t = text.strip()
        if re.match(r'(?i)^(copyright|©)', t):
            return 'labelCopyRight'
        if re.fullmatch(r'\d{4}(\s*[-/]\s*\d{4})?', t):
            return 'labelYear'
        if re.search(r'\b\d{4}-\d+[A-Za-z]?$', t) or re.match(r'(?i)^page\s*\d+', t):
            return 'labelPageNbr'
        return 'textLabel'

    _FORMAT_RE = re.compile(r'(?i)format\s*:?\s*(\d+(?:[.,]\d+)?)\s*[xX×*]\s*(\d+(?:[.,]\d+)?)')

    def _group_to_stamp(self, grp, to_mm):
        leaves = self._flatten(grp)
        texts = [s for s in leaves if s.text is not None and s.text.text.strip()]
        pics = [s for s in leaves if s.blip]

        # The box: "Format WxH" text box, otherwise the largest shape
        box = next((s for s in texts if self._FORMAT_RE.search(s.text.text)), None)
        if box is None:
            candidates = [s for s in leaves if s.shape_type in (1, 202) and not s.blip]
            if not candidates:
                return None
            box = max(candidates, key=lambda s: (s.rect[2] - s.rect[0]) * (s.rect[3] - s.rect[1]))
        bx1, by1, bx2, by2 = to_mm(box.rect)

        m = self._FORMAT_RE.search(box.text.text) if box.text else None
        geo_w, geo_h = bx2 - bx1, by2 - by1
        if m:
            w_mm = float(m.group(1).replace(',', '.'))
            h_mm = float(m.group(2).replace(',', '.'))
            # Outdated "Format" text: keep the measured size
            if abs(w_mm - geo_w) > max(4.0, 0.06 * geo_w) or abs(h_mm - geo_h) > max(4.0, 0.06 * geo_h):
                self.warnings.append(
                    f"{self._page_name} : « {box.text.text.strip()} » ne correspond pas à la case "
                    f"dessinée ({geo_w:.0f}x{geo_h:.0f} mm) — taille mesurée utilisée.")
                w_mm, h_mm = round(geo_w - 1.5), round(geo_h - 1.5)
        else:
            w_mm, h_mm = round(geo_w - 1.5), round(geo_h - 1.5)

        above, below = [], []
        for s in texts:
            if s is box:
                continue
            x1, y1, x2, y2 = to_mm(s.rect)
            (above if (y1 + y2) / 2 < (by1 + by2) / 2 else below).append((y1, s.text.text.strip('\n')))
        above.sort()
        below.sort()

        desc = '\n'.join(t for _, t in above)
        nbr_idx = next((i for i, (_, t) in enumerate(below) if re.match(r'(?i)^\s*n[°o]', t)), 0)
        nbr = below[nbr_idx][1] if below else ''
        value = '\n'.join(t for i, (_, t) in enumerate(below) if i != nbr_idx)

        image = b''
        if pics:
            pic = max(pics, key=lambda s: (s.rect[2] - s.rect[0]) * (s.rect[3] - s.rect[1]))
            if pic.blip - 1 < len(self.blips):
                image = self.blips[pic.blip - 1]
            if not image:
                self.warnings.append("Image non lisible dans un groupe")

        return StampData(desc, nbr, value, w_mm, h_mm, (bx1 + bx2) / 2, (by1 + by2) / 2, image)

    def _flatten(self, grp):
        out = []
        for c in grp.children:
            out.extend(self._flatten(c) if c.is_group else [c])
        return out


# ============================================================================
# 5. Building the pages in the application
# ============================================================================

class XlsAlbumImporter:
    """Create Stamp Album pages from an "Album de Timbres" .xls workbook."""

    def __init__(self, window, file_path: str):
        self.win = window
        self.file_path = file_path

    def run(self) -> dict:
        from PyQt6.QtCore import Qt, QRectF
        from PyQt6.QtGui import QFont, QPixmap
        from PyQt6.QtWidgets import QGraphicsTextItem
        from Stamp import Stamp

        reader = XlsAlbumReader(self.file_path)
        pages = reader.read_pages()
        n_stamps = 0
        no_image = 0
        aligns = {'center': Qt.AlignmentFlag.AlignCenter, 'right': Qt.AlignmentFlag.AlignRight,
                  'left': Qt.AlignmentFlag.AlignLeft}

        for pd in pages:
            scene = self.win.newPage('portrait' if pd.portrait else 'landscape',
                                     pd.has_border, paper_format=pd.paper)
            if scene is None:
                scene = self.win.getCurrentPageScene()

            # Alignment: the Excel frame is mapped onto the app's border
            border = next((it for it in scene.items() if it.data(0) == 'borderGroup'), None)
            if border is not None and pd.frame is not None:
                b = border.sceneBoundingRect()
                fx1, fy1, fx2, fy2 = pd.frame
                sx = b.width() / mm(fx2 - fx1)
                sy = b.height() / mm(fy2 - fy1)

                def X(v, b=b, fx1=fx1, sx=sx): return b.left() + (mm(v) - mm(fx1)) * sx
                def Y(v, b=b, fy1=fy1, sy=sy): return b.top() + (mm(v) - mm(fy1)) * sy
            else:
                sx = 1.0

                def X(v): return mm(v)
                def Y(v): return mm(v)

            # Free-floating pictures (rare)
            for im in pd.images:
                pix = QPixmap()
                if pix.loadFromData(im.image):
                    from ResizablePixmapItem import ResizablePixmapItem
                    item = ResizablePixmapItem(pix)
                    item.setScale(min(mm(im.w_mm) / pix.width(), mm(im.h_mm) / pix.height()))
                    item.setPos(X(im.x_mm), Y(im.y_mm))
                    scene.addItemWithUndo(item, "Add Image")

            # Page texts: positions computed first (they bound the stamps)
            placed_labels = []
            for lb in pd.labels:
                font = QFont()
                if lb.font:
                    family, size, bold, italic = lb.font
                    font = QFont(family)
                    font.setPointSize(max(1, int(round(size))))
                    font.setBold(bold)
                    font.setItalic(italic)
                probe = QGraphicsTextItem(lb.text)
                probe.setFont(font)
                tw, th = probe.boundingRect().width(), probe.boundingRect().height()
                x, w = X(lb.x_mm), mm(lb.w_mm) * sx
                if lb.align == 'center':
                    x += (w - tw) / 2.0
                elif lb.align == 'right':
                    x += w - tw
                y = Y(lb.y_mm)
                # Keep the text inside the border (3 mm margin)
                if border is not None:
                    inner = border.sceneBoundingRect().adjusted(mm(3), mm(3), -mm(3), -mm(3))
                    x = max(inner.left(), min(x, inner.right() - tw))
                    y = max(inner.top(), min(y, inner.bottom() - th))
                placed_labels.append((lb, font, x, y, QRectF(x, y, tw, th)))

            # Stamps
            groups = []
            for st in pd.stamps:
                pix = QPixmap()
                if not st.image or not pix.loadFromData(st.image):
                    pix = QPixmap()
                    no_image += 1
                before = {it for it in scene.items() if it.parentItem() is None}
                Stamp().createStampPix(scene, st.nbr, st.value, st.desc,
                                       st.w_mm, st.h_mm, 0.0, 0.0, pix)
                grp = next((it for it in scene.items() if it.parentItem() is None
                            and it not in before and it.data(0) == 'stampGroup'), None)
                if grp is None:
                    continue
                box = next((c for c in grp.childItems() if c.data(0) == 'stampBox'), None)
                if box is not None:
                    c = box.sceneBoundingRect().center()
                    grp.moveBy(X(st.cx_mm) - c.x(), Y(st.cy_mm) - c.y())
                groups.append(grp)
                n_stamps += 1

            if groups and not self._resolve_overlaps(scene, groups, border, placed_labels):
                reader.warnings.append(f"{pd.name} : page trop chargée, des textes se chevauchent "
                                       f"(à ajuster à la main).")

            for lb, font, x, y, _r in placed_labels:
                scene.addTextLabel(lb.text, x, y, font, aligns.get(lb.align), lb.kind)

        return {'pages': len(pages), 'stamps': n_stamps, 'no_image': no_image,
                'names': [p.name for p in pages], 'warnings': reader.warnings}

    @staticmethod
    def _visible_rect(grp):
        from PyQt6.QtWidgets import QGraphicsTextItem
        rect = None
        for c in grp.childItems():
            if isinstance(c, QGraphicsTextItem) and not c.toPlainText().strip():
                continue
            r = c.sceneBoundingRect()
            rect = r if rect is None else rect.united(r)
        return rect if rect is not None else grp.sceneBoundingRect()

    def _resolve_overlaps(self, scene, groups, border, labels, gap=mm(1.5)):
        """Stamp texts are spaced further apart in Stamp Album than in Excel:
        push overlapping stamps apart, then move the whole block up into the free
        space (below the year, above the footer). Return False if the page is
        still too crowded."""
        page = border.sceneBoundingRect() if border is not None else scene.sceneRect()
        mid = page.center().y()
        top_limit = page.top() + mm(3)
        bottom_limit = page.bottom() - mm(3)
        for _lb, _f, _x, _y, r in labels:
            if r.center().y() < mid:
                top_limit = max(top_limit, r.bottom() + gap)
            else:
                bottom_limit = min(bottom_limit, r.top() - gap)

        groups = sorted(groups, key=lambda g: self._visible_rect(g).top())
        original = [(g, g.pos()) for g in groups]
        # 1. push apart stamps that overlap vertically
        for i, g in enumerate(groups):
            r = self._visible_rect(g)
            for prev in groups[:i]:
                pr = self._visible_rect(prev)
                h_overlap = r.left() < pr.right() and pr.left() < r.right()
                if h_overlap and r.top() < pr.bottom() + gap:
                    g.moveBy(0, pr.bottom() + gap - r.top())
                    r = self._visible_rect(g)
        # 2. move up if the bottom overflows
        bottom = max(self._visible_rect(g).bottom() for g in groups)
        top = min(self._visible_rect(g).top() for g in groups)
        overflow = bottom - bottom_limit
        if overflow > 0:
            shift = min(overflow, max(0.0, top - top_limit))
            for g in groups:
                g.moveBy(0, -shift)
            overflow -= shift
        if overflow > 0.5:
            # Cannot fit everything: keep the original Excel layout
            for g, pos in original:
                g.setPos(pos)
            return False
        return True
