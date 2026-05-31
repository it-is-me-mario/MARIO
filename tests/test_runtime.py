import mario.compute.runtime as runtime


def test_physical_memory_bytes_prefers_windows_kernel_api_on_nt(monkeypatch):
    monkeypatch.setattr(runtime.os, "name", "nt", raising=False)
    monkeypatch.setattr(runtime, "_windows_physical_memory_bytes", lambda: 123456789)
    monkeypatch.setattr(runtime, "_sysconf_physical_memory_bytes", lambda: None)
    monkeypatch.setattr(runtime, "_proc_meminfo_physical_memory_bytes", lambda: None)

    assert runtime.physical_memory_bytes() == 123456789


def test_physical_memory_bytes_uses_sysconf_on_posix(monkeypatch):
    monkeypatch.setattr(runtime.os, "name", "posix", raising=False)
    monkeypatch.setattr(runtime, "_windows_physical_memory_bytes", lambda: None)
    monkeypatch.setattr(runtime, "_sysconf_physical_memory_bytes", lambda: 987654321)
    monkeypatch.setattr(runtime, "_proc_meminfo_physical_memory_bytes", lambda: None)

    assert runtime.physical_memory_bytes() == 987654321


def test_physical_memory_bytes_falls_back_to_proc_meminfo(monkeypatch):
    monkeypatch.setattr(runtime.os, "name", "posix", raising=False)
    monkeypatch.setattr(runtime, "_windows_physical_memory_bytes", lambda: None)
    monkeypatch.setattr(runtime, "_sysconf_physical_memory_bytes", lambda: None)
    monkeypatch.setattr(runtime, "_proc_meminfo_physical_memory_bytes", lambda: 555555555)

    assert runtime.physical_memory_bytes() == 555555555


def test_proc_meminfo_parser_reads_total_bytes(monkeypatch):
    meminfo = "MemTotal:       1024 kB\nMemFree:         128 kB\n"

    def _open(*args, **kwargs):
        from io import StringIO

        return StringIO(meminfo)

    monkeypatch.setattr("builtins.open", _open)

    assert runtime._proc_meminfo_physical_memory_bytes() == 1024 * 1024
