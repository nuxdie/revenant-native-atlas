"""Read the game's X drawable without grabbing the shared X server."""
import ctypes as C
import ctypes.util
import os

from PIL import Image


class XImage(C.Structure):
    _fields_ = [('width', C.c_int), ('height', C.c_int), ('xoffset', C.c_int),
                ('format', C.c_int), ('data', C.c_void_p), ('byte_order', C.c_int),
                ('bitmap_unit', C.c_int), ('bitmap_bit_order', C.c_int),
                ('bitmap_pad', C.c_int), ('depth', C.c_int), ('bytes_per_line', C.c_int),
                ('bits_per_pixel', C.c_int), ('red_mask', C.c_ulong),
                ('green_mask', C.c_ulong), ('blue_mask', C.c_ulong)]


class WindowCapture:
    def __init__(self, window, display=None, composite=False):
        self.window = int(window)
        self.x = C.CDLL(ctypes.util.find_library('X11'))
        self.x.XOpenDisplay.argtypes = [C.c_char_p]
        self.x.XOpenDisplay.restype = C.c_void_p
        self.x.XGetImage.argtypes = [C.c_void_p, C.c_ulong, C.c_int, C.c_int,
                                    C.c_uint, C.c_uint, C.c_ulong, C.c_int]
        self.x.XGetImage.restype = C.POINTER(XImage)
        self.x.XDestroyImage.argtypes = [C.POINTER(XImage)]
        self.x.XCloseDisplay.argtypes = [C.c_void_p]
        # A disappearing game window should report a failed capture rather
        # than let Xlib terminate the atlas process or wait for a mouse click.
        self._error_handler = C.CFUNCTYPE(C.c_int, C.c_void_p, C.c_void_p)(lambda *_: 0)
        self.x.XSetErrorHandler.argtypes = [C.c_void_p]
        self.x.XSetErrorHandler.restype = C.c_void_p
        self._previous_handler = self.x.XSetErrorHandler(self._error_handler)
        self.display = self.x.XOpenDisplay((display or os.environ.get('DISPLAY', ':0.0')).encode())
        if not self.display:
            raise RuntimeError('Cannot open game display')
        self.pixmap = None
        if composite:
            extension = C.CDLL(ctypes.util.find_library('Xcomposite'))
            extension.XCompositeRedirectWindow.argtypes = [C.c_void_p, C.c_ulong, C.c_int]
            extension.XCompositeUnredirectWindow.argtypes = [C.c_void_p, C.c_ulong, C.c_int]
            extension.XCompositeNameWindowPixmap.argtypes = [C.c_void_p, C.c_ulong]
            extension.XCompositeNameWindowPixmap.restype = C.c_ulong
            self._composite = extension
            self._redirected_window = self.window
            # Automatic redirection keeps the private desktop visible while
            # making its pixels independent of other desktop applications.
            extension.XCompositeRedirectWindow(self.display, self.window, 0)
            self.pixmap = extension.XCompositeNameWindowPixmap(self.display, self.window)
            self.window = self.pixmap

    def frame(self, width=640, height=480):
        raw = self.x.XGetImage(self.display, self.window, 0, 0, width, height, C.c_ulong(-1).value, 2)
        if not raw:
            raise RuntimeError('Game drawable unavailable')
        try:
            info = raw.contents
            data = C.string_at(info.data, info.bytes_per_line * info.height)
            if info.bits_per_pixel == 32 and info.byte_order == 0 and info.red_mask in (0, 0xff0000):
                return Image.frombytes('RGB', (width, height), data, 'raw', 'BGRX', info.bytes_per_line, 1)
            raise RuntimeError(f'Unsupported native display format: {info.bits_per_pixel} bits')
        finally:
            self.x.XDestroyImage(raw)

    def close(self):
        if self.display:
            if self.pixmap:
                self.x.XFreePixmap.argtypes = [C.c_void_p, C.c_ulong]
                self.x.XFreePixmap(self.display, self.pixmap)
                self._composite.XCompositeUnredirectWindow(self.display, self._redirected_window, 0)
            self.x.XCloseDisplay(self.display)
            self.display = None
            self.x.XSetErrorHandler(self._previous_handler)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
