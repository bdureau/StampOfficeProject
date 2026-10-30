"""
AlbumEasy Importer
------------------
Converts an AlbumEasy description file (.txt) into Stamp Album pages.

Architecture:
  1. Lecture du fichier (UTF-8, repli cp1252), suppression des commentaires
     hors guillemets, fusion des lignes continuées par « \\ ».
  2. Analyse de chaque commande « NOM (arguments) » en jetons (chaînes / mots / nombres).
  3. Mise en page « à la AlbumEasy » : curseur vertical, rangées de timbres centrées,
     colonnes, paragraphes avec retour à la ligne, titres et numéros de page.

Les timbres sont créés avec Stamp.createStampPix() (dimensions en mm) et les textes
avec Page.addTextLabel() / Page.addRichText(), pour que tout soit sauvegardé et
rechargé correctement dans un fichier .sta.

Author: Boris du Reau
"""
import html
import re
from dataclasses import dataclass, field
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QFontMetricsF, QImage, QPixmap
from PyQt6.QtWidgets import QGraphicsScene, QGraphicsTextItem

from Stamp import Stamp

PX_PER_MM = 96.0 / 25.4


def mm(value) -> float:
    """Millimètres -> pixels de scène (96 DPI)."""
    return float(value) * PX_PER_MM


# ----------------------------------------------------------------------------
# Analyse syntaxique
# ----------------------------------------------------------------------------

_CMD_RE = re.compile(r'^([A-Z][A-Z0-9_]*)\s*(?:\((.*)\))?\s*;?\s*$', re.S)
_TOKEN_RE = re.compile(r'"((?:[^"\\]|\\.)*)"|([^\s"]+)')
_NUM_RE = re.compile(r'^[-+]?\d+(?:\.\d*)?$|^[-+]?\.\d+$')


@dataclass
class Arg:
    value: str
    quoted: bool

    @property
    def is_number(self) -> bool:
        return not self.quoted and bool(_NUM_RE.match(self.value))

    @property
    def num(self) -> float:
        return float(self.value)

    @property
    def is_word(self) -> bool:
        return not self.quoted and not self.is_number


def _unescape(s: str) -> str:
    return s.replace('\\n', '\n').replace('\\t', '    ').replace('\\"', '"').replace('\\\\', '\\')


def strip_comment(line: str) -> str:
    """Supprime un commentaire '#' situé hors d'une chaîne entre guillemets."""
    in_quotes = False
    prev = ''
    for i, ch in enumerate(line):
        if ch == '"' and prev != '\\':
            in_quotes = not in_quotes
        elif ch == '#' and not in_quotes:
            return line[:i]
        prev = ch
    return line


def iter_logical_lines(raw_lines):
    """Supprime les commentaires et fusionne les lignes terminées par '\\'.
    "abc"\\  +  "def"  devient  "abcdef" (concaténation de chaînes AlbumEasy)."""
    buf = None
    for raw in raw_lines:
        line = strip_comment(raw.rstrip('\r\n')).strip()
        if buf is not None:
            if buf.endswith('"') and line.startswith('"'):
                line = buf[:-1] + line[1:]
            else:
                line = (buf + ' ' + line).strip()
            buf = None
        if line.endswith('\\') and not line.endswith('\\\\'):
            buf = line[:-1].rstrip()
            continue
        yield line
    if buf:
        yield buf


def parse_args(arg_str: str):
    args = []
    for m in _TOKEN_RE.finditer(arg_str or ''):
        if m.group(1) is not None:
            args.append(Arg(_unescape(m.group(1)), True))
        else:
            args.append(Arg(m.group(2), False))
    return args


# ----------------------------------------------------------------------------
# Modèle intermédiaire
# ----------------------------------------------------------------------------

@dataclass
class PendingStamp:
    w: float                      # mm
    h: float                      # mm
    nbr: str = ''
    value: str = ''
    heading: str = ''
    pixmap: QPixmap = field(default_factory=QPixmap)
    blank: bool = False


@dataclass
class PageInfo:
    scene: object
    is_info: bool
    x0: float
    x1: float
    bottom: float


