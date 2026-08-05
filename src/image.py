from ctypes import *
from ctypes.wintypes import *

from webview2.winapp.dlls import gdi32, user32
from webview2.winapp.const import *
from libpng import *



# https://learn.microsoft.com/en-us/windows/win32/api/winuser/ns-winuser-iconinfo
class ICONINFO(Structure):
    _fields_ = [
        ("fIcon", BOOL),
        ("xHotspot", DWORD),
        ("yHotspot", DWORD),
        ("hbmMask", HBITMAP),
        ("hbmColor", HBITMAP)
    ]

# https://learn.microsoft.com/en-us/windows/win32/api/wingdi/ns-wingdi-bitmap
#class BITMAP(Structure):
#    _fields_ = [
#        ("bmType", LONG),
#        ("bmWidth", LONG),
#        ("bmHeight", LONG),
#        ("bmWidthBytes", LONG),
#        ("bmPlanes", WORD),
#        ("bmBitsPixel", WORD),
#        ("bmBits", LPVOID),
#    ]

# https://learn.microsoft.com/en-us/windows/win32/api/wingdi/ns-wingdi-bitmapinfoheader
class BITMAPINFOHEADER(Structure):
    def __init__(self):
        self.biSize = sizeof(self)
    _fields_ = [
        ("biSize", DWORD),
        ("biWidth", LONG),
        ("biHeight", LONG),
        ("biPlanes", WORD),
        ("biBitCount", WORD),
        ("biCompression", DWORD),
        ("biSizeImage", DWORD),
        ("biXPelsPerMeter", LONG),
        ("biYPelsPerMeter", LONG),
        ("biClrUsed", DWORD),
        ("biClrImportant", DWORD)
    ]

# Custom
class BMPHEADER(Structure):
    _pack_ = 2
    _fields_ = [
        ('magic', SHORT),
        ('size', DWORD),
        ('reserved', DWORD),
        ('offset', DWORD),
    ]
    def __init__(self, *args, **kwargs):
        super(BMPHEADER, self).__init__(*args, **kwargs)
        self.magic = 0x4D42  # BM
        self.offset = sizeof(self) + sizeof(BITMAPINFOHEADER)

# https://learn.microsoft.com/en-us/windows/win32/api/wingdi/ns-wingdi-bitmapinfo
class BITMAPINFO(Structure):
    _fields_ = [
        ("bmiHeader", BITMAPINFOHEADER),
    ]

# https://learn.microsoft.com/en-us/windows/win32/api/wingdi/ns-wingdi-rgbquad
class RGBQUAD(Structure):
    _fields_ = [
        ("rgbBlue", BYTE),
        ("rgbGreen", BYTE),
        ("rgbRed", BYTE),
        ("rgbReserved", BYTE),
    ]

msimg32 = windll.Msimg32

class BLENDFUNCTION(Structure):
    _fields_ = [
        ("BlendOp", BYTE),
        ("BlendFlags", BYTE),
        ("SourceConstantAlpha", BYTE),
        ("AlphaFormat", BYTE),
    ]

msimg32.AlphaBlend.argtypes = (
    HDC, INT, INT, INT, INT,
    HDC, INT, INT, INT, INT,
    BLENDFUNCTION
)

