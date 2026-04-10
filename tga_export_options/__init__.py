# -*- coding: utf-8 -*-
from krita import Extension, Krita
import os
import struct
import traceback


def _tga_encode_row(mv, w, Bpp):
    """RLE-encode one row of pixels from a memoryview slice.

    Pre-extracts pixels as bytes objects so comparisons are C-level
    bytes == bytes with no per-iteration memoryview slice creation.
    """
    px_list = [bytes(mv[j * Bpp:(j + 1) * Bpp]) for j in range(w)]
    out = bytearray()
    i = 0
    while i < w:
        px  = px_list[i]
        run = 1
        while i + run < w and run < 128 and px_list[i + run] == px:
            run += 1

        if run >= 3:
            out.append(0x80 | (run - 1))
            out.extend(px)
            i += run
            continue

        # Raw packet: stop just before a run of 3+ identical pixels.
        raw = 1
        while i + raw < w and raw < 128:
            ni = i + raw
            if ni + 2 < w and px_list[ni] == px_list[ni + 1] == px_list[ni + 2]:
                break
            raw += 1
        out.append(raw - 1)
        out.extend(mv[i * Bpp:(i + raw) * Bpp])    # single slice for whole packet
        i += raw
    return out

from PyQt5.QtCore import Qt, QSettings
from PyQt5.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QGroupBox, QRadioButton, QCheckBox,
    QLineEdit, QFrame, QMessageBox,
)


