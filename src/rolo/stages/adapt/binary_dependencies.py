from __future__ import annotations

import struct
from pathlib import Path
from typing import BinaryIO

MAX_LIBRARY_COUNT = 512
MAX_STRING_BYTES = 4096
MAX_FAT_SLICES = 8


def _read_at(stream: BinaryIO, offset: int, size: int) -> bytes:
    if offset < 0 or size < 0 or size > 4 * 1024 * 1024:
        raise ValueError("binary metadata read is outside bounded limits")
    stream.seek(offset)
    value = stream.read(size)
    if len(value) != size:
        raise ValueError("binary metadata is truncated")
    return value


def _cstring(stream: BinaryIO, offset: int) -> str:
    stream.seek(offset)
    value = stream.read(MAX_STRING_BYTES).split(b"\0", 1)[0]
    return value.decode("utf-8", errors="replace")


def _elf_dependencies(stream: BinaryIO) -> list[str]:
    header = _read_at(stream, 0, 64)
    elf_class = header[4]
    byte_order = "<" if header[5] == 1 else ">" if header[5] == 2 else None
    if elf_class not in {1, 2} or byte_order is None:
        raise ValueError("unsupported ELF class or byte order")
    if elf_class == 2:
        phoff = struct.unpack_from(byte_order + "Q", header, 32)[0]
        phentsize, phnum = struct.unpack_from(byte_order + "HH", header, 54)
        program_format = byte_order + "IIQQQQQQ"
        dynamic_format = byte_order + "qQ"
    else:
        phoff = struct.unpack_from(byte_order + "I", header, 28)[0]
        phentsize, phnum = struct.unpack_from(byte_order + "HH", header, 42)
        program_format = byte_order + "IIIIIIII"
        dynamic_format = byte_order + "iI"
    expected_size = struct.calcsize(program_format)
    if phnum > 4096 or phentsize < expected_size:
        raise ValueError("ELF program-header table exceeds limits")
    loads: list[tuple[int, int, int]] = []
    dynamic: tuple[int, int] | None = None
    for index in range(phnum):
        values = struct.unpack(
            program_format,
            _read_at(stream, phoff + index * phentsize, expected_size),
        )
        if elf_class == 2:
            kind, offset, virtual, file_size = values[0], values[2], values[3], values[5]
        else:
            kind, offset, virtual, file_size = values[0], values[1], values[2], values[4]
        if kind == 1:
            loads.append((virtual, virtual + file_size, offset))
        elif kind == 2:
            dynamic = (offset, file_size)
    if dynamic is None:
        return []
    entry_size = struct.calcsize(dynamic_format)
    if dynamic[1] // entry_size > 8192:
        raise ValueError("ELF dynamic table exceeds limits")
    needed: list[int] = []
    string_address: int | None = None
    for offset in range(dynamic[0], dynamic[0] + dynamic[1], entry_size):
        tag, value = struct.unpack(dynamic_format, _read_at(stream, offset, entry_size))
        if tag == 0:
            break
        if tag == 1 and len(needed) < MAX_LIBRARY_COUNT:
            needed.append(value)
        elif tag == 5:
            string_address = value
    if string_address is None:
        return []
    string_offset = next(
        (
            file_offset + string_address - start
            for start, end, file_offset in loads
            if start <= string_address < end
        ),
        None,
    )
    if string_offset is None:
        raise ValueError("ELF dynamic string table is not file-backed")
    return [name for value in needed if (name := _cstring(stream, string_offset + value))]


