import const

from webview2.winapp.comtypes import *
from webview2.winapp.dlls import *
from webview2.winapp.const import *

DATADIR_GET = 1
DV_E_FORMATETC = 0x80040064

FD_FILESIZE = 0x00000040
FD_UNICODE = 0x80000000

DVTARGETDEVICE = LPVOID
IAdviseSink = LPVOID
IEnumSTATDATA = LPVOID

FMT_SHELLURL = user32.RegisterClipboardFormatW("UniformResourceLocator")
FMT_SHELLURLW = user32.RegisterClipboardFormatW("UniformResourceLocatorW")
FMT_FILEDESCRIPTORW = user32.RegisterClipboardFormatW("FileGroupDescriptorW")
FMT_FILECONTENTS = user32.RegisterClipboardFormatW("FileContents")
FMT_MOZURL = user32.RegisterClipboardFormatW('text/x-moz-url')

FMT_CUSTOM = user32.RegisterClipboardFormatW("SimpleData")

class CustomData(Structure):
    _fields_ = [
        ("cmd_id",              DWORD),
    ]

class FILEDESCRIPTORW(Structure):
    _fields_ = [
        ("dwFlags",             DWORD),
        ("clsid",               GUID),
        ("sizel",               SIZEL),
        ("pointl",              POINTL),
        ("dwFileAttributes",    DWORD),
        ("ftCreationTime",      FILETIME),
        ("ftLastAccessTime",    FILETIME),
        ("ftLastWriteTime",     FILETIME),
        ("nFileSizeHigh",       DWORD),
        ("nFileSizeLow",        DWORD),
        ("cFileName",           (WCHAR * MAX_PATH)),
    ]

class FILEGROUPDESCRIPTORW(Structure):
    _fields_ = [
        ("cItems",              UINT),
        ("fgd",                 (FILEDESCRIPTORW * 1)),
    ]

#class FILEDESCRIPTORA(Structure):
#    _fields_ = [
#        ("dwFlags",             DWORD),
#        ("clsid",               GUID),
#        ("sizel",               SIZEL),
#        ("pointl",              POINTL),
#        ("dwFileAttributes",    DWORD),
#        ("ftCreationTime",      FILETIME),
#        ("ftLastAccessTime",    FILETIME),
#        ("ftLastWriteTime",     FILETIME),
#        ("nFileSizeHigh",       DWORD),
#        ("nFileSizeLow",        DWORD),
#        ("cFileName",           (CHAR * MAX_PATH)),
#    ]
#
#class FILEGROUPDESCRIPTORA(Structure):
#    _fields_ = [
#        ("cItems",              UINT),
#        ("fgd",                 (FILEDESCRIPTORA * 1)),
#    ]

class FORMATETC(Structure):
    _fields_ = [
        ("cfFormat",            WORD),  # CLIPFORMAT
        ("ptd",                 POINTER(DVTARGETDEVICE)),
        ("dwAspect",            DWORD),
        ("lindex",              LONG),
        ("tymed",               DWORD),
    ]

class STGMEDIUM(Structure):
    _fields_ = [
        ("tymed",               DWORD),
        ("hGlobal",             HGLOBAL),  # actually UNION
        ("pUnkForRelease",      POINTER(IUnknown)),
    ]

class IEnumFORMATETC(IUnknown):
    _case_insensitive_ = True
    _iid_ = GUID('{00000103-0000-0000-C000-000000000046}')
    _idlflags_ = []

IEnumFORMATETC._methods_ = [
    COMMETHOD([], HRESULT, 'Next',
        ( ['in'], ULONG, 'celt' ),
        ( ['in'], POINTER(FORMATETC), 'rgelt' ),
        ( ['in'], POINTER(ULONG), 'pceltFetched' )),

    COMMETHOD([], HRESULT, 'Skip',
        ( ['in'], ULONG, 'celt' )),

    COMMETHOD([], HRESULT, 'Reset'),

    COMMETHOD([], HRESULT, 'Clone',
        ( ['out'], POINTER(POINTER(IEnumFORMATETC)), 'ppenum' )),
]

class IDataObject(IUnknown):
    _case_insensitive_ = True
    _iid_ = GUID('{0000010e-0000-0000-C000-000000000046}')
    _idlflags_ = []

