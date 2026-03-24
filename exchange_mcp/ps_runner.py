"""Async PowerShell subprocess runner.

Provides run_ps() — the lowest-level building block for all PowerShell execution
in this project. Spawns powershell.exe, enforces timeouts, captures UTF-8 output,
and raises descriptive errors on non-zero exits.

JSON parsing is the caller's responsibility; this module returns raw strings.

Implementation notes
--------------------
* Scripts are delivered via ``-EncodedCommand`` (Base64-encoded UTF-16LE) rather
  than ``-Command`` to guarantee Unicode-safe argument passing on Windows.  Using
  ``-Command`` passes the script through the system code page (typically cp1252)
  which silently corrupts non-ASCII characters.
* ``run_ps()`` automatically prepends ``_PS_PREAMBLE`` to every script so that
  ``[Console]::OutputEncoding`` is always set to UTF-8 before any output is
  written.  Without this, PowerShell uses the system code page for stdout, which
  produces bytes that cannot be correctly decoded as UTF-8.
* ``proc.communicate()`` is used instead of ``proc.wait()`` to prevent pipe-buffer
  deadlock when stdout/stderr produce more than ~4 KB of output.
* After ``proc.kill()`` we always ``await proc.wait()`` to reap the zombie before
  re-raising ``TimeoutError``.
"""

import asyncio
import base64
from asyncio.subprocess import PIPE

# Prepended to every script to ensure consistent encoding and strict error mode.
# IMPORTANT: Without this preamble PowerShell uses the system code page (cp1252
# on Western Windows) for stdout, which corrupts non-ASCII characters.
_PS_PREAMBLE: str = (
    "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8\n"
    "$ErrorActionPreference = 'Stop'\n"
)

DEFAULT_TIMEOUT: int = 60


def _encode_command(script: str) -> str:
    """Encode *script* as Base64 UTF-16LE for ``powershell.exe -EncodedCommand``.

    PowerShell's ``-EncodedCommand`` flag expects a Base64-encoded UTF-16LE
    string.  This encoding sidesteps Windows code-page issues that corrupt
    non-ASCII characters when using ``-Command``.

    Args:
        script: The PowerShell script to encode.

    Returns:
        ASCII Base64 string suitable for the ``-EncodedCommand`` flag.
    """
    utf16le_bytes = script.encode("utf-16-le")
    return base64.b64encode(utf16le_bytes).decode("ascii")


async def run_ps(script: str, timeout: int = DEFAULT_TIMEOUT) -> str:
    """Spawn powershell.exe, run *script*, and return decoded stdout.

    The script is delivered via ``-EncodedCommand`` (Base64-encoded UTF-16LE)
    so that Unicode characters in the script body are preserved correctly on
    all Windows locales.

    The preamble (``_PS_PREAMBLE``) is automatically prepended to every script
    to ensure UTF-8 console encoding is set before any output is written.

    Args:
        script:  The PowerShell script body to execute.
        timeout: Maximum seconds to wait for the process to complete.
                 Defaults to DEFAULT_TIMEOUT (60 s).

    Returns:
        Stripped UTF-8 decoded stdout from the PowerShell process.

    Raises:
        TimeoutError:   The process did not complete within *timeout* seconds.
                        The subprocess is killed before this exception propagates.
        RuntimeError:   PowerShell exited with a non-zero return code.
                        The exception message contains the decoded stderr content.
    """
    full_script = _PS_PREAMBLE + script
    encoded = _encode_command(full_script)

    proc = await asyncio.create_subprocess_exec(
        "pwsh.exe",
        "-NonInteractive",
        "-NoProfile",
        "-EncodedCommand",
        encoded,
        stdout=PIPE,
        stderr=PIPE,
    )

    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            proc.communicate(),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        # Kill the subprocess and reap it before raising so we leave no zombies.
        proc.kill()
        await proc.wait()
        raise TimeoutError(
            f"PowerShell process did not complete within {timeout} second(s)."
        ) from None

    stdout = stdout_bytes.decode("utf-8", errors="replace")
    stderr = stderr_bytes.decode("utf-8", errors="replace")

    if proc.returncode != 0:
        raise RuntimeError(
            f"PowerShell exited with code {proc.returncode}. stderr:\n{stderr}"
        )

    return stdout.strip()


def build_script(body: str) -> str:
    """Prepend the standard preamble to *body* and return the combined script.

    The preamble sets UTF-8 console encoding and strict error handling
    (``$ErrorActionPreference = 'Stop'``).

    Note: ``run_ps()`` already prepends the preamble automatically.  ``build_script()``
    is provided for cases where callers need to inspect or log the full script
    before execution, or where the combined text is used outside ``run_ps()``.

    Args:
        body: Raw PowerShell script body.

    Returns:
        Full script string ready to pass to run_ps() or for inspection.
    """
    return _PS_PREAMBLE + body