# Commandes sans effet visuel pertinent dans Stamp Album (ignorées silencieusement)
_SILENT = {
    'COLOUR_PAGE_QUADRILLE', 'TEXT_CHAR_SPACING', 'TEXT_LINE_LEADING',
    'ALBUM_STAMP_IMG_SETTING', 'ALBUM_STAMP_IMG_NEW_SETTING', 'ALBUM_STAMP_NEW_IMG_SETTING',
    'ALBUM_PAGES_FOOTER_PAD', 'ALBUM_PAGES_HEADER_PAD', 'ALBUM_PAGES_MARGIN_TXT_PAD',
    'COLOUR_STAMP_BACKGROUND', 'COLOUR_STAMP_BOX', 'COLOUR_STAMP_TEXT', 'COLOUR_PAGE_BORDER',
    'COLOUR_PAGE_TITLE', 'ALBUM_TITLE',
}


class AlbumEasyImporter:
    """Importe un fichier AlbumEasy dans la fenêtre principale (MainWindow.Window)."""

    def __init__(self, window, file_path: str):
        self.win = window
        self.path = Path(file_path)
        self.base_dir = self.path.parent

        # Réglages globaux de l'album
        self.page_w_mm, self.page_h_mm = 210.0, 297.0
        self.margins = [15.0, 15.0, 15.0, 15.0]   # gauche, droite, haut, bas
        self.has_border = False
        self.row_gap = 4.0                         # mm entre deux rangées
        self.text_gap = 1.0                        # mm après un texte
        self.title = None                          # (QFont, texte)
        self.fonts = {}                            # alias -> famille
        self.text_color = QColor('black')
        self.row_align = 'bottom'
        self.box_adjust = 0.0
        self.img_grey = False
        self.img_hide = False
        self.footer_number = None

        # État de la page courante
        self.pages = []
        self.scene = None
        self.x0 = self.x1 = self.top = self.bottom = self.y = 0.0
        self.page_x0 = self.page_x1 = 0.0
        self.columns = None
        self.row = []
        self.row_mode = 'FS'
        self.row_spacing = 4.0
        self.paragraph = None
        self.content_top = 0.0
        self._tmp_scene = QGraphicsScene()     # scène de mesure des timbres

        # Rapport
        self.stamp_count = 0
        self.unsupported = {}
        self.missing_images = []
        self.notes = set()

        self.handlers = {
            'ALBUM_PAGES_SIZE': self._album_pages_size,
            'ALBUM_PAGES_MARGINS': self._album_pages_margins,
            'ALBUM_PAGES_BORDER': self._album_pages_border,
            'ALBUM_PAGES_DECORATIVE_BORDER': self._album_pages_border,
            'ALBUM_PAGES_SPACING': self._album_pages_spacing,
            'ALBUM_PAGES_TITLE': self._album_pages_title,
            'ALBUM_DEFINE_FONT': self._album_define_font,
            'ALBUM_AUTHOR': self._album_author,
            'ALBUM_PAGES_FOOTER_NUMBER': self._footer_number,
            'PAGE_START': lambda a: self._start_page(info=False),
            'PAGE_START_INFO': self._page_start_info,
            'PAGE_TEXT': lambda a: self._page_text(a, 'left'),
            'PAGE_TEXT_CENTRE': lambda a: self._page_text(a, 'center'),
            'PAGE_TEXT_CENTER': lambda a: self._page_text(a, 'center'),
            'PAGE_TEXT_PARAGRAPH_START': self._paragraph_start,
            'PAGE_VSPACE': self._page_vspace,
            'PAGE_COLUMN_START': self._column_start,
            'PAGE_COLUMN_NEXT': self._column_next,
            'PAGE_COLUMN_STOP': self._column_stop,
            'PAGE_ADD_BOX': self._page_add_box,
            'PAGE_BACKGROUND_IMG': self._page_background_img,
            'COLOUR_PAGE_TEXT': self._colour_page_text,
            'ROW_ALIGN_TOP': lambda a: setattr(self, 'row_align', 'top'),
            'ROW_ALIGN_MIDDLE': lambda a: setattr(self, 'row_align', 'middle'),
            'ROW_ALIGN_BOTTOM': lambda a: setattr(self, 'row_align', 'bottom'),
            'ROW_START': lambda a: self._row_start(a, 'FS'),
            'ROW_START_FS': lambda a: self._row_start(a, 'FS'),
            'ROW_START_JS': lambda a: self._row_start(a, 'JS'),
            'STAMP_ADD': self._stamp_add,
            'STAMP_ADD_IMG': self._stamp_add_img,
            'STAMP_ADD_BLANK': self._stamp_add_blank,
            'STAMP_HEADING': self._stamp_heading,
            'STAMP_HEADING_VA': self._stamp_heading,
            'STAMP_BOXES_SIZE_ADJUST': self._boxes_size_adjust,
            'ALBUM_STAMP_IMG_GREYSCALE_ON': lambda a: setattr(self, 'img_grey', True),
            'ALBUM_STAMP_IMG_GREYSCALE_OFF': lambda a: setattr(self, 'img_grey', False),
            'ALBUM_STAMP_IMG_HIDE': lambda a: setattr(self, 'img_hide', True),
            'ALBUM_STAMP_IMG_SHOW': lambda a: setattr(self, 'img_hide', False),
        }

    # ------------------------------------------------------------------ run
    def run(self) -> dict:
        for line in iter_logical_lines(self._read_lines()):
            if self.paragraph is not None:
                if line.upper().startswith('PAGE_TEXT_PARAGRAPH_END'):
                    self._paragraph_end()
                elif line:
                    self.paragraph['lines'].append(line)
                continue
            if not line:
                continue
            m = _CMD_RE.match(line)
            if not m:
                continue
            cmd = m.group(1)
            args = parse_args(m.group(2))
            handler = self.handlers.get(cmd)
            if handler is None:
                if cmd not in _SILENT:
                    self.unsupported[cmd] = self.unsupported.get(cmd, 0) + 1
                continue
            # Toute commande de page avant le premier PAGE_START crée une page implicite
            if self.scene is None and (cmd.startswith('PAGE_') or cmd.startswith('STAMP_')
                                       or cmd.startswith('ROW_START')) \
                    and cmd not in ('PAGE_START', 'PAGE_START_INFO'):
                self._start_page(info=False)
            handler(args)

        if self.paragraph is not None:
            self._paragraph_end()
        self._flush_row()
        self._add_footers()

        return {
            'pages': len(self.pages),
            'stamps': self.stamp_count,
            'unsupported': self.unsupported,
            'missing_images': self.missing_images,
            'notes': sorted(self.notes),
        }

    def _read_lines(self):
        data = self.path.read_bytes()
        for enc in ('utf-8-sig', 'cp1252', 'latin-1'):
            try:
                return data.decode(enc).splitlines()
            except UnicodeDecodeError:
                continue
        return data.decode('utf-8', errors='replace').splitlines()

    # --------------------------------------------------------- utilitaires
    @staticmethod
    def _nums(args):
        return [a.num for a in args if a.is_number]

    @staticmethod
    def _strings(args):
        return [a.value for a in args if a.quoted]

    def _font(self, code: str, size: float) -> QFont:
        """HN/HB/HI/HBI = Helvetica, TN/TB... = Times, CN... = Courier, ou police définie."""
        code = (code or 'HN').upper()
        if code in self.fonts:
            family = self.fonts[code]
            font = QFont(family)
            low = family.lower()
            font.setBold('bold' in low)
            font.setItalic('italic' in low or 'oblique' in low)
        else:
            family = {'H': 'Arial', 'T': 'Times New Roman', 'C': 'Courier New'}.get(code[:1], 'Arial')
            style = code[1:]
            font = QFont(family)
            font.setBold('B' in style)
            font.setItalic('I' in style)
        font.setPointSize(max(1, int(round(size))))
        return font

    def _font_from_args(self, args, default_size=10.0) -> QFont:
        code = args[0].value if args and args[0].is_word else 'HN'
        nums = self._nums(args)
        return self._font(code, nums[0] if nums else default_size)

    @staticmethod
    def _wrap(text: str, font: QFont, width_px: float) -> str:
        """Retour à la ligne manuel : le texte reste un label simple (sauvegarde fidèle)."""
        fm = QFontMetricsF(font)
        limit = max(40.0, width_px - 12.0)
        out = []
        for para in text.split('\n'):
            words = para.split(' ')
            line = ''
            for w in words:
                cand = w if not line else line + ' ' + w
                if not line or fm.horizontalAdvance(cand) <= limit:
                    line = cand
                else:
                    out.append(line)
                    line = w
            out.append(line)
        return '\n'.join(out)

    # ---------------------------------------------------------- pages
    def _start_page(self, info=False, no_border=False, continuation=False):
        self._flush_row()
        if continuation and self.pages:
            no_border = not any(it.data(0) == 'borderGroup' for it in self.scene.items())
        portrait_w, portrait_h = sorted((self.page_w_mm, self.page_h_mm))
        paper = 'Letter' if abs(portrait_w - 215.9) < 3 else 'A4'
        orient = 'landscape' if self.page_w_mm > self.page_h_mm else 'portrait'
        border = self.has_border and not no_border

        scene = self.win.newPage(orient, border, paper_format=paper)
        if scene is None:
            scene = self.win.getCurrentPageScene()
        self.scene = scene

        rect = scene.sceneRect()
        border_item = next((it for it in scene.items() if it.data(0) == 'borderGroup'), None)
        if border_item is not None:
            b = border_item.sceneBoundingRect()
            pad = mm(4)
            self.x0, self.x1 = b.left() + pad, b.right() - pad
            self.top, self.bottom = b.top() + pad, b.bottom() - pad
        else:
            left, right, top, bottom = self.margins
            self.x0, self.x1 = mm(left), rect.width() - mm(right)
            self.top, self.bottom = mm(top), rect.height() - mm(bottom)
        self.page_x0, self.page_x1 = self.x0, self.x1
        self.y = self.top
        self.columns = None
        self.pages.append(PageInfo(scene, info, self.x0, self.x1, self.bottom))

        if not info and self.title:
            font, text = self.title
            self._add_text(text, font, 'center', gap_mm=3.0)
        self.content_top = self.y

    def _page_start_info(self, args):
        no_border = any(a.value.upper() == 'NO_BORDER' for a in args if not a.quoted)
        self._start_page(info=True, no_border=no_border)

    # ---------------------------------------------------------- textes
    def _add_text(self, text, font, align='left', gap_mm=None, wrap=True):
        self._flush_row()
        if text is None:
            return
        avail = self.x1 - self.x0
        if wrap:
            text = self._wrap(text, font, avail)

        probe = QGraphicsTextItem(text)
        probe.setFont(font)
        w = probe.boundingRect().width()
        h = probe.boundingRect().height()

        if align == 'center':
            x = self.x0 + max(0.0, (avail - w) / 2.0)
        elif align == 'right':
            x = max(self.x0, self.x1 - w)
        else:
            x = self.x0

        qt_align = {'center': Qt.AlignmentFlag.AlignCenter,
                    'right': Qt.AlignmentFlag.AlignRight}.get(align, Qt.AlignmentFlag.AlignLeft)

        if self.text_color.name() == '#000000':
            self.scene.addTextLabel(text, x, self.y, font, qt_align)
        else:
            # Texte en couleur : bloc rich text (le HTML est sauvegardé dans le .sta)
            css_align = {'center': 'center', 'right': 'right'}.get(align, 'left')
            body = html.escape(text).replace('\n', '<br/>')
            markup = (f"<div align='{css_align}' style=\"font-family:'{font.family()}'; "
                      f"font-size:{font.pointSize()}pt; "
                      f"font-weight:{'bold' if font.bold() else 'normal'}; "
                      f"font-style:{'italic' if font.italic() else 'normal'}; "
                      f"color:{self.text_color.name()};\">{body}</div>")
            item = self.scene.addRichText(markup, x, self.y)
            h = item.boundingRect().height()

        self.y += h + mm(self.text_gap if gap_mm is None else gap_mm)

    def _page_text(self, args, align):
        strings = self._strings(args)
        if not strings:
            return
        font = self._font_from_args(args)
        # Un nombre placé APRÈS la chaîne = espace (mm) après le texte
        idx = next(i for i, a in enumerate(args) if a.quoted)
        after = [a.num for a in args[idx + 1:] if a.is_number]
        self._add_text(strings[0], font, align, gap_mm=after[0] if after else None)

    def _paragraph_start(self, args):
        self._flush_row()
        words = [a.value.upper() for a in args[1:] if a.is_word]
        align = 'left'
        if any(w.startswith('CENT') for w in words):
            align = 'center'
        elif 'RIGHT' in words:
            align = 'right'
        nums = self._nums(args)[1:]          # le premier nombre est la taille de police
        pad_l = pad_r = 0.0
        gap = None
        if len(nums) == 1:
            pad_l = pad_r = nums[0]
        elif len(nums) == 2:
            pad_l = pad_r = nums[0]
            gap = nums[1]
        elif len(nums) >= 3:
            pad_l, gap, pad_r = nums[0], nums[1], nums[2]
        self.paragraph = {'font': self._font_from_args(args), 'align': align,
                          'pad_l': pad_l, 'pad_r': pad_r, 'gap': gap, 'lines': []}

    def _paragraph_end(self):
        p, self.paragraph = self.paragraph, None
        if not p['lines']:
            return
        text = ' '.join(l.strip() for l in p['lines'])
        text = _unescape(text)
        text = '\n'.join(re.sub(r'\s+', ' ', part).strip() for part in text.split('\n'))
        text = text.rstrip('\n')
        if p['align'] == 'left':
            self.notes.add("Paragraphes JUSTIFIED importés alignés à gauche.")
        saved = (self.x0, self.x1)
        self.x0 = min(saved[1] - mm(20), saved[0] + mm(p['pad_l']))
        self.x1 = max(self.x0 + mm(20), saved[1] - mm(p['pad_r']))
        self._add_text(text, p['font'], p['align'], gap_mm=p['gap'] if p['gap'] is not None else 2.0)
        self.x0, self.x1 = saved

    def _page_vspace(self, args):
        self._flush_row()
        nums = self._nums(args)
        if nums:
            self.y += mm(nums[0])

    def _colour_page_text(self, args):
        name = args[0].value if args else 'black'
        color = QColor(name.lower())
        self.text_color = color if color.isValid() else QColor('black')

    # ---------------------------------------------------------- colonnes
    def _column_start(self, args):
        self._flush_row()
        nums = self._nums(args) + [0.0] * 5
        pct, p1l, p1r, p2l, p2r = nums[:5]
        pct = pct if 5 <= pct <= 95 else 50.0
        full = (self.x0, self.x1)
        split = full[0] + (full[1] - full[0]) * pct / 100.0
        self.columns = {'full': full, 'y_start': self.y, 'max_y': self.y,
                        'col2': (split + mm(p2l), full[1] - mm(p2r))}
        self.x0, self.x1 = full[0] + mm(p1l), split - mm(p1r)

    def _column_next(self, args):
        if not self.columns:
            return
        self._flush_row()
        self.columns['max_y'] = max(self.columns['max_y'], self.y)
        self.y = self.columns['y_start']
        self.x0, self.x1 = self.columns['col2']

    def _column_stop(self, args):
        if not self.columns:
            return
        self._flush_row()
        self.y = max(self.columns['max_y'], self.y)
        self.x0, self.x1 = self.columns['full']
        self.columns = None

    # ---------------------------------------------------------- timbres
    def _row_start(self, args, mode):
        self._flush_row()
        self.row_mode = mode
        nums = self._nums(args)
        # ROW_START_FS (police taille épaisseur_cadre espacement)
        self.row_spacing = nums[2] if len(nums) >= 3 else 4.0

    def _box_size(self, nums):
        return nums[0] + self.box_adjust, nums[1] + self.box_adjust

    @staticmethod
    def _join(*parts):
        return '\n'.join(p.strip() for p in parts if p and p.strip())

    def _stamp_add(self, args):
        """STAMP_ADD (l h "texte1" "texte2" "texte3" "texte4" ...)
        texte1/2 = dans la case (valeur faciale) -> champ Valeur
        texte3/4 = sous la case (n° de catalogue) -> champ Numéro"""
        nums = self._nums(args)
        if len(nums) < 2:
            return
        s = self._strings(args) + [''] * 6
        w, h = self._box_size(nums)
        self.row.append(PendingStamp(w, h, nbr=self._join(s[2], s[3], *s[4:]),
                                     value=self._join(s[0], s[1])))

    def _stamp_add_img(self, args):
        """STAMP_ADD_IMG (l h "image" "texte1" "texte2" "texte3" ["texte case" dy dy ...] [NO_FRAME])
        texte1/2 (sous la case) -> Numéro, texte3 -> Valeur, texte dans la case -> ajouté à Valeur."""
        nums = self._nums(args)
        s = self._strings(args)
        if len(nums) < 2 or not s:
            return
        w, h = self._box_size(nums)
        s = s + [''] * 5
        if any(a.value.upper() == 'NO_FRAME' for a in args if not a.quoted):
            self.notes.add("NO_FRAME ignoré : les cases sont toujours encadrées.")
        self.row.append(PendingStamp(w, h, nbr=self._join(s[1], s[2]),
                                     value=self._join(s[3], s[4]),
                                     pixmap=self._load_pixmap(s[0])))

    def _stamp_add_blank(self, args):
        nums = self._nums(args)
        if nums:
            self.row.append(PendingStamp(nums[0], nums[1] if len(nums) > 1 else 0.0, blank=True))

    def _stamp_heading(self, args):
        strings = self._strings(args)
        target = next((s for s in reversed(self.row) if not s.blank), None)
        if target is not None and strings:
            target.heading = strings[0]
            if len([a for a in args if a.is_number]) > 1:
                self.notes.add("Décalage horizontal des STAMP_HEADING ignoré.")

    def _boxes_size_adjust(self, args):
        nums = self._nums(args)
        self.box_adjust = nums[0] if nums else 0.0

    def _load_pixmap(self, rel_path: str) -> QPixmap:
        if self.img_hide or not rel_path:
            return QPixmap()
        p = Path(rel_path.replace('\\', '/'))
        if not p.is_absolute():
            p = self.base_dir / p
        if not p.is_file() and p.parent.is_dir():
            # Recherche insensible à la casse (Linux)
            low = p.name.lower()
            p = next((f for f in p.parent.iterdir() if f.name.lower() == low), p)
        if not p.is_file():
            if rel_path not in self.missing_images:
                self.missing_images.append(rel_path)
            return QPixmap()
        img = QImage(str(p))
        if img.isNull():
            return QPixmap()
        if self.img_grey:
            img = img.convertToFormat(QImage.Format.Format_Grayscale8)
        return QPixmap.fromImage(img)

    def _create_stamp(self, s: PendingStamp):
        """Construit le timbre via Stamp.createStampPix dans une scène temporaire
        (pour pouvoir le mesurer avant de choisir sa page) et retourne son groupe."""
        tmp = self._tmp_scene
        before = set(tmp.items())
        Stamp().createStampPix(tmp, s.nbr, s.value, s.heading, s.w, s.h, 0.0, 0.0, s.pixmap)
        grp = next((it for it in tmp.items()
                    if it.parentItem() is None and it not in before
                    and it.data(0) == 'stampGroup'), None)
        return grp

    def _commit(self, grp):
        """Transfère un groupe de la scène temporaire vers la page courante (avec Undo)."""
        self._tmp_scene.removeItem(grp)
        self.scene.addItemWithUndo(grp, "Add Stamp")
        self.stamp_count += 1

    @staticmethod
    def _box_of(group):
        return next((c for c in group.childItems() if c.data(0) == 'stampBox'), None)

    @staticmethod
    def _visible_rect(group):
        """Rectangle réellement visible (case + image + textes non vides) : les textes
        vides créés par Stamp ne doivent pas consommer d'espace vertical."""
        rect = None
        for c in group.childItems():
            if isinstance(c, QGraphicsTextItem) and not c.toPlainText().strip():
                continue
            r = c.sceneBoundingRect()
            rect = r if rect is None else rect.united(r)
        return rect if rect is not None else group.sceneBoundingRect()

    def _flush_row(self):
        if not self.row or self.scene is None:
            self.row = []
            return
        pending, self.row = self.row, []

        # Découpage automatique si la rangée dépasse la largeur disponible
        avail = self.x1 - self.x0
        gap_fs = mm(self.row_spacing)
        chunks, cur, cur_w = [], [], 0.0
        for s in pending:
            w = mm(s.w)
            extra = w if not cur else gap_fs + w
            if cur and cur_w + extra > avail:
                chunks.append(cur)
                cur, cur_w = [s], w
                self.notes.add("Rangées trop larges coupées automatiquement.")
            else:
                cur.append(s)
                cur_w += extra
        if cur:
            chunks.append(cur)

        for chunk in chunks:
            self._place_row(chunk)

    def _place_row(self, row):
        avail = self.x1 - self.x0
        widths = [mm(s.w) for s in row]
        total = sum(widths)
        n = len(row)
        if self.row_mode == 'JS':
            gap = max(0.0, (avail - total) / (n + 1))
            x = self.x0 + gap
        else:
            gap = mm(self.row_spacing)
            x = self.x0 + max(0.0, (avail - total - gap * (n - 1)) / 2.0)

        placed = []
        for s, w in zip(row, widths):
            if not s.blank:
                grp = self._create_stamp(s)
                box = self._box_of(grp) if grp is not None else None
                if box is not None:
                    br = box.sceneBoundingRect()
                    gr = self._visible_rect(grp)
                    placed.append({'grp': grp, 'x': x, 'top': br.top(), 'left': br.left(),
                                   'h': br.height(), 'above': br.top() - gr.top()})
            x += w + gap
        if not placed:
            return

        H = max(p['h'] for p in placed)
        for p in placed:
            if self.row_align == 'top':
                p['shift'] = 0.0
            elif self.row_align == 'middle':
                p['shift'] = (H - p['h']) / 2.0
            else:
                p['shift'] = H - p['h']
        above = max(p['above'] - p['shift'] for p in placed)
        below = max(self._visible_rect(p['grp']).bottom() - p['top'] - p['shift'] for p in placed)

        # La rangée ne tient plus : page de suite automatique (hors mode colonnes)
        if (self.y + above + below > self.bottom and self.columns is None
                and self.y > self.content_top + 1):
            self._start_page(info=self.pages[-1].is_info, continuation=True)
            self.notes.add("Rangées ne tenant pas dans le cadre reportées sur une page de suite.")
        elif self.y + above + below > self.bottom:
            self.notes.add("Certaines pages débordent du cadre (contenu trop haut).")

        base = self.y + above
        for p in placed:
            p['grp'].moveBy(p['x'] - p['left'], base + p['shift'] - p['top'])
            self._commit(p['grp'])

        self.y = base + below + mm(self.row_gap)

    # ---------------------------------------------------------- objets divers
    def _page_add_box(self, args):
        """PAGE_ADD_BOX (police taille épaisseur x y l h "t1" "t2" "t3" "t4" [angle])"""
        self._flush_row()
        nums = self._nums(args)
        if len(nums) < 6:
            return
        x_mm, y_mm, w_mm, h_mm = nums[2:6]
        s = self._strings(args) + [''] * 4
        grp = self._create_stamp(PendingStamp(w_mm, h_mm, nbr=self._join(s[2], s[3]),
                                              value=self._join(s[0], s[1])))
        box = self._box_of(grp) if grp is not None else None
        if box is None:
            return
        br = box.sceneBoundingRect()
        # Coordonnées AlbumEasy relatives au coin supérieur gauche de la feuille
        grp.moveBy(mm(x_mm) - br.left(), mm(y_mm) - br.top())
        if len(nums) >= 7 and nums[6]:
            center = box.mapToItem(grp, box.boundingRect().center())
            grp.setTransformOriginPoint(center)
            grp.setRotation(nums[6])
            self.notes.add("La rotation des PAGE_ADD_BOX n'est pas conservée à l'enregistrement.")
        self._commit(grp)

    def _page_background_img(self, args):
        strings = self._strings(args)
        if not strings:
            return
        pix = self._load_pixmap(strings[0])
        if pix.isNull():
            return
        from ResizablePixmapItem import ResizablePixmapItem
        nums = self._nums(args) + [1.0, 0.0, 0.0]
        scale_factor, dx, dy = nums[0] or 1.0, nums[1], nums[2]
        rect = self.scene.sceneRect()
        fit = min(rect.width() / pix.width(), rect.height() / pix.height()) * scale_factor
        item = ResizablePixmapItem(pix)
        item.setScale(fit)
        item.setPos((rect.width() - pix.width() * fit) / 2.0 + mm(dx),
                    (rect.height() - pix.height() * fit) / 2.0 + mm(dy))
        item.setZValue(-100)
        self.scene.addItemWithUndo(item, "Background image")

    # ---------------------------------------------------------- réglages album
    def _album_pages_size(self, args):
        nums = self._nums(args)
        if len(nums) >= 2:
            self.page_w_mm, self.page_h_mm = nums[0], nums[1]
            if not any(abs(min(nums[:2]) - v) < 3 for v in (210.0, 215.9)):
                self.notes.add(f"Format {nums[0]}x{nums[1]} mm non géré : A4 utilisé.")

    def _album_pages_margins(self, args):
        nums = self._nums(args)
        if len(nums) >= 4:
            self.margins = nums[:4]

    def _album_pages_border(self, args):
        self.has_border = True

    def _album_pages_spacing(self, args):
        nums = self._nums(args)
        if nums:
            self.row_gap = max(2.0, nums[0])

    def _album_pages_title(self, args):
        strings = self._strings(args)
        if strings:
            self.title = (self._font_from_args(args, 14), strings[-1])

    def _album_define_font(self, args):
        if len(args) >= 2:
            self.fonts[args[0].value.upper()] = args[1].value

    def _album_author(self, args):
        strings = self._strings(args)
        if strings and hasattr(self.win, 'album_metadata'):
            self.win.album_metadata['author'] = strings[0]

    def _footer_number(self, args):
        """ALBUM_PAGES_FOOTER_NUMBER (police taille L|C|R|LR|RL départ "préfixe" "suffixe")"""
        words = [a.value.upper() for a in args[1:] if a.is_word]
        nums = self._nums(args)
        strings = self._strings(args) + ['', '']
        self.footer_number = {
            'font': self._font_from_args(args, 10),
            'align': words[0] if words else 'C',
            'start': int(nums[1]) if len(nums) > 1 else 1,
            'prefix': strings[0], 'suffix': strings[1],
        }

    def _add_footers(self):
        fn = self.footer_number
        if not fn:
            return
        numbered = [p for p in self.pages if not p.is_info]
        last = fn['start'] + len(numbered) - 1
        for k, page in enumerate(numbered):
            n = fn['start'] + k
            text = f"{fn['prefix']}{n}{fn['suffix']}".replace('$PAGES$', str(last))
            probe = QGraphicsTextItem(text)
            probe.setFont(fn['font'])
            w = probe.boundingRect().width()
            align = fn['align']
            if align in ('LR', 'RL'):
                odd = n % 2 == 1
                align = ('L' if odd else 'R') if align == 'LR' else ('R' if odd else 'L')
            if align == 'L':
                x = page.x0
            elif align == 'R':
                x = page.x1 - w
            else:
                x = page.x0 + (page.x1 - page.x0 - w) / 2.0
            # Comme AlbumEasy : sous le cadre s'il reste la place, sinon en bas du cadre
            border = next((it for it in page.scene.items() if it.data(0) == 'borderGroup'), None)
            h = probe.boundingRect().height()
            if border is not None and border.sceneBoundingRect().bottom() + h < page.scene.sceneRect().bottom():
                y = border.sceneBoundingRect().bottom() + 1
            else:
                y = page.bottom - h + mm(2)
            page.scene.addTextLabel(text, x, y, fn['font'], Qt.AlignmentFlag.AlignLeft, "labelPageNbr")