IDataObject._methods_ = [
    COMMETHOD([], HRESULT, 'GetData',
        ( ['in'], POINTER(FORMATETC), 'pformatetcIn' ),
        ( ['out'], POINTER(STGMEDIUM), 'pmedium' )),

    COMMETHOD([], HRESULT, 'GetDataHere',
        ( ['in'], POINTER(FORMATETC), 'pformatetc' ),
        ( ['out', 'in'], POINTER(STGMEDIUM), 'pmedium' )),

    COMMETHOD([], HRESULT, 'QueryGetData',
        ( ['in'], POINTER(FORMATETC), 'pformatetc' )),

    COMMETHOD([], HRESULT, 'GetCanonicalFormatEtc',
        ( ['in'], POINTER(FORMATETC), 'pformatectIn' ),
        ( ['out'], POINTER(FORMATETC), 'pformatetcOut' )),

    COMMETHOD([], HRESULT, 'SetData',
        ( ['in'], POINTER(FORMATETC), 'pformatetc' ),
        ( ['in'], POINTER(STGMEDIUM), 'pmedium' ),
        ( ['in'], BOOL, 'fRelease' )),

    COMMETHOD([], HRESULT, 'EnumFormatEtc',
        ( ['in'], DWORD, 'dwDirection' ),
        ( ['out'], POINTER(POINTER(IEnumFORMATETC)), 'ppenumFormatEtc' )),

    COMMETHOD([], HRESULT, 'DAdvise',
        ( ['in'], POINTER(FORMATETC), 'pformatetc' ),
        ( ['in'], DWORD, 'advf' ),
        ( ['in'], POINTER(IAdviseSink), 'pAdvSink' ),
        ( ['out'], POINTER(DWORD), 'pdwConnection' )),

    COMMETHOD([], HRESULT, 'DUnadvise',
        ( ['in'], DWORD, 'dwConnection' )),

    COMMETHOD([], HRESULT, 'EnumDAdvise',
        ( ['out'], POINTER(POINTER(IEnumSTATDATA)), 'ppenumAdvise' )),
]

shell32.SHCreateStdEnumFmtEtc.argtypes = (UINT, POINTER(FORMATETC), LPVOID)
shell32.SHDoDragDrop.argtypes = (HWND, POINTER(IDataObject), LPVOID, DWORD, LPDWORD)


class DataObject(COMObject):
    _com_interfaces_ = [IDataObject]

    ########################################
    #
    ########################################
    def __init__(self, url = None, name = None, cmd_id = None):

        self._url = url
        self._name = name
        self._formats = [FMT_SHELLURL, FMT_SHELLURLW, CF_UNICODETEXT, FMT_FILEDESCRIPTORW, FMT_FILECONTENTS, FMT_MOZURL] if url else []

        if cmd_id is not None:
            self._cmd_id = cmd_id
            self._formats.append(FMT_CUSTOM)

        if self._formats:
            self._num_formats = len(self._formats)
            self._rgfe = (FORMATETC * self._num_formats)()
            for i, cf_format in enumerate(self._formats):
                self._rgfe[i].cfFormat = cf_format
                self._rgfe[i].tymed = TYMED_HGLOBAL
                self._rgfe[i].lindex = 0 if cf_format == FMT_FILECONTENTS else -1
                self._rgfe[i].dwAspect = DVASPECT_CONTENT

    ########################################
    #
    ########################################
    def EnumFormatEtc(self, this, dwDirection, ppefe):
        if dwDirection == DATADIR_GET:
            return shell32.SHCreateStdEnumFmtEtc(self._num_formats, self._rgfe, ppefe)

    ########################################
    #
    ########################################
    def QueryGetData(self, this, pfe):
        if pfe.contents.cfFormat in self._formats:
            return S_OK
        return S_FALSE

    ########################################
    #
    ########################################
    def GetData(self, this, pfe, pmed):