class TgaExportOptions(Extension):

    BOTTOM_LEFT = 0
    TOP_LEFT    = 2
    VALID_TYPES = frozenset({1, 2, 3, 9, 10, 11})

    # RLE image-type mappings (class attrs — no per-call dict creation)
    _RLE_TO_RAW = {9: 1, 10: 2, 11: 3}
    _RAW_TO_RLE = {1: 9, 2: 10, 3: 11}

    # ext_offset(4) + dev_offset(4) + signature(16) + '.' + NUL
    _TGA_FOOTER = struct.pack('<II', 0, 0) + b'TRUEVISION-XFILE.\x00'

    def __init__(self, parent):
        super().__init__(parent)
        self._last_dir   = ''
        self._origin     = self.BOTTOM_LEFT
        self._rle        = False
        self._depth      = 0       # 0 = keep, 24, or 32
        self._footer     = True    # TGA 2.0 footer
        self._comment    = ''      # Image ID string
        self._processing = False   # re-entrancy guard
        self._log('__init__ called')
        self._load_settings()

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    def _log(self, msg):
        print(f'[TGA Export Options] {msg}')

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    @staticmethod
    def _qs_int(s, key, default):
        try:
            return int(s.value(key, default))
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _qs_bool(s, key, default):
        v = s.value(key, 'true' if default else 'false')
        return str(v).lower() in ('true', '1', 'yes')

    def _load_settings(self):
        try:
            s = QSettings('krita_plugins', 'tga_export_options')
            saved_dir = s.value('last_dir', '')
            if saved_dir and os.path.isdir(str(saved_dir)):
                self._last_dir = str(saved_dir)
            self._origin  = self._qs_int(s,  'origin', 0)
            self._rle     = self._qs_bool(s, 'rle',    False)
            self._depth   = self._qs_int(s,  'depth',  0)
            self._footer  = self._qs_bool(s, 'footer', True)
            saved_comment = s.value('comment', '')
            self._comment = str(saved_comment) if saved_comment else ''
            self._log(f'Settings loaded: origin={"BL" if self._origin == 0 else "TL"} '
                      f'rle={self._rle} depth={self._depth} footer={self._footer}')
        except Exception as e:
            self._log(f'Error loading settings: {e}')

    def _save_settings(self):
        try:
            s = QSettings('krita_plugins', 'tga_export_options')
            s.setValue('origin',  self._origin)
            s.setValue('rle',     'true' if self._rle else 'false')
            s.setValue('depth',   self._depth)
            s.setValue('footer',  'true' if self._footer else 'false')
            s.setValue('comment', self._comment)
            if self._last_dir:
                s.setValue('last_dir', self._last_dir)
            s.sync()
        except Exception as e:
            self._log(f'Error saving settings: {e}')

    # ------------------------------------------------------------------
    # Krita extension hooks
    # ------------------------------------------------------------------

    def setup(self):
        self._log('setup() called')
        try:
            notifier = Krita.instance().notifier()
            notifier.setActive(True)
            notifier.imageSaved.connect(self._on_image_saved)
            self._log('imageSaved signal connected OK')
        except Exception as e:
            self._log(f'ERROR in setup(): {e}')

    def createActions(self, _window):
        pass

    # ------------------------------------------------------------------
    # Dialog
    # ------------------------------------------------------------------

    def _show_export_dialog(self, title, info_text=None):
        """Show the export options dialog.

        Updates self._origin/_rle/_depth/_footer/_comment on OK.
        Returns True if accepted, False if skipped.
        """
        dlg = QDialog(self._get_window())
        dlg.setWindowTitle(title)
        dlg.setMinimumWidth(420)
        layout = QVBoxLayout(dlg)

        if info_text:
            lbl = QLabel(info_text)
            lbl.setWordWrap(True)
            layout.addWidget(lbl)
            layout.addSpacing(8)

        # --- Origin ---
        grp_origin = QGroupBox('Origin')
        gl = QVBoxLayout(grp_origin)
        rb_bl = QRadioButton('Bottom-Left — standard, max compatibility')
        rb_tl = QRadioButton('Top-Left — OpenGL, game engines')
        (rb_tl if self._origin == self.TOP_LEFT else rb_bl).setChecked(True)
        gl.addWidget(rb_bl)
        gl.addWidget(rb_tl)
        layout.addWidget(grp_origin)

        # --- Bit depth ---
        grp_depth = QGroupBox('Bit Depth')
        dl = QVBoxLayout(grp_depth)
        rb_keep = QRadioButton('Keep as is — do not change')
        rb_32   = QRadioButton('32 bit (RGBA) — with alpha channel')
        rb_24   = QRadioButton('24 bit (RGB) — no alpha, smaller file')
        {32: rb_32, 24: rb_24}.get(self._depth, rb_keep).setChecked(True)
        for rb in (rb_keep, rb_32, rb_24):
            dl.addWidget(rb)
        layout.addWidget(grp_depth)

        # --- Checkboxes ---
        cb_rle    = QCheckBox('RLE compression (reduces file size)')
        cb_footer = QCheckBox('TGA 2.0 Footer (improves compatibility)')
        cb_rle.setChecked(self._rle)
        cb_footer.setChecked(self._footer)
        layout.addWidget(cb_rle)
        layout.addSpacing(2)
        layout.addWidget(cb_footer)
        layout.addSpacing(6)

        # --- Comment / Image ID ---
        lbl_comment = QLabel('Comment (Image ID, up to 255 ASCII chars):')
        lbl_comment.setStyleSheet('color: gray; font-size: 11px;')
        layout.addWidget(lbl_comment)
        le_comment = QLineEdit(self._comment)
        le_comment.setMaxLength(255)
        le_comment.setPlaceholderText('e.g. author, project name (ASCII only)...')
        layout.addWidget(le_comment)
        layout.addSpacing(12)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        layout.addWidget(sep)
        layout.addSpacing(6)

        # --- Buttons ---
        btn_layout = QHBoxLayout()
        btn_skip = QPushButton('Skip')
        btn_ok   = QPushButton('OK')
        btn_ok.setDefault(True)
        btn_ok.setMinimumWidth(100)
        btn_skip.clicked.connect(dlg.reject)
        btn_ok.clicked.connect(dlg.accept)
        btn_layout.addWidget(btn_skip)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_ok)
        layout.addLayout(btn_layout)

        if dlg.exec_() != QDialog.Accepted:
            return False

        if rb_32.isChecked():
            depth = 32
        elif rb_24.isChecked():
            depth = 24
        else:
            depth = 0

        self._origin  = self.BOTTOM_LEFT if rb_bl.isChecked() else self.TOP_LEFT
        self._rle     = cb_rle.isChecked()
        self._depth   = depth
        self._footer  = cb_footer.isChecked()
        self._comment = le_comment.text().strip()
        return True

    # ------------------------------------------------------------------
    # imageSaved handler
    # ------------------------------------------------------------------

    def _on_image_saved(self, filename):
        self._log(f'imageSaved fired: {filename!r}')

        if self._processing:
            self._log('Already processing, skipping')
            return
        if not filename or not filename.lower().endswith('.tga'):
            return
        if not os.path.isfile(filename):
            self._log(f'File not found: {filename}')
            return

        self._log('TGA detected, showing dialog...')
        self._processing = True
        try:
            if not self._show_export_dialog(
                    'TGA Export Options',
                    f'File saved: {os.path.basename(filename)}'):
                self._log('User skipped')
                return

            self._process_tga(filename)

            d = os.path.dirname(os.path.abspath(filename))
            if os.path.isdir(d):
                self._last_dir = d

        except Exception as e:
            self._log(f'ERROR in _on_image_saved: {e}')
            traceback.print_exc()
            try:
                QMessageBox.critical(self._get_window(), 'TGA Export Options Error', str(e))
            except Exception:
                pass
        finally:
            self._save_settings()
            self._processing = False

    # ------------------------------------------------------------------
    # TGA processing
    # ------------------------------------------------------------------

    def _process_tga(self, path):
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            with open(path, 'rb') as f:
                data = bytearray(f.read())

            if len(data) < 18:
                raise ValueError('File too small for TGA')

            # Parse header
            id_len    = data[0]
            cmap_type = data[1]
            img_type  = data[2]

            if img_type not in self.VALID_TYPES:
                raise ValueError(f'Unsupported TGA image type: {img_type}')

            cmap_len = struct.unpack_from('<H', data, 5)[0]
            cmap_bpp = data[7]
            w, h     = struct.unpack_from('<HH', data, 12)
            bpp      = data[16]
            desc     = data[17]
            Bpp      = (bpp + 7) // 8

            if Bpp == 0:
                raise ValueError('Invalid TGA: pixel depth is 0')

            cmap_size = cmap_len * ((cmap_bpp + 7) // 8) if cmap_type == 1 else 0
            pix_off   = 18 + id_len + cmap_size

            # Strip existing TGA 2.0 footer
            if len(data) >= 26 and data[-18:-2] == b'TRUEVISION-XFILE':
                data = data[:-26]

            # Decompress RLE if present
            expected_size = w * h * Bpp
            if img_type in self._RLE_TO_RAW:
                pixels   = self._rle_decode(data[pix_off:], w, h, Bpp)
                img_type = self._RLE_TO_RAW[img_type]
            else:
                pixels = data[pix_off:pix_off + expected_size]  # bytearray slice, no copy

            if len(pixels) != expected_size:
                raise ValueError(
                    f'Pixel data size mismatch: expected {expected_size} bytes, got {len(pixels)}')

            parts = []

            # --- 1) Fix origin ---
            cur_origin  = (desc >> 4) & 3
            origin_name = 'Bottom-Left' if self._origin == self.BOTTOM_LEFT else 'Top-Left'
            if cur_origin != self._origin:
                row_bytes = w * Bpp
                mv_px = memoryview(pixels)
                rows = [mv_px[y * row_bytes:(y + 1) * row_bytes] for y in range(h)]

                if (cur_origin ^ self._origin) & 2:     # vertical flip
                    rows.reverse()

                if (cur_origin ^ self._origin) & 1:     # horizontal flip
                    rows = [self._flip_row(row, w, Bpp) for row in rows]

                pixels = bytearray().join(rows)
                desc   = (desc & 0x0F) | (self._origin << 4)
                self._log(f'Origin set to {origin_name}')
            else:
                self._log(f'Already {origin_name}')
            parts.append(f'origin={origin_name}')

            # --- 2) Change bit depth ---
            if self._depth in (24, 32) and bpp != self._depth and img_type == 2:
                if bpp == 32 and self._depth == 24:
                    pixels, bpp, Bpp, desc = self._bgra_to_bgr(pixels, w, h, desc)
                    self._log('Depth changed: 32 -> 24')
                    parts.append('24 bit')
                elif bpp == 24 and self._depth == 32:
                    pixels, bpp, Bpp, desc = self._bgr_to_bgra(pixels, w, h, desc)
                    self._log('Depth changed: 24 -> 32')
                    parts.append('32 bit')
                elif bpp == 16:
                    self._log('16-bit depth conversion not supported, keeping as is')
                    parts.append(f'depth={bpp} bit (unchanged)')
            else:
                parts.append('depth=keep')

            # --- 3) Comment / Image ID ---
            comment_clipped = self._comment[:255]
            comment_bytes   = comment_clipped.encode('ascii', 'replace')
            non_ascii       = sum(1 for c in comment_clipped if ord(c) > 127)
            new_id_len      = len(comment_bytes)
            if self._comment:
                parts.append(f'id={self._comment[:20]}')
                self._log(f'Image ID set: {self._comment!r}')
            if non_ascii:
                self._log(f'Warning: {non_ascii} non-ASCII char(s) replaced')

            # --- 4) RLE compression ---
            if self._rle and img_type in self._RAW_TO_RLE:
                pixel_data = self._rle_encode(pixels, w, h, Bpp)
                out_type   = self._RAW_TO_RLE[img_type]
                parts.append('RLE')
                self._log('RLE applied')
            else:
                pixel_data = pixels
                out_type   = img_type
                if not self._rle:
                    self._log('Uncompressed')

            # --- 5) Color map data ---
            cmap_data = data[18 + id_len:pix_off]

            # --- 6) Assemble header: copy original, patch only changed fields ---
            header     = bytearray(data[:18])
            header[0]  = new_id_len   # id length  (comment may differ from original)
            header[2]  = out_type     # image type (RLE flag may have changed)
            header[16] = bpp          # bits/pixel (may have changed on depth convert)
            header[17] = desc         # descriptor (origin bits / alpha bits)

            if self._footer:
                parts.append('TGA2.0')
                self._log('TGA 2.0 footer added')

            # Single allocation: b''.join pre-computes total size before copying
            out_parts = [header]
            if new_id_len:
                out_parts.append(comment_bytes)
            out_parts.append(cmap_data)
            out_parts.append(pixel_data)
            if self._footer:
                out_parts.append(self._TGA_FOOTER)

            with open(path, 'wb') as f:
                f.write(b''.join(out_parts))

            status = 'TGA: ' + ', '.join(parts)
            self._show_status(status)
            self._log(f'Done: {status}')

        finally:
            QApplication.restoreOverrideCursor()

    # ------------------------------------------------------------------
    # Pixel format converters (channel-stride slice ops — C-level speed)
    # ------------------------------------------------------------------

    @staticmethod
    def _bgra_to_bgr(pixels, w, h, desc):
        """BGRA (32-bit) -> BGR (24-bit)."""
        n   = w * h
        out = bytearray(n * 3)
        out[0::3] = pixels[0::4]    # B
        out[1::3] = pixels[1::4]    # G
        out[2::3] = pixels[2::4]    # R
        return out, 24, 3, desc & 0xF0          # 0 alpha bits

    @staticmethod
    def _bgr_to_bgra(pixels, w, h, desc):
        """BGR (24-bit) -> BGRA (32-bit)."""
        n   = w * h
        out = bytearray(n * 4)
        out[0::4] = pixels[0::3]    # B
        out[1::4] = pixels[1::3]    # G
        out[2::4] = pixels[2::3]    # R
        out[3::4] = b'\xff' * n     # A = fully opaque
        return out, 32, 4, (desc & 0xF0) | 8   # 8 alpha bits

    @staticmethod
    def _flip_row(row, w, Bpp):
        """Reverse pixel order within a row (per-channel stride reverse)."""
        out = bytearray(w * Bpp)
        for c in range(Bpp):
            out[c::Bpp] = row[c::Bpp][::-1]
        return out

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _show_status(self, msg):
        try:
            qwin = self._get_window()
            if qwin:
                sb = qwin.statusBar()
                if sb:
                    sb.showMessage(msg, 5000)
                    return
        except Exception:
            pass
        self._log(f'Status: {msg}')

    def _get_window(self):
        try:
            w = Krita.instance().activeWindow()
            if w:
                return w.qwindow()
        except Exception:
            pass
        return None

    # ------------------------------------------------------------------
    # RLE codec
    # ------------------------------------------------------------------

    @staticmethod
    def _rle_encode(pixels, w, h, Bpp):
        # Encode each row independently — no packet may cross a row boundary.
        # Row-by-row decoders (most game engines) require this; cross-row
        # packets cause channel misalignment and row displacement.
        row_bytes = w * Bpp
        mv = memoryview(pixels)
        return bytearray().join(
            _tga_encode_row(mv[s:s + row_bytes], w, Bpp)
            for s in range(0, h * row_bytes, row_bytes)
        )

    @staticmethod
    def _rle_decode(src, w, h, Bpp):
        expected            = w * h * Bpp
        out                 = bytearray(expected)
        total               = w * h
        i = pos = pix_count = 0

        while pix_count < total and i < len(src):
            hdr = src[i]
            i  += 1
            n   = (hdr & 0x7F) + 1
            if pix_count + n > total:
                n = total - pix_count

            if hdr & 0x80:
                if i + Bpp > len(src):
                    raise ValueError('RLE data truncated in run-length packet')
                # bytes * n: single C-level allocation, far faster than a Python loop.
                out[pos:pos + n * Bpp] = src[i:i + Bpp] * n
                pos += n * Bpp
                i   += Bpp
            else:
                chunk = n * Bpp
                if i + chunk > len(src):
                    raise ValueError('RLE data truncated in raw packet')
                out[pos:pos + chunk] = src[i:i + chunk]
                pos += chunk
                i   += chunk
            pix_count += n

        if pos != expected:
            raise ValueError(
                f'RLE decode size mismatch: expected {expected} bytes, got {pos}')
        return out


Krita.instance().addExtension(TgaExportOptions(Krita.instance()))