########################################
# For HBITMAPS used in menus, Windows needs hidden pixels (alpha = 0)
# to be black, otherwise the menu icons have strange artifacts. Achieving
# this with plain GDI is astonishingly complicate...
########################################
def hbitmap_fix_alpha(h_bitmap, w = 16, h = 16):

    hdc = user32.GetDC(None)

    h_bitmap_copy = user32.CopyImage(h_bitmap, IMAGE_BITMAP, w, h, LR_CREATEDIBSECTION)

    hdc_a = gdi32.CreateCompatibleDC(hdc)
    gdi32.SelectObject(hdc_a, h_bitmap_copy)

    hdc_b = gdi32.CreateCompatibleDC(hdc)
    h_bitmap_tmp = gdi32.CreateCompatibleBitmap(hdc_a, w, h)
    gdi32.SelectObject(hdc_b, h_bitmap_tmp)

    bi = BITMAPINFO()
    bi.bmiHeader.biSize        = sizeof(BITMAPINFOHEADER)
    bi.bmiHeader.biWidth       = 1
    bi.bmiHeader.biHeight      = 1
    bi.bmiHeader.biPlanes      = 1
    bi.bmiHeader.biBitCount    = 32
    bi.bmiHeader.biCompression = BI_RGB

    ok = gdi32.StretchDIBits(
        hdc_a, 0, 0, w, h,
        0, 0, 1, 1,
        byref(RGBQUAD(0x00, 0x00, 0x00, 0xFF)),
        byref(bi),
        DIB_RGB_COLORS, SRCAND
    )

    # h_bitmap_copy (hdc_a) is now all black and has original alpha channel

    h_bitmap_alpha_only = user32.CopyImage(h_bitmap_copy, IMAGE_BITMAP, w, h, LR_CREATEDIBSECTION)

    gdi32.BitBlt(
        hdc_b, 0, 0, w, h,
        hdc_a, 0, 0,
        NOTSRCCOPY,
    )
    gdi32.StretchDIBits(
        hdc_b, 0, 0, w, h,
        0, 0, 1, 1,
        byref(RGBQUAD(0x00, 0x00, 0x00, 0xFF)),
        byref(bi),
        DIB_RGB_COLORS, SRCAND
    )

    # h_bitmap_tmp (hdc_b) is now all black and has inverted alpha channel

    gdi32.SelectObject(hdc_a, h_bitmap)

    ok = msimg32.AlphaBlend(
        hdc_a, 0, 0, w, h,
        hdc_b, 0, 0, w, h,
        BLENDFUNCTION(AC_SRC_OVER, 0, 255, AC_SRC_ALPHA)
    )

    # h_bitmap (hdc_a) is now a bitmap with all hidden pixels (alpha=0) being black, but with
    # wrong alpha channel, so restore the original alpha channel.

    gdi32.StretchDIBits(
        hdc_a, 0, 0, w, h,
        0, 0, 1, 1,
        byref(RGBQUAD(0xFF, 0xFF, 0xFF, 0x00)),
        byref(bi),
        DIB_RGB_COLORS, SRCAND
    )
    gdi32.SelectObject(hdc_b, h_bitmap_alpha_only)
    gdi32.BitBlt(
        hdc_a, 0, 0, w, h,
        hdc_b, 0, 0,
        SRCPAINT,
    )

    # Clean up
    gdi32.DeleteObject(h_bitmap_copy)
    gdi32.DeleteObject(h_bitmap_tmp)
    gdi32.DeleteObject(h_bitmap_alpha_only)

    gdi32.DeleteDC(hdc_a)
    gdi32.DeleteDC(hdc_b)
    user32.ReleaseDC(None, hdc)

########################################
#
########################################
def bytes_to_hbitmap(data, bmWidth, bmHeight, bytes_per_pixel=4):
    bits = create_string_buffer(data)

    bmiHeader = BITMAPINFOHEADER()
    bmiHeader.biSize = sizeof(BITMAPINFOHEADER)
    bmiHeader.biWidth = bmWidth
    bmiHeader.biHeight = -bmHeight
    bmiHeader.biPlanes = 1
    bmiHeader.biBitCount = 8 * bytes_per_pixel
    bmiHeader.biCompression = BI_RGB
    bmiHeader.biSizeImage = ((((bmWidth * bmiHeader.biBitCount) + 31) & ~31) >> 3) * bmHeight

    bi = BITMAPINFO()
    bi.bmiHeader = bmiHeader
    h_bitmap = gdi32.CreateDIBSection(None, byref(bi), DIB_RGB_COLORS, None, None, 0)
    gdi32.SetDIBits(None, h_bitmap, 0, bmHeight, bits, byref(bi), DIB_RGB_COLORS)

    return h_bitmap

########################################
#
########################################
def hicon_to_hbitmap(h_icon, bitmap_size = 16, is_8bit = False):
    hdc = user32.GetDC(None)
    h_bitmap = gdi32.CreateCompatibleBitmap(hdc, bitmap_size, bitmap_size)

    hdc_dest = gdi32.CreateCompatibleDC(hdc)
    gdi32.SelectObject(hdc_dest, h_bitmap)

    user32.DrawIconEx(hdc_dest, 0, 0, h_icon, bitmap_size, bitmap_size, 0, None, DI_NORMAL)  #DI_COMPAT | DI_IMAGE)

    h_bitmap_copy = user32.CopyImage(h_bitmap, IMAGE_BITMAP, bitmap_size, bitmap_size, 0 if is_8bit else LR_CREATEDIBSECTION)

    # Clean up
    gdi32.DeleteDC(hdc_dest)
    user32.ReleaseDC(None, hdc)
    gdi32.DeleteObject(h_bitmap)

#    hbitmap_fix_alpha(h_bitmap_copy)

    return h_bitmap_copy

########################################
#
########################################
def load_png_file(png_file, fix_alpha = False):
    png = PNG.from_file(png_file)
    pixels = pixels_from_data(png)
    if png.ihdr.bytes_per_pixel == 4:
        pixels[0::4], pixels[2::4] = pixels[2::4], pixels[0::4]  # RGBA => BGRA
    else:
        pixels[0::3], pixels[2::3] = pixels[2::3], pixels[0::3]  # RGB => BGR
    h_bitmap = bytes_to_hbitmap(bytes(pixels), 16, 16, png.ihdr.bytes_per_pixel)
    if fix_alpha and png.ihdr.bytes_per_pixel == 4:
        hbitmap_fix_alpha(h_bitmap)
    return h_bitmap

