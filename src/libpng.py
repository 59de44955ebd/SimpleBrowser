"""
A minimal PNG parser that we only use to load PNG data from Chrome's
SQLite database 'Favicons' and convert it to HBITMAP.

Since we are only dealing with small 16x16 icons, using a pure Python
parser should be fine, no need to import a large module like Pillow.
"""
import struct

import zlib
#from zlib import crc32
#from enum import IntEnum
from itertools import cycle
from collections import deque  #, Counter

#CRITICAL_CHUNK_TYPES = [b'IHDR', b'PLTE', b'IDAT', b'IEND']

class StreamReader:
    def __init__(self, data):
        self._data = data
        self.pointer = 0

    def read(self, size):
        rho = self._data[self.pointer:self.pointer + size]
        self.pointer += size
        return rho

    def read1(self):
        rho = self._data[self.pointer]
        self.pointer += 1
        return rho

    def readall(self):
        rho = self._data[self.pointer:]
        self.pointer = len(self._data)
        return rho

    def __len__(self):
        return len(self._data) - self.pointer

    def is_empty(self):
        return len(self) <= 0


class Chunk():
    @classmethod
    def from_stream(cls, reader: StreamReader):
        """read a single chunk from the head of the buffer"""
        new = cls()
        length = struct.unpack(">I", reader.read(4))[0]
        new.type = reader.read(4)
        new.body = reader.read(length)
        new.crc = struct.unpack(">I", reader.read(4))[0]
        new.valid = True  #new.crc == crc32(new.type+new.body)
        return new

    @classmethod
    def from_buffer(cls, buf):
        return Chunk.from_stream(StreamReader(buf))

    @classmethod
    def create(cls, ctype, body):
        new = cls()
        new.type = ctype
        new.body = body
        new.crc = 0 #crc32(new.type+new.body)
        new.valid = True
        return new

    def total(self):
        """return length including type-, length- and checksum fields"""
        return len(self.body)+12

    def __repr__(self):
        return "Chunk[{}]:{}".format(self.type.decode('ascii'), len(self.body))


IEND = Chunk.create(b'IEND', b'')

def parse_chunks(data):
    """parse bytes to list of Chunks"""
    i = 0
    chunks = []
    s = StreamReader(data)
    while not s.is_empty():
        try:
            c = Chunk.from_stream(s)
#            if not c.valid:
#                print(f"WARNING: chunk {len(chunks)} checksum failed")
#            if c.type[0]&(1<<5) == 0:
#                if not c.type in CRITICAL_CHUNK_TYPES:
#                    print(f"ERROR: chunk {i} of type {c.type} cannot be interpreted")
        except struct.error:
            print("WARNING: Orphan data")
            return chunks, s.readall()
        chunks.append(c)
        if c.type == b'IEND':
            if not s.is_empty():
                print("WARNING: Orphan data after IEND chunk")
                return chunks, s.readall()

    return chunks, None

def bits_to_bytes(x):
    return (x >> 3) + ((x & 7) > 0)

_bits_per_pixel = {}
_bits_per_pixel[0] = {1:1, 2:2, 4:4, 8:8, 16:16}
_bits_per_pixel[2] = {8:24, 16:48}
_bits_per_pixel[3] = {1:1, 2:2, 4:4, 8:8}
_bits_per_pixel[4] = {8:16, 16:32}
_bits_per_pixel[6] = {8:32, 16:64}

class ColorType():
    GRAYSCALE = 0
    RGB = 2
    PALETTE = 3
    GRAYSCALE_ALPHA = 4
    RGBA = 6


class IHDR():
    @classmethod
    def create(cls, width, height, bitdepth, colortype, compression=0, filtermethod=0, interlace=0):
        new = cls()
        new.width = width
        new.height = height
        new.bitdepth = bitdepth
        new.colortype = colortype
        new.compression = compression
        new.filtermethod = filtermethod
        new.interlace = interlace
