# -*- coding: utf-8 -*-
from krita import Extension, Krita
import os
import struct


class TgaExportOptions(Extension):

    BOTTOM_LEFT = 0
    TOP_LEFT = 2
    VALID_TYPES = (1, 2, 3, 9, 10, 11)

    def __init__(self, parent):
        super().__init__(parent)
        self._last_dir = ''
        self._origin = self.BOTTOM_LEFT
        self._rle = False
        self._depth = 0       # 0 = keep, 24, or 32
        self._footer = True   # TGA 2.0 footer
        self._comment = ''    # Image ID string
        self._processing = False  # re-entrancy guard
        self._load_settings()
        print('[TGA Export Options] __init__ called')

    def _load_settings(self):
        try:
            from PyQt5.QtCore import QSettings
            s = QSettings('krita_plugins', 'tga_export_options')
            saved_dir = s.value('last_dir', '')
            if saved_dir and os.path.isdir(str(saved_dir)):
                self._last_dir = str(saved_dir)
            saved_origin = s.value('origin', 0)
            self._origin = int(saved_origin) if saved_origin is not None else 0
            saved_rle = s.value('rle', 'false')
            self._rle = str(saved_rle).lower() in ('true', '1', 'yes')
            saved_depth = s.value('depth', 0)
            self._depth = int(saved_depth) if saved_depth is not None else 0
            saved_footer = s.value('footer', 'true')
            self._footer = str(saved_footer).lower() not in ('false', '0', 'no')
            saved_comment = s.value('comment', '')
            self._comment = str(saved_comment) if saved_comment else ''
            print('[TGA Export Options] Settings loaded: origin=%s rle=%s depth=%s footer=%s' % (
                'BL' if self._origin == 0 else 'TL',
                self._rle, self._depth, self._footer))
        except Exception as e:
            print('[TGA Export Options] Error loading settings: %s' % e)

    def _save_settings(self):
        try:
            from PyQt5.QtCore import QSettings
            s = QSettings('krita_plugins', 'tga_export_options')
            s.setValue('origin', self._origin)
            s.setValue('rle', 'true' if self._rle else 'false')
            s.setValue('depth', self._depth)
            s.setValue('footer', 'true' if self._footer else 'false')
            s.setValue('comment', self._comment)
            if self._last_dir:
                s.setValue('last_dir', self._last_dir)
            s.sync()
        except Exception as e:
            print('[TGA Export Options] Error saving settings: %s' % e)

    def setup(self):
        print('[TGA Export Options] setup() called')
        try:
            notifier = Krita.instance().notifier()
            notifier.setActive(True)
            notifier.imageSaved.connect(self._on_image_saved)
            print('[TGA Export Options] imageSaved signal connected OK')
        except Exception as e:
            print('[TGA Export Options] ERROR in setup(): %s' % e)

    def createActions(self, window):
        pass

    # ======================================================
    #  ORIGIN DIALOG
    # ======================================================

    def _show_origin_dialog(self, title, info_text=None):
        from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout,
            QLabel, QPushButton, QGroupBox, QRadioButton, QCheckBox,
            QLineEdit, QFrame)

        win = self._get_window()
        dlg = QDialog(win)
        dlg.setWindowTitle(title)
        dlg.setMinimumWidth(420)
        layout = QVBoxLayout(dlg)

        if info_text:
            lbl = QLabel(info_text)
            lbl.setWordWrap(True)
            layout.addWidget(lbl)
            layout.addSpacing(8)

        # --- Origin radio buttons ---
        grp_origin = QGroupBox('Origin')
        gl = QVBoxLayout(grp_origin)
        rb_bl = QRadioButton('Bottom-Left — standard, max compatibility')
        rb_tl = QRadioButton('Top-Left — OpenGL, game engines')

        if self._origin == self.TOP_LEFT:
            rb_tl.setChecked(True)
        else:
            rb_bl.setChecked(True)

        gl.addWidget(rb_bl)
        gl.addWidget(rb_tl)
        layout.addWidget(grp_origin)

        # --- Bit depth radio buttons ---
        grp_depth = QGroupBox('Bit Depth')
        dl = QVBoxLayout(grp_depth)
        rb_keep = QRadioButton('Keep as is — do not change')
        rb_32 = QRadioButton('32 bit (RGBA) — with alpha channel')
        rb_24 = QRadioButton('24 bit (RGB) — no alpha, smaller file')

        if self._depth == 32:
            rb_32.setChecked(True)
        elif self._depth == 24:
            rb_24.setChecked(True)
        else:
            rb_keep.setChecked(True)

        dl.addWidget(rb_keep)
        dl.addWidget(rb_32)
        dl.addWidget(rb_24)
        layout.addWidget(grp_depth)

        # --- Checkboxes ---
        cb_rle = QCheckBox('RLE compression (reduces file size)')
        cb_rle.setChecked(self._rle)
        layout.addWidget(cb_rle)

        layout.addSpacing(2)

        cb_footer = QCheckBox('TGA 2.0 Footer (improves compatibility)')
        cb_footer.setChecked(self._footer)
        layout.addWidget(cb_footer)

        layout.addSpacing(6)

        # --- Comment / Image ID ---
        lbl_comment = QLabel('Comment (Image ID, up to 255 ASCII chars):')
        lbl_comment.setStyleSheet('color: gray; font-size: 11px;')
        layout.addWidget(lbl_comment)
        le_comment = QLineEdit()
        le_comment.setText(self._comment)
        le_comment.setMaxLength(255)
        le_comment.setPlaceholderText('e.g. author, project name (ASCII only)...')
        layout.addWidget(le_comment)

        layout.addSpacing(12)

        # --- Separator ---
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        layout.addWidget(sep)

        layout.addSpacing(6)

        # --- Buttons ---
        btn_layout = QHBoxLayout()
        btn_skip = QPushButton('Skip')
        btn_ok = QPushButton('OK')
        btn_ok.setDefault(True)
        btn_ok.setMinimumWidth(100)
        btn_skip.clicked.connect(dlg.reject)
        btn_ok.clicked.connect(dlg.accept)
        btn_layout.addWidget(btn_skip)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_ok)
        layout.addLayout(btn_layout)

        result = dlg.exec_()

        if result != QDialog.Accepted:
            return None

        # Read values
        origin = self.BOTTOM_LEFT if rb_bl.isChecked() else self.TOP_LEFT
        rle = cb_rle.isChecked()
        footer = cb_footer.isChecked()
        comment = le_comment.text().strip()
        if rb_32.isChecked():
            depth = 32
        elif rb_24.isChecked():
            depth = 24
        else:
            depth = 0

        # Save state (but don't write to disk yet -- caller will do it)
        self._origin = origin
        self._rle = rle
        self._depth = depth
        self._footer = footer
        self._comment = comment

        return {
            'origin': origin,
            'rle': rle,
            'depth': depth,
            'footer': footer,
            'comment': comment,
        }

    # ======================================================
    #  AUTO-INTERCEPT: dialog after saving TGA
    # ======================================================

    def _on_image_saved(self, filename):
        print('[TGA Export Options] imageSaved fired: %s' % repr(filename))

        if self._processing:
            print('[TGA Export Options] Already processing, skipping')
            return

        if not filename:
            return
        if not filename.lower().endswith('.tga'):
            return
        if not os.path.isfile(filename):
            print('[TGA Export Options] File not found: %s' % filename)
            return

        print('[TGA Export Options] TGA detected, showing dialog...')

        self._processing = True
        try:
            basename = os.path.basename(filename)
            info = 'File saved: %s' % basename

            result = self._show_origin_dialog('TGA Export Options', info)
            if result is None:
                print('[TGA Export Options] User skipped')
                return

            self._process_tga(filename, result)

            # Update last_dir only after successful processing
            d = os.path.dirname(os.path.abspath(filename))
            if os.path.isdir(d):
                self._last_dir = d

        except Exception as e:
            print('[TGA Export Options] ERROR in _on_image_saved: %s' % e)
            import traceback
            traceback.print_exc()
            try:
                from PyQt5.QtWidgets import QMessageBox
                QMessageBox.critical(self._get_window(),
                    'TGA Export Options Error', str(e))
            except Exception:
                pass
        finally:
            self._save_settings()
            self._processing = False

    # ======================================================
    #  SINGLE-PASS TGA PROCESSING
    # ======================================================

    def _process_tga(self, path, opts):
        """Read the file once, apply all modifications in memory,
        write the result once."""

        from PyQt5.QtWidgets import QApplication
        from PyQt5.QtCore import Qt

        # Show wait cursor while processing
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            self._process_tga_impl(path, opts)
        finally:
            QApplication.restoreOverrideCursor()

    def _process_tga_impl(self, path, opts):
        """Internal implementation (called under wait cursor)."""

        origin = opts['origin']
        rle = opts['rle']
        depth = opts['depth']  # 0 = keep, 24, or 32
        footer = opts['footer']
        comment = opts.get('comment', '')

        with open(path, 'rb') as f:
            data = bytearray(f.read())

        if len(data) < 18:
            raise ValueError('File too small for TGA')

        parts = []

        # --- Parse header ---
        id_len = data[0]
        cmap_type = data[1]
        img_type = data[2]

        # --- Validate image type ---
        if img_type not in self.VALID_TYPES:
            raise ValueError('Unsupported TGA image type: %d' % img_type)

        cmap_len = struct.unpack_from('<H', data, 5)[0]
        cmap_bpp = data[7]
        w = struct.unpack_from('<H', data, 12)[0]
        h = struct.unpack_from('<H', data, 14)[0]
        bpp = data[16]
        desc = data[17]

        Bpp = (bpp + 7) // 8

        # --- Validate pixel depth ---
        if Bpp == 0:
            raise ValueError('Invalid TGA: pixel depth is 0')

        cmap_size = cmap_len * ((cmap_bpp + 7) // 8) if cmap_type == 1 else 0
        pix_off = 18 + id_len + cmap_size

        # --- Strip existing TGA 2.0 footer ---
        if len(data) >= 26 and data[-18:-2] == bytearray(b'TRUEVISION-XFILE'):
            data = data[:-26]

        # --- Decompress RLE if needed ---
        is_rle = img_type in (9, 10, 11)
        expected_size = w * h * Bpp
        if is_rle:
            pixels = self._rle_decode(data[pix_off:], w, h, Bpp)
            img_type = {9: 1, 10: 2, 11: 3}[img_type]
        else:
            pix_end = pix_off + expected_size
            pixels = bytearray(data[pix_off:pix_end])

        # --- Validate decoded pixel data size ---
        if len(pixels) != expected_size:
            raise ValueError(
                'Pixel data size mismatch: expected %d bytes, got %d' % (
                    expected_size, len(pixels)))

        # --- 1) Fix origin ---
        cur_origin = (desc >> 4) & 3
        origin_name = 'Bottom-Left' if origin == self.BOTTOM_LEFT else 'Top-Left'
        if cur_origin != origin:
            row_bytes = w * Bpp
            rows = []
            for y in range(h):
                s = y * row_bytes
                rows.append(pixels[s:s + row_bytes])

            # Flip vertically if top/bottom differs
            if (cur_origin ^ origin) & 2:
                rows.reverse()

            # Flip horizontally if left/right differs
            if (cur_origin ^ origin) & 1:
                flipped = []
                for row in rows:
                    nr = bytearray(row_bytes)
                    for x in range(w):
                        src_off = (w - 1 - x) * Bpp
                        dst_off = x * Bpp
                        nr[dst_off:dst_off + Bpp] = row[src_off:src_off + Bpp]
                    flipped.append(nr)
                rows = flipped

            pixels = bytearray().join(rows)

            desc = (desc & 0x0F) | (origin << 4)
            print('[TGA Export Options] Origin set to %s' % origin_name)
        else:
            print('[TGA Export Options] Already %s' % origin_name)
        parts.append('origin=%s' % origin_name)

        # --- 2) Change bit depth ---
        depth_changed = False
        depth_unsupported = False
        if depth in (24, 32) and bpp != depth and img_type == 2:
            if bpp == 32 and depth == 24:
                # BGRA -> BGR: strip alpha using memoryview for speed
                mv = memoryview(pixels)
                new_pixels = bytearray(w * h * 3)
                for i in range(w * h):
                    so = i * 4
                    do = i * 3
                    new_pixels[do:do + 3] = mv[so:so + 3]
                pixels = new_pixels
                bpp = 24
                Bpp = 3
                desc = desc & 0xF0  # 0 alpha bits
                depth_changed = True
                print('[TGA Export Options] Depth changed: 32 -> 24')
            elif bpp == 24 and depth == 32:
                # BGR -> BGRA: add alpha=255
                mv = memoryview(pixels)
                new_pixels = bytearray(w * h * 4)
                for i in range(w * h):
                    so = i * 3
                    do = i * 4
                    new_pixels[do:do + 3] = mv[so:so + 3]
                    new_pixels[do + 3] = 0xFF
                pixels = new_pixels
                bpp = 32
                Bpp = 4
                desc = (desc & 0xF0) | 8  # 8 alpha bits
                depth_changed = True
                print('[TGA Export Options] Depth changed: 24 -> 32')
            elif bpp == 16:
                depth_unsupported = True
                print('[TGA Export Options] 16-bit depth conversion not supported, keeping as is')

        if depth_changed:
            parts.append('%d bit' % bpp)
        elif depth_unsupported:
            parts.append('depth=%d bit (unchanged)' % bpp)
        else:
            parts.append('depth=keep')

        # --- 3) Prepare comment / Image ID ---
        comment_bytes = bytearray()
        non_ascii_count = 0
        for ch in comment[:255]:
            if ord(ch) < 128:
                comment_bytes.append(ord(ch))
            else:
                comment_bytes.append(ord('?'))
                non_ascii_count += 1
        new_id_len = len(comment_bytes)
        if comment:
            parts.append('id=%s' % comment[:20])
            print('[TGA Export Options] Image ID set: %s' % repr(comment))
        if non_ascii_count > 0:
            print('[TGA Export Options] Warning: %d non-ASCII char(s) replaced' % non_ascii_count)

        # --- 4) RLE compress if requested ---
        if rle and img_type in (1, 2, 3):
            pixel_data = self._rle_encode(pixels, w, h, Bpp)
            out_type = {1: 9, 2: 10, 3: 11}[img_type]
            parts.append('RLE')
            print('[TGA Export Options] RLE applied')
        else:
            pixel_data = pixels
            out_type = img_type
            if not rle:
                print('[TGA Export Options] Uncompressed')

        # --- 5) Build new color map data ---
        cmap_data = data[18 + id_len:pix_off]

        # --- 6) Build the complete file ---
        header = bytearray(18)
        header[0] = new_id_len
        header[1] = cmap_type
        header[2] = out_type
        header[3:8] = data[3:8]  # cmap spec
        header[8:12] = data[8:12]  # x/y origin
        struct.pack_into('<H', header, 12, w)
        struct.pack_into('<H', header, 14, h)
        header[16] = bpp
        header[17] = desc

        out = bytearray()
        out.extend(header)
        if new_id_len > 0:
            out.extend(comment_bytes)
        out.extend(cmap_data)
        out.extend(pixel_data)

        # --- 7) TGA 2.0 footer ---
        if footer:
            # 4 bytes ext offset + 4 bytes dev offset + 16 bytes sig + '.' + null
            foot = struct.pack('<II', 0, 0)
            foot += b'TRUEVISION-XFILE'
            foot += b'.' + bytes([0])
            out.extend(foot)
            parts.append('TGA2.0')
            print('[TGA Export Options] TGA 2.0 footer added')

        # --- Write result ---
        with open(path, 'wb') as f:
            f.write(bytes(out))

        # Status bar message
        status = 'TGA: %s' % ', '.join(parts)
        self._show_status(status)
        print('[TGA Export Options] Done: %s' % status)

    def _show_status(self, msg):
        try:
            w = Krita.instance().activeWindow()
            if w and hasattr(w, 'qwindow'):
                qw = w.qwindow()
                sb = qw.statusBar()
                if sb:
                    sb.showMessage(msg, 5000)
                    return
        except Exception:
            pass
        print('[TGA Export Options] Status: %s' % msg)

    # ======================================================
    #  HELPERS
    # ======================================================

    def _get_window(self):
        try:
            w = Krita.instance().activeWindow()
            if w:
                return w.qwindow()
        except Exception:
            pass
        return None

    # ======================================================
    #  RLE COMPRESSION / DECOMPRESSION
    # ======================================================

    def _rle_encode(self, pixels, w, h, Bpp):
        mv = memoryview(pixels)
        out = bytearray()
        total = w * h
        i = 0
        while i < total:
            off = i * Bpp
            px_slice = mv[off:off + Bpp]
            # Count run of identical pixels (zero-copy via memoryview)
            run = 1
            while i + run < total and run < 128:
                ro = (i + run) * Bpp
                if mv[ro:ro + Bpp] != px_slice:
                    break
                run += 1
            if run >= 3:
                # RLE packet: worth it for 3+ identical pixels
                out.append(0x80 | (run - 1))
                out.extend(px_slice)
                i += run
            else:
                # Raw packet: collect non-repeating pixels
                raw = 1
                while i + raw < total and raw < 128:
                    # Look ahead: if next 3 pixels are identical, stop raw
                    ro = (i + raw) * Bpp
                    nxt = mv[ro:ro + Bpp]
                    if i + raw + 2 < total:
                        r1 = (i + raw + 1) * Bpp
                        r2 = (i + raw + 2) * Bpp
                        if nxt == mv[r1:r1 + Bpp] == mv[r2:r2 + Bpp]:
                            break
                    raw += 1
                out.append(raw - 1)
                out.extend(mv[off:off + raw * Bpp])
                i += raw
        return out

    def _rle_decode(self, src, w, h, Bpp):
        expected = w * h * Bpp
        out = bytearray(expected)
        total = w * h
        i = 0
        pos = 0
        count = 0
        while count < total and i < len(src):
            hdr = src[i]
            i += 1
            n = (hdr & 0x7F) + 1
            # Clamp to remaining pixels to handle overshooting last packet
            if count + n > total:
                n = total - count
            if hdr & 0x80:
                if i + Bpp > len(src):
                    raise ValueError('RLE data truncated in run-length packet')
                px = src[i:i + Bpp]
                i += Bpp
                for _ in range(n):
                    out[pos:pos + Bpp] = px
                    pos += Bpp
            else:
                chunk = n * Bpp
                if i + chunk > len(src):
                    raise ValueError('RLE data truncated in raw packet')
                out[pos:pos + chunk] = src[i:i + chunk]
                pos += chunk
                i += chunk
            count += n
        if pos != expected:
            raise ValueError(
                'RLE decode size mismatch: expected %d bytes, got %d' % (
                    expected, pos))
        return out


Krita.instance().addExtension(TgaExportOptions(Krita.instance()))
