import struct
from pathlib import Path

from rolo.stages.adapt.binary_dependencies import inspect_binary_dependencies


def _write_elf64(path: Path) -> None:
    value = bytearray(0x400)
    value[:16] = b"\x7fELF\x02\x01\x01" + b"\0" * 9
    struct.pack_into("<H", value, 18, 62)
    struct.pack_into("<Q", value, 32, 64)
    struct.pack_into("<HHH", value, 52, 64, 56, 2)
    struct.pack_into("<IIQQQQQQ", value, 64, 1, 5, 0, 0x400000, 0, len(value), len(value), 0x1000)
    struct.pack_into(
        "<IIQQQQQQ", value, 120, 2, 4, 0x200, 0x400200, 0, 80, 80, 8
    )
    entries = [(1, 1), (1, 11), (5, 0x400300), (10, 21), (0, 0)]
    for index, entry in enumerate(entries):
        struct.pack_into("<qQ", value, 0x200 + index * 16, *entry)
    value[0x300 : 0x300 + 21] = b"\0libfoo.so\0libbar.so\0"
    path.write_bytes(value)


def _write_pe32(path: Path) -> None:
    value = bytearray(0x600)
    value[:2] = b"MZ"
    struct.pack_into("<I", value, 60, 0x80)
    value[0x80:0x84] = b"PE\0\0"
    struct.pack_into("<HHIIIHH", value, 0x84, 0x14C, 1, 0, 0, 0, 0xE0, 0)
    optional = 0x98
    struct.pack_into("<H", value, optional, 0x10B)
    struct.pack_into("<II", value, optional + 104, 0x1000, 40)
    section = 0x178
    value[section : section + 8] = b".rdata\0\0"
    struct.pack_into("<IIII", value, section + 8, 0x200, 0x1000, 0x200, 0x200)
    struct.pack_into("<IIIII", value, 0x200, 0, 0, 0, 0x1050, 0)
    value[0x250 : 0x25D] = b"KERNEL32.dll\0"
    path.write_bytes(value)


def _write_macho64(path: Path) -> None:
    value = bytearray(80)
    value[:4] = b"\xcf\xfa\xed\xfe"
    struct.pack_into("<IIIIIII", value, 4, 0x01000007, 3, 2, 1, 48, 0, 0)
    struct.pack_into("<IIIIII", value, 32, 0xC, 48, 24, 0, 0, 0)
    value[56 : 56 + 17] = b"/usr/lib/libz.dylib\0"
    path.write_bytes(value)


def test_static_elf_needed_dependencies(tmp_path: Path) -> None:
    binary = tmp_path / "robot"
    _write_elf64(binary)
    result = inspect_binary_dependencies(binary)
    assert result == {
        "status": "COMPLETE",
        "format": "ELF",
        "libraries": ["libbar.so", "libfoo.so"],
        "limitations": [],
    }


def test_static_pe_import_dependencies(tmp_path: Path) -> None:
    binary = tmp_path / "robot.exe"
    _write_pe32(binary)
    result = inspect_binary_dependencies(binary)
    assert result["status"] == "COMPLETE"
    assert result["format"] == "PE"
    assert result["libraries"] == ["KERNEL32.dll"]


def test_static_macho_dylib_dependencies(tmp_path: Path) -> None:
    binary = tmp_path / "robot"
    _write_macho64(binary)
    result = inspect_binary_dependencies(binary)
    assert result["status"] == "COMPLETE"
    assert result["format"] == "MACHO"
    assert result["libraries"] == ["/usr/lib/libz.dylib"]


def test_non_binary_is_not_applicable(tmp_path: Path) -> None:
    source = tmp_path / "README.md"
    source.write_text("robot", encoding="utf-8")
    assert inspect_binary_dependencies(source) == {
        "status": "NOT_APPLICABLE",
        "format": None,
        "libraries": [],
    }