def _pe_dependencies(stream: BinaryIO) -> list[str]:
    dos = _read_at(stream, 0, 64)
    pe_offset = struct.unpack_from("<I", dos, 60)[0]
    signature = _read_at(stream, pe_offset, 24)
    if signature[:4] != b"PE\0\0":
        raise ValueError("invalid PE signature")
    section_count = struct.unpack_from("<H", signature, 6)[0]
    optional_size = struct.unpack_from("<H", signature, 20)[0]
    if section_count > 4096 or optional_size > 4096:
        raise ValueError("PE header exceeds limits")
    optional = _read_at(stream, pe_offset + 24, optional_size)
    magic = struct.unpack_from("<H", optional, 0)[0]
    data_directory = 112 if magic == 0x20B else 96 if magic == 0x10B else None
    if data_directory is None or len(optional) < data_directory + 16:
        raise ValueError("unsupported PE optional header")
    import_rva, import_size = struct.unpack_from("<II", optional, data_directory + 8)
    section_offset = pe_offset + 24 + optional_size
    sections: list[tuple[int, int, int]] = []
    for index in range(section_count):
        raw = _read_at(stream, section_offset + index * 40, 40)
        virtual_size, virtual_address, raw_size, raw_offset = struct.unpack_from(
            "<IIII", raw, 8
        )
        sections.append(
            (virtual_address, virtual_address + max(virtual_size, raw_size), raw_offset)
        )

    def rva_offset(rva: int) -> int:
        for start, end, file_offset in sections:
            if start <= rva < end:
                return file_offset + rva - start
        raise ValueError("PE RVA is not file-backed")

    if not import_rva or not import_size:
        return []
    table = rva_offset(import_rva)
    libraries: list[str] = []
    for index in range(min(MAX_LIBRARY_COUNT, import_size // 20 + 1)):
        descriptor = _read_at(stream, table + index * 20, 20)
        if descriptor == b"\0" * 20:
            break
        name_rva = struct.unpack_from("<I", descriptor, 12)[0]
        if name_rva and (name := _cstring(stream, rva_offset(name_rva))):
            libraries.append(name)
    return libraries


_MACHO_MAGICS = {
    b"\xce\xfa\xed\xfe": ("<", False),
    b"\xcf\xfa\xed\xfe": ("<", True),
    b"\xfe\xed\xfa\xce": (">", False),
    b"\xfe\xed\xfa\xcf": (">", True),
}
_DYLIB_COMMANDS = {0xC, 0x18, 0x1F, 0x23, 0x80000018, 0x8000001F, 0x80000023}


def _macho_dependencies(stream: BinaryIO, base: int = 0) -> list[str]:
    magic = _read_at(stream, base, 4)
    if magic in {b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca"}:
        byte_order = ">" if magic == b"\xca\xfe\xba\xbe" else "<"
        count = struct.unpack(byte_order + "I", _read_at(stream, base + 4, 4))[0]
        libraries: list[str] = []
        for index in range(min(count, MAX_FAT_SLICES)):
            architecture = _read_at(stream, base + 8 + index * 20, 20)
            offset = struct.unpack_from(byte_order + "I", architecture, 8)[0]
            libraries.extend(_macho_dependencies(stream, base + offset))
        return list(dict.fromkeys(libraries))
    if magic not in _MACHO_MAGICS:
        raise ValueError("unsupported Mach-O magic")
    byte_order, is_64 = _MACHO_MAGICS[magic]
    header_size = 32 if is_64 else 28
    header = _read_at(stream, base, header_size)
    command_count = struct.unpack_from(byte_order + "I", header, 16)[0]
    command_bytes = struct.unpack_from(byte_order + "I", header, 20)[0]
    if command_count > 8192 or command_bytes > 16 * 1024 * 1024:
        raise ValueError("Mach-O load-command table exceeds limits")
    offset = base + header_size
    libraries: list[str] = []
    for _ in range(command_count):
        command, size = struct.unpack(byte_order + "II", _read_at(stream, offset, 8))
        if size < 8 or size > command_bytes:
            raise ValueError("invalid Mach-O load command")
        if command in _DYLIB_COMMANDS and size >= 24:
            raw = _read_at(stream, offset, size)
            name_offset = struct.unpack_from(byte_order + "I", raw, 8)[0]
            if 0 < name_offset < size:
                name = raw[name_offset:].split(b"\0", 1)[0].decode(
                    "utf-8", errors="replace"
                )
                if name:
                    libraries.append(name)
        offset += size
    return libraries


def inspect_binary_dependencies(path: Path) -> dict[str, object]:
    """Read loader metadata without loading or executing the target binary."""
    try:
        with path.open("rb") as stream:
            magic = stream.read(4)
            stream.seek(0)
            if magic == b"\x7fELF":
                file_format = "ELF"
                libraries = _elf_dependencies(stream)
            elif magic[:2] == b"MZ":
                file_format = "PE"
                libraries = _pe_dependencies(stream)
            elif magic in _MACHO_MAGICS or magic in {
                b"\xca\xfe\xba\xbe",
                b"\xbe\xba\xfe\xca",
            }:
                file_format = "MACHO"
                libraries = _macho_dependencies(stream)
            else:
                return {"status": "NOT_APPLICABLE", "format": None, "libraries": []}
    except (OSError, ValueError, struct.error) as exc:
        return {
            "status": "PARTIAL",
            "format": None,
            "libraries": [],
            "limitations": [str(exc)],
        }
    return {
        "status": "COMPLETE",
        "format": file_format,
        "libraries": sorted(dict.fromkeys(libraries))[:MAX_LIBRARY_COUNT],
        "limitations": [],
    }