########################################
#
########################################
def load_png_data(png_data, fix_alpha = False):
    png = PNG.from_buffer(png_data)
    pixels = pixels_from_data(png)
    if png.ihdr.bytes_per_pixel == 4:
        pixels[0::4], pixels[2::4] = pixels[2::4], pixels[0::4]  # RGBA => BGRA
    else:
        pixels[0::3], pixels[2::3] = pixels[2::3], pixels[0::3]  # RGB => BGR
    h_bitmap = bytes_to_hbitmap(bytes(pixels), 16, 16, png.ihdr.bytes_per_pixel)
    if fix_alpha and png.ihdr.bytes_per_pixel == 4:
        hbitmap_fix_alpha(h_bitmap)
    return h_bitmap

########################################
#
########################################
#def hicon_to_hbitmap(h_icon, bitmap_size = 16, is_8bit = False):
#    icon_info = ICONINFO()
#    user32.GetIconInfo(h_icon, byref(icon_info))
#
##    GetIconInfo creates bitmaps for the hbmMask and hbmColor or members of ICONINFO.
##    The calling application must manage these bitmaps and delete them with
##    DeleteObject call when they are no longer necessary.
#
#    hdc = user32.GetDC(None)
#    h_bitmap = gdi32.CreateCompatibleBitmap(hdc, bitmap_size, bitmap_size)
##    h_bitmap = user32.CopyImage(h_bitmap, IMAGE_BITMAP, bitmap_size, bitmap_size, LR_CREATEDIBSECTION)
#
#    hdc_dest = gdi32.CreateCompatibleDC(hdc)
#    gdi32.SelectObject(hdc_dest, h_bitmap)
#
##    user32.FillRect(hdc_dest, byref(RECT(0, 0, bitmap_size, bitmap_size)), gdi32.CreateSolidBrush(0x000000))
#
##    bi = BITMAPINFO()
##    bi.bmiHeader.biSize        = sizeof(BITMAPINFOHEADER)
##    bi.bmiHeader.biWidth       = 1
##    bi.bmiHeader.biHeight      = 1
##    bi.bmiHeader.biPlanes      = 1
##    bi.bmiHeader.biBitCount    = 32
##    bi.bmiHeader.biCompression = BI_RGB
##
##    gdi32.StretchDIBits(
##        hdc_dest, 0, 0, bitmap_size, bitmap_size,
##        0, 0, 1, 1,
##        byref(RGBQUAD(0x00, 0x00, 0x00, 0x00)),
##        byref(bi),
##        DIB_RGB_COLORS,
##        SRCPAINT
##    )
#
#    hdc_src = gdi32.CreateCompatibleDC(hdc)
#    gdi32.SelectObject(hdc_src, icon_info.hbmColor)
#
#    gdi32.MaskBlt(hdc_dest, 0, 0, bitmap_size, bitmap_size, hdc_src, 0, 0, icon_info.hbmMask, 0, 0, DWORD(((SRCPAINT << 8) & 0xff000000) | MERGEPAINT))
#
#    gdi32.DeleteObject(icon_info.hbmColor)
#    gdi32.DeleteObject(icon_info.hbmMask)
#
#    gdi32.DeleteDC(hdc_dest)
#    gdi32.DeleteDC(hdc_src)
#
#    user32.ReleaseDC(None, hdc)
#
#    hbitmap_fix_alpha(h_bitmap)
#
#    return h_bitmap
#
#    h_bitmap_copy = user32.CopyImage(h_bitmap, IMAGE_BITMAP, bitmap_size, bitmap_size, LR_CREATEDIBSECTION)
#    gdi32.DeleteObject(h_bitmap)
#    return h_bitmap_copy

########################################
# This minimal code *only* works for 32-bit HBITMAPS with a width divisible by 4 (no padding)
########################################
def hbitmap_to_bmp(h_bitmap, width, height, bmp_file):
    data_size = width * height * 4

    bmi = BITMAPINFO()
    bmi.bmiHeader.biSize = sizeof(BITMAPINFOHEADER)
    bmi.bmiHeader.biWidth = width
    bmi.bmiHeader.biHeight = -height
    bmi.bmiHeader.biPlanes = 1
    bmi.bmiHeader.biBitCount = 32
    bmi.bmiHeader.biCompression = BI_RGB
    bmi.bmiHeader.biSizeImage = data_size

    hdc = gdi32.CreateCompatibleDC(None)
    gdi32.SelectObject(hdc, h_bitmap)
    bits = create_string_buffer(data_size)
    gdi32.GetDIBits(hdc, h_bitmap, 0, data_size, bits, byref(bmi), DIB_RGB_COLORS)
    gdi32.DeleteDC(hdc)

    with open(bmp_file, 'wb') as f:
        bmh = BMPHEADER()
        bmh.size = sizeof(BMPHEADER) + sizeof(BITMAPINFO) + data_size
        f.write(bytes(bmh))
        f.write(bytes(bmi))
        f.write(bits)
