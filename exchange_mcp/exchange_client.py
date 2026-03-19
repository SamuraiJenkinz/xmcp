"""Exchange Online client with interactive or certificate-based authentication.

Wraps the async PowerShell subprocess runner (ps_runner) with Exchange Online-
specific concerns:

* Interactive auth (default) or certificate-based Azure AD authentication (CBA)
* Per-call Connect/Disconnect lifecycle inside a try/finally block
* ConvertTo-Json -Depth 10 enforcement to prevent object truncation
* Retry logic with exponential backoff for transient failures
* Health-check endpoint via verify_connection()

Auth mode is auto-detected:
  - If AZURE_CERT_THUMBPRINT env var is set → CBA (unattended)
  - Otherwise → interactive (browser popup for login)

All Exchange-facing MCP tools in Phases 3-6 call this module — not ps_runner
directly.  This layer owns the PowerShell script template and the JSON
serialisation contract.

Design decisions
----------------
* run_cmdlet() returns raw Python objects (dicts/lists) parsed from JSON.
* Exceptions raised: RuntimeError (PS error or Exchange error), TimeoutError,
  json.JSONDecodeError.
* Auth errors and invalid-input errors are non-retryable — raising immediately
  avoids wasting quota and making the caller wait.
* Transient errors (throttling, network, connection reset) retry up to
  max_retries times with 2**attempt seconds backoff.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

from exchange_mcp import ps_runner

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# PowerShell script fragments
# ---------------------------------------------------------------------------

# Interactive auth — opens browser for login. Works on Windows desktop.
_PS_CONNECT_INTERACTIVE: str = """\
Import-Module ExchangeOnlineManagement -ErrorAction Stop
Connect-ExchangeOnline `
    -ShowBanner:$false `
    -SkipLoadingFormatData"""

# Certificate-based auth (CBA) — env vars are read by PowerShell at runtime.
# Used when AZURE_CERT_THUMBPRINT env var is set.
_PS_CONNECT_CBA: str = """\
Import-Module ExchangeOnlineManagement -ErrorAction Stop
Connect-ExchangeOnline `
    -CertificateThumbPrint $env:AZURE_CERT_THUMBPRINT `
    -AppID $env:AZURE_CLIENT_ID `
    -Organization $env:AZURE_TENANT_DOMAIN `
    -ShowBanner:$false `
    -SkipLoadingFormatData"""

# Always executed in the finally block to ensure the session is cleaned up
# even if the cmdlet raises an error.
_PS_DISCONNECT: str = (
    "Disconnect-ExchangeOnline -Confirm:$false -ErrorAction SilentlyContinue"
)

# ---------------------------------------------------------------------------
# Error classification
# ---------------------------------------------------------------------------

# Fragments that indicate the error is NOT transient and should NOT be
# retried.  These strings are tested case-insensitively.
_NON_RETRYABLE_PATTERNS: tuple[str, ...] = (
    # Auth failures
    "authentication failed",
    "access denied",
    "unauthorized",
    "invalid client",
    "invalid_client",
    "aadsts",                     # Azure AD error codes
    "certificate",                # CBA cert problems
    "appid",                      # Wrong App ID
    # Input / logic errors
    "couldn't find the object",
    "could not find the object",
    "object not found",
    "invalid input",
    "parameter cannot be",
    "cannot bind",
    "is not a recognized",
    "not recognized",
    "property '*' cannot",
    "ambiguous parameter",
)


def _is_retryable(error_message: str) -> bool:
    """Return True if *error_message* indicates a transient failure.

    Non-retryable errors (auth failures, invalid input) return False so the
    caller can raise immediately without burning retry quota.

    Args:
        error_message: The string error message to classify.

    Returns:
        True for transient failures that should be retried.
        False for auth or input errors that will not succeed on retry.
    """
    lower = error_message.lower()
    for pattern in _NON_RETRYABLE_PATTERNS:
        if pattern in lower:
            return False
    return True


# ---------------------------------------------------------------------------
# ExchangeClient
# ---------------------------------------------------------------------------


class ExchangeClient:
    """High-level client for Exchange Online via PowerShell.

    Auth mode is auto-detected:
      - If AZURE_CERT_THUMBPRINT is set → certificate-based auth (CBA)
      - Otherwise → interactive auth (browser popup)

    Every public method is a coroutine — callers must ``await`` them.

    Attributes:
        timeout:            Per-cmdlet PowerShell timeout in seconds.
        max_retries:        Maximum retry attempts for transient errors.
        default_result_size: Default -ResultSize argument passed by tools.
        auth_mode:          "interactive" or "certificate" (auto-detected).
    """

    def __init__(
        self,
        timeout: int = 60,
        max_retries: int = 3,
        default_result_size: int = 100,
    ) -> None:
        """Initialise the client, auto-detect auth mode.

        Args:
            timeout:             Max seconds to wait for a cmdlet to finish.
            max_retries:         Max retry attempts on transient errors.
            default_result_size: Suggested -ResultSize for listing cmdlets.

        Raises:
            EnvironmentError: If certificate auth is detected (AZURE_CERT_THUMBPRINT
                              set) but other required cert env vars are missing.
        """
        self.timeout = timeout
        self.max_retries = max_retries
        self.default_result_size = default_result_size

        # Auto-detect auth mode
        if os.environ.get("AZURE_CERT_THUMBPRINT"):
            self.auth_mode = "certificate"
            self._verify_env()
            logger.info("ExchangeClient using certificate-based auth (CBA)")
        else:
            self.auth_mode = "interactive"
            logger.info("ExchangeClient using interactive auth (browser popup)")

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _verify_env(self) -> None:
        """Raise EnvironmentError if any required env var is missing/empty.

        Checks:
            AZURE_CERT_THUMBPRINT — certificate thumbprint for CBA
            AZURE_CLIENT_ID       — Azure AD application (client) ID
            AZURE_TENANT_DOMAIN   — tenant domain, e.g. contoso.onmicrosoft.com

        Raises:
            EnvironmentError: With a message listing all missing variable
                              names so the operator can fix them in one pass.
        """
        required = [
            "AZURE_CERT_THUMBPRINT",
            "AZURE_CLIENT_ID",
            "AZURE_TENANT_DOMAIN",
        ]
        missing = [var for var in required if not os.environ.get(var)]
        if missing:
            raise EnvironmentError(
                "ExchangeClient requires the following environment variables to be set "
                f"and non-empty: {', '.join(missing)}"
            )

    def _build_cmdlet_script(self, cmdlet_line: str) -> str:
        """Return a complete PowerShell script that connects, runs, and disconnects.

        The script structure is:
            1. Connect-ExchangeOnline (interactive or CBA depending on auth_mode)
            2. Execute *cmdlet_line* and capture output as JSON
            3. Always disconnect in the finally block

        The script uses ``ConvertTo-Json -Depth 10`` to prevent truncation of
        nested objects (Exchange frequently returns objects with 4-6 levels of
        nesting).

        Note: ``ps_runner.run_ps()`` automatically prepends the preamble
        (UTF-8 encoding + $ErrorActionPreference = 'Stop') so we do NOT call
        ``build_script()`` here — doing so would duplicate the preamble.

        Args:
            cmdlet_line: A single PowerShell cmdlet expression (no semicolons).
                         Example: ``Get-Mailbox -Identity user@contoso.com``

        Returns:
            Complete PowerShell script body ready for ``ps_runner.run_ps()``.
        """
        connect = _PS_CONNECT_CBA if self.auth_mode == "certificate" else _PS_CONNECT_INTERACTIVE
        body = f"""\
try {{
    {connect}
    $result = {cmdlet_line} | ConvertTo-Json -Depth 10
    Write-Output $result
}}
catch {{
    $errorObj = @{{ error = $_.Exception.Message; type = $_.Exception.GetType().FullName }}
    Write-Output ($errorObj | ConvertTo-Json)
    exit 1
}}
finally {{
    {_PS_DISCONNECT}
}}"""
        return body

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run_cmdlet(self, cmdlet_line: str) -> Any:
        """Execute a single Exchange Online cmdlet and return parsed JSON.

        Builds the full PowerShell script (connect → execute → disconnect),
        runs it via ps_runner, parses the JSON output, and raises if the
        script reported an error.

        Args:
            cmdlet_line: A PowerShell cmdlet expression.
                         Example: ``Get-Mailbox -Identity user@contoso.com``

        Returns:
            Parsed JSON result — dict, list, or scalar depending on cmdlet.

        Raises:
            TimeoutError:         PowerShell did not finish within ``timeout``.
            RuntimeError:         PowerShell exited non-zero OR the cmdlet
                                  returned an ``{"error": ...}`` payload.
            json.JSONDecodeError: The script output was not valid JSON.
        """
        script = self._build_cmdlet_script(cmdlet_line)
        # run_ps() raises TimeoutError or RuntimeError on failure; let these
        # propagate unchanged so the retry layer can inspect them.
        raw = await ps_runner.run_ps(script, timeout=self.timeout)

        if not raw:
            # Empty output — some cmdlets legitimately return nothing (e.g.
            # when a filter matches no objects).  Return empty list to be safe.
            return []

        parsed = json.loads(raw)

        # The catch block in the PS script writes {"error": "...", "type": "..."}
        # and then calls ``exit 1``, so run_ps() will have already raised
        # RuntimeError.  This branch is a defence-in-depth guard for the
        # unlikely case where exit 1 is swallowed.
        if isinstance(parsed, dict) and "error" in parsed:
            raise RuntimeError(parsed["error"])

        return parsed

    async def run_cmdlet_with_retry(self, cmdlet_line: str) -> Any:
        """Execute a cmdlet with exponential-backoff retry on transient errors.

        Retry policy:
            * ``TimeoutError``: always retry (transient network condition)
            * ``RuntimeError`` matching ``_NON_RETRYABLE_PATTERNS``: raise
              immediately — retrying auth/input errors wastes quota.
            * ``RuntimeError`` NOT matching non-retryable patterns: retry
              (assume connection reset, throttling, etc.)

        The backoff delay between attempts is ``2 ** attempt`` seconds
        (1 s, 2 s, 4 s for attempts 0, 1, 2).

        Args:
            cmdlet_line: A PowerShell cmdlet expression.

        Returns:
            Parsed JSON result from the first successful attempt.

        Raises:
            TimeoutError or RuntimeError from the final attempt when all
            retries are exhausted.
        """
        last_exc: Exception | None = None

        for attempt in range(self.max_retries):
            try:
                return await self.run_cmdlet(cmdlet_line)
            except TimeoutError as exc:
                last_exc = exc
                wait = 2 ** attempt
                logger.warning(
                    "Cmdlet timed out (attempt %d/%d). Retrying in %ds. cmdlet=%r",
                    attempt + 1,
                    self.max_retries,
                    wait,
                    cmdlet_line,
                )
                await asyncio.sleep(wait)
            except RuntimeError as exc:
                if not _is_retryable(str(exc)):
                    # Non-retryable — raise immediately without logging retry.
                    logger.error(
                        "Non-retryable error from Exchange (attempt %d/%d): %s",
                        attempt + 1,
                        self.max_retries,
                        exc,
                    )
                    raise
                last_exc = exc
                wait = 2 ** attempt
                logger.warning(
                    "Transient error (attempt %d/%d). Retrying in %ds. error=%r",
                    attempt + 1,
                    self.max_retries,
                    wait,
                    str(exc),
                )
                await asyncio.sleep(wait)

        # All attempts exhausted.
        raise last_exc  # type: ignore[misc]

    async def verify_connection(self) -> bool:
        """Health-check: verify Exchange Online connectivity.

        Runs ``Get-OrganizationConfig | Select-Object Name`` and checks that
        a non-empty organisation name is returned.  This is a lightweight
        smoke-test that confirms both the PowerShell environment and the Azure
        AD / Exchange credentials are working.

        Returns:
            True  if the organisation name is present in the response.
            False if the cmdlet fails or returns an empty/missing Name.
                  This method never raises — callers can treat False as
                  "connection unhealthy" and surface an appropriate message.
        """
        try:
            result = await self.run_cmdlet(
                "Get-OrganizationConfig | Select-Object Name"
            )
            if isinstance(result, dict):
                return bool(result.get("Name"))
            # If it came back as a list (shouldn't, but defensive)
            if isinstance(result, list) and result:
                return bool(result[0].get("Name") if isinstance(result[0], dict) else False)
            return False
        except Exception as exc:  # noqa: BLE001
            logger.warning("verify_connection() failed: %s", exc)
            return False