#        assert new.colortype in set([0, 2, 3, 4, 6]), "ERROR: {} is not a valid colortype".format(new.colortype)
#        if new.colortype == 0:
#            assert new.bitdepth in set([1,2,4,8,16]), "ERROR: {} is not a valid bitdepth for colortype {}".format(new.bitdepth, ColorType(new.colortype).name)
#        elif new.colortype == 2:
#            assert new.bitdepth in set([8,16]), "ERROR: {} is not a valid bitdepth for colortype {}".format(new.bitdepth, ColorType(new.colortype).name)
#        elif new.colortype == 3:
#            assert new.bitdepth in set([1,2,4,8]), "ERROR: {} is not a valid bitdepth for colortype {}".format(new.bitdepth, ColorType(new.colortype).name)
#        elif new.colortype == 4:
#            assert new.bitdepth in set([8,16]), "ERROR: {} is not a valid bitdepth for colortype {}".format(new.bitdepth, ColorType(new.colortype).name)
#        elif new.colortype == 6:
#            assert new.bitdepth in set([8,16]), "ERROR: {} is not a valid bitdepth for colortype {}".format(new.bitdepth, ColorType(new.colortype).name)
#        assert new.compression==0, "ERROR: {} is not a valid compression type".format(new.compression)
#        assert new.filtermethod==0, "ERROR: {} is not a valid filter method".format(new.filtermethod)
#        assert new.interlace in set([0, 1]), "ERROR: {} is not a valid interlace method".format(new.interlace)
        new.bytes_per_pixel = bits_to_bytes(_bits_per_pixel[new.colortype][new.bitdepth])
        new.width_bytes = bits_to_bytes(new.width * _bits_per_pixel[new.colortype][new.bitdepth])
        return new

    @classmethod
    def from_reader(cls, reader: StreamReader):
        length, expected = len(reader), struct.calcsize(">IIBBBBB")
        if length > expected:
            print(f"WARNING: IHDR too large? (found: {length}, expected: {expected})")
            raise ValueError
        elif length < expected:
            print(f"ERROR: IHDR too small? (found: {length}, expected: {expected})")
            raise ValueError
        width, height, bitdepth, colortype, compression, filtermethod, interlace = struct.unpack(">IIBBBBB", reader.readall())
        new = cls.create(width, height, bitdepth, colortype, compression, filtermethod, interlace)
        return new

    @classmethod
    def from_buffer(cls, buf):
        return IHDR.from_reader(StreamReader(buf))

    def __repr__(self):
        data = [("width", self.width), ("height", self.height), ("bitdepth", self.bitdepth), ("colortype", ColorType(self.colortype).name), ("compression", self.compression), ("filtermethod", self.filtermethod), ("interlace", ["false", "adam7"][self.interlace])]
        return '\n'.join("{} : {}".format(y, x) for x, y in data)

    def to_chunk(self):
        return Chunk.create(b'IHDR',
            struct.pack(">IIBBBBB", self.width, self.height, self.bitdepth, self.colortype, self.compression, self.filtermethod, self.interlace)
        )


class InterlaceMethod():
    NULL_METHOD = 0
    ADAM7 = 1

PASS_WIDTH = [1, 1, 2, 2, 4, 4, 8]
PASS_HEIGHT = [1, 1, 1, 2, 2, 4, 4]