#        try:
        pfe = pfe.contents
        pmed = pmed.contents

        if pfe.cfFormat == FMT_CUSTOM:
            data = CustomData(self._cmd_id)
            pmed.tymed = TYMED_HGLOBAL
            pmed.hGlobal = kernel32.GlobalAlloc(GMEM_MOVEABLE | GMEM_ZEROINIT, sizeof(data))
            pcontents = kernel32.GlobalLock(pmed.hGlobal)
            memmove(pcontents, byref(data), sizeof(data))
            kernel32.GlobalUnlock(pmed.hGlobal)
            return S_OK

        elif pfe.cfFormat == FMT_MOZURL:
            data = f'{self._url}\n{self._name}'.encode('utf-16le')
            pmed.tymed = TYMED_HGLOBAL
            pmed.hGlobal = kernel32.GlobalAlloc(GMEM_MOVEABLE | GMEM_ZEROINIT, len(data) + 2)
            pcontents = kernel32.GlobalLock(pmed.hGlobal)
            memmove(pcontents, data, len(data))
            kernel32.GlobalUnlock(pmed.hGlobal)
            return S_OK

        elif pfe.cfFormat == FMT_SHELLURL:
            data = self._url.encode()
            pmed.tymed = TYMED_HGLOBAL
            pmed.hGlobal = kernel32.GlobalAlloc(GMEM_MOVEABLE | GMEM_ZEROINIT, len(data) + 1)
            pcontents = kernel32.GlobalLock(pmed.hGlobal)
            memmove(pcontents, data, len(data))
            kernel32.GlobalUnlock(pmed.hGlobal)
            return S_OK

        elif pfe.cfFormat == FMT_SHELLURLW:
            data = self._url.encode('utf-16le')
            pmed.tymed = TYMED_HGLOBAL
            pmed.hGlobal = kernel32.GlobalAlloc(GMEM_MOVEABLE | GMEM_ZEROINIT, len(data) + 2)
            pcontents = kernel32.GlobalLock(pmed.hGlobal)
            memmove(pcontents, data, len(data))
            kernel32.GlobalUnlock(pmed.hGlobal)
            return S_OK

        elif pfe.cfFormat == CF_UNICODETEXT:
            data = self._url.encode('utf-16le')
            pmed.tymed = TYMED_HGLOBAL
            pmed.hGlobal = kernel32.GlobalAlloc(GMEM_MOVEABLE | GMEM_ZEROINIT, len(data) + 2)
            pcontents = kernel32.GlobalLock(pmed.hGlobal)
            memmove(pcontents, data, len(data))
            kernel32.GlobalUnlock(pmed.hGlobal)
            return S_OK

        elif pfe.cfFormat == FMT_FILEDESCRIPTORW:
            fgd = FILEGROUPDESCRIPTORW()
            fgd.cItems = 1
            fgd.fgd[0].cFileName = self._name + '.url'
            fgd.fgd[0].nFileSizeLow = len(f'[InternetShortcut]\r\nURL={self._url}\r\n')
            fgd.fgd[0].dwFlags = FD_FILESIZE | FD_UNICODE
            pmed.tymed = TYMED_HGLOBAL
            pmed.hGlobal = kernel32.GlobalAlloc(GMEM_MOVEABLE | GMEM_ZEROINIT, sizeof(fgd))
            pcontents = kernel32.GlobalLock(pmed.hGlobal)
            memmove(pcontents, byref(fgd), sizeof(fgd))
            kernel32.GlobalUnlock(pmed.hGlobal)
            return S_OK

        elif pfe.cfFormat == FMT_FILECONTENTS:
            data = f'[InternetShortcut]\r\nURL={self._url}\r\n'.encode()
            pmed.tymed = TYMED_HGLOBAL
            pmed.hGlobal = kernel32.GlobalAlloc(GMEM_MOVEABLE | GMEM_ZEROINIT, len(data))
            pcontents = kernel32.GlobalLock(pmed.hGlobal)
            memmove(pcontents, data, len(data))
            kernel32.GlobalUnlock(pmed.hGlobal)
            return S_OK

        return DV_E_FORMATETC


########################################
#
########################################
def drop_url(url = None, filename = None, cmd_id = None):
    shell32.SHDoDragDrop(None, DataObject(url, filename, cmd_id), None, DROPEFFECT_COPY, byref(DWORD()))

########################################
#
########################################
def parse_url_file(filename):
    with open(filename, 'r') as f:
        lines = f.readlines()
    for line in lines[1:]:
        if line.startswith('URL='):
            return line[4:].rstrip()