def get_scanlines(img):
    data = StreamReader(img.data)
    if img.ihdr.interlace == InterlaceMethod.NULL_METHOD:
        for _ in range(img.ihdr.height):
            filter_byte = data.read1()
            scanline = data.read(img.ihdr.width_bytes)
            yield filter_byte, scanline
    elif img.ihdr.interlace == InterlaceMethod.ADAM7:
        counter = 0
        for pass_height, pass_width in zip(PASS_HEIGHT, PASS_WIDTH):
            for y0 in range(0, img.ihdr.height, 8):
                for y1 in range(pass_height):
                    filter_byte = data.read1()
                    scanline = data.read(pass_width * img.ihdr.bytes_per_pixel * (img.ihdr.width // 8))
                    yield filter_byte, scanline
                    counter += 1
#                    print(f"{counter=}, {y0=}, {y1=}")

def decompress(data):
    D = zlib.decompressobj()
    data = D.decompress(data)
    return data, D.unused_data

class FilterType():
    NONE = 0
    SUB = 1
    UP = 2
    AVG = 3
    PAETH = 4

def undo_sub(scanline, bytes_per_pixel):
    old = deque([0] * bytes_per_pixel)
    out = []
    for b in scanline:
        new = (b + old.pop()) & 0xff
        out.append(new)
        old.appendleft(new)
    return bytes(out)

def undo_up(scanline, prev):
    return bytes((x + b) & 0xff for x, b in zip(scanline, prev))

def undo_avg(scanline, prev, bytes_per_pixel):
    if scanline is None:
        print("scanline was none")
        raise ValueError
    if prev is None:
        prev = cycle([0])
    out = []
    old = deque([0] * bytes_per_pixel)
    for x, b in zip(scanline, prev):
        new = (x + (b + old.pop()) // 2) & 0xff
        out.append(new)
        old.appendleft(new)
    return bytes(out)

def undo_paeth(scanline, prev, bytes_per_pixel):
    out = []
    old = deque([0] * bytes_per_pixel)
    old_up = deque([0] * bytes_per_pixel)
    for x, b in zip(scanline, prev):
        a = old.pop()
        c = old_up.pop()
        p = a + b - c
        pa = abs(p - a)
        pb = abs(p - b)
        pc = abs(p - c)
        if pa <= pb and pa <= pc:
            rho = a
        elif pb <= pc:
            rho = b
        else:
            rho = c
        new = (x + rho) & 0xff
        out.append(new)
        old.appendleft(new)
        old_up.appendleft(b)
    return bytes(out)

def undo_filter(img):
    previous = None
    for i, (filter_byte, scanline) in enumerate(get_scanlines(img)):
        if previous is None:
            previous = [0] * len(scanline)
        if filter_byte == FilterType.NONE:
            rho = scanline
        elif filter_byte == FilterType.SUB:
            rho = undo_sub(scanline, img.ihdr.bytes_per_pixel)
        elif filter_byte == FilterType.UP:
            rho = undo_up(scanline, previous)
        elif filter_byte == FilterType.AVG:
            rho = undo_avg(scanline, previous, img.ihdr.bytes_per_pixel)
        elif filter_byte == FilterType.PAETH:
            rho = undo_paeth(scanline, previous, img.ihdr.bytes_per_pixel)
        else:
            raise ValueError(f"invalid filter method {filter_byte}")
        yield rho
        previous = rho

def tuple_coords(y, x, width):
    assert x < width
    return y * width + x

PASS_OFFSETS = [
    [[0,], [0,]],
    [[0,], [4,]],
    [[4,], [0, 4]],
    [[0, 4], [2, 6]],
    [[2, 6], [0, 2, 4, 6]],
    [[0, 2, 4, 6], [1, 3, 5, 7]],
    [[1, 3, 5, 7], [0, 1, 2, 3, 4, 5, 6, 7]]
]

def div_ceil(a, b):
    q, r = divmod(a, b)
    return q + (r > 0)

def pixels_from_data(img):
    pixels = bytearray(img.ihdr.width * img.ihdr.height * img.ihdr.bytes_per_pixel)

    if img.ihdr.interlace == InterlaceMethod.NULL_METHOD:
        for y, scanline in enumerate(undo_filter(img)):
            offset = y * img.ihdr.width_bytes
            pixels[offset:offset + img.ihdr.width_bytes] = scanline

    elif img.ihdr.interlace == InterlaceMethod.ADAM7:
        scanlines = undo_filter(img)
        counter = 0
        pass_count = 0
        debug = [0] * img.ihdr.height * img.ihdr.width_bytes
        for pass_height_offsets, pass_width_offsets in PASS_OFFSETS:
            pass_count += 1
            for y in range(0, img.ihdr.height, 8):
                for y_offset in pass_height_offsets:
                    scanline = iter(next(scanlines))
                    counter += 1
                    byte_per_scanline = 0
                    for x in range(0, img.ihdr.width, 8):
                        for x_offset in pass_width_offsets:
                            for channel in range(img.ihdr.bytes_per_pixel):
                                try:
                                    index = tuple_coords(y + y_offset, (x + x_offset) * img.ihdr.bytes_per_pixel + channel, img.ihdr.width_bytes)
                                    byte_per_scanline += 1
                                    debug[index] += 1
                                    pixels[index] = next(scanline)
                                except IndexError:
                                    print("THERE WAS AN ERROR")
                                    break
                                except StopIteration:
                                    print(f"at pass {pass_count} shit broke, tried fetching byte {byte_per_scanline}")
                                    exit(1)
                    if (rem:=len(list(scanline))) > 0:
                        print(f"there were {rem} bytes left over")
                        exit(1)
        print(f"there were {len(list(scanlines))} scanlines left over")
        print(Counter(debug).most_common(3))

    return pixels


class PNG():
    MAGIC = b"\x89\x50\x4e\x47\x0d\x0a\x1a\x0a"

    def get_chunks_by_type(self, ctype):
        return [chunk for chunk in self.chunks if chunk.type == ctype]

    @classmethod
    def from_chunks(cls, chunks, ihdr=None, orphan=None, just_header=False):
        new = cls()
        new.chunks = chunks
        if not orphan is None:
            new.orphan = orphan
        if ihdr is None:
            try:
                ihdr, *_ = new.get_chunks_by_type(b'IHDR')
            except ValueError:
                print("ERROR: Please supply a IHDR chunk")
            if len(_) > 0:
                print("WARNING: Multiple IHDR chunks found, used first")
            new.ihdr = IHDR.from_buffer(ihdr.body)
        else:
            new.ihdr = ihdr
            new.chunks = [ihdr.to_chunk()] + chunks
            if len(new.get_chunks_by_type(b'IHDR')) > 1:
                print("WARNING: Multiple IHDR chunks found, used the selected one")
        iend_chunks = new.get_chunks_by_type(b'IEND')
        if len(iend_chunks) == 0:
            print("INFO: autogenerated IEND chunk")
            new.chunks.append(IEND)
        elif len(iend_chunks) > 1:
            print(f"ERROR: there must be exactly one IEND chunk, but found {len(iend_chunks)}")
        elif len(iend_chunks[0].body) > 0:
            print(f"ERROR: IEND chunk must be empty, found {len(iend_chunks[0].body)} bytes")

        try:
            new.data, unused = decompress(b''.join(c.body for c in new.get_chunks_by_type(b'IDAT')))
            if unused:
                new.unused = unused
                print(f"INFO: unused {len(unused)} bytes of data in IDAT")

            if new.ihdr.interlace == InterlaceMethod.NULL_METHOD:
                actual_dim, supposed_dim = len(new.data), new.ihdr.width * new.ihdr.height * new.ihdr.bytes_per_pixel + new.ihdr.height

#                if actual_dim > supposed_dim:
#                    print("WARNING: too many pixels")
#                    print("expected:\n\t{}x{}x{} = {}".format(new.ihdr.width, new.ihdr.height, new.ihdr.bytes_per_pixel, supposed_dim))
#                    print("found:\n\t{}".format(actual_dim))
#                elif actual_dim < supposed_dim:
#                    print("ERROR: too few pixels")
#                    print("expected:\n\t{}x{}x{} = {}".format(new.ihdr.width, new.ihdr.height, new.ihdr.bytes_per_pixel, supposed_dim))
#                    print("found:\n\t{}".format(actual_dim))
#                    new.data += (supposed_dim - actual_dim) * b'\x00'

        except zlib.error as e:
            print("ERROR: zlib.decompress failed")
            print(e)
            return new

#        if just_header:
#            return new
#        elif new.ihdr.bitdepth != 8:
#            print("WARNING: bit depths that are different from 8 are not really supported")
#            return new

        new.pixels = pixels_from_data(new)
        try:
            new.pixels = pixels_from_data(new)
        except Exception as e:
            print("from_chunks", e)
        return new

    @classmethod
    def from_buffer(cls, buf, just_header=False):
        """interpret content of buffer as PNG image"""
        assert len(cls.MAGIC) + 12 < len(buf), "ERROR: buffer too short"
        if buf[:len(cls.MAGIC)] != cls.MAGIC:
            print("ERROR: magic bytes mismatched")

        orphan = None
        chunks, orphan = parse_chunks(buf[len(cls.MAGIC):])

        if chunks[0].type != b'IHDR':
            print("ERROR: first chunk must be of type IHDR, {} type chunk found".format(chunks[0].type))
            print(chunks)
        count = sum(chunk.type == b'IHDR' for chunk in chunks)
        if count > 1:
            print("ERROR: there must be exactly 1 IHDR chunk, found {}".format(count))
        if chunks[-1].type != b'IEND':
             print("ERROR: last chunk must be of type IEND, {} type chunk found".format(chunks[-1].type))
        count = sum(chunk.type == b'IEND' for chunk in chunks)
        if count != 1:
            print("ERROR: there must be exactly 1 IEND chunk, found {}".format(count))

        return cls.from_chunks(chunks, orphan = orphan, just_header=just_header)

    @classmethod
    def from_file(cls, name, just_header=False):
        """read file as a PNG image"""
        with open(name, "rb") as f:
            return cls.from_buffer(f.read(), just_header)
