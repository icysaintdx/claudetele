"""Local Claude Code Bun implementation integration.

Provides a manager that calls the local Bun-based Claude Code implementation
instead of using the official Claude CLI SDK.
"""

import asyncio
import json
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator, Callable, Dict, List, Optional, Tuple

import structlog

from ..config.settings import Settings
from ..security.validators import SecurityValidator
from ..storage.message_storage import (
    ConversationMessage,
    MessageHistoryStorage,
    MessageRole,
)
from .exceptions import (
    ClaudeMCPError,
    ClaudeParsingError,
    ClaudeProcessError,
    ClaudeTimeoutError,
)
from .monitor import _is_claude_internal_path, check_bash_directory_boundary
from .sdk_integration import ClaudeResponse, StreamUpdate

logger = structlog.get_logger()

# Patterns to extract tool usage from output
_TOOL_PATTERNS = [
    r"📖\s*Read(?::\s*(.+))?",
    r"📂\s*LS",
    r"✏️\s*Edit(?::\s*(.+))?",
    r"📝\s*Write(?::\s*(.+))?",
    r"💻\s*Bash(?::\s*(.+))?",
    r"🔍\s*Grep(?::\s*(.+))?",
    r"📁\s*Glob(?::\s*(.+))?",
    r"🤖\s*Task",
    r"📋\s*TodoRead",
    r"✅\s*TodoWrite",
    r"🌐\s*WebFetch",
    r"🔎\s*WebSearch",
    r"🛠️\s*Skill",
]


def _extract_tools_from_output(output: str) -> List[Dict[str, Any]]:
    """Extract tool usage information from CLI output."""
    tools = []
    timestamp = asyncio.get_event_loop().time()

    for pattern in _TOOL_PATTERNS:
        matches = re.finditer(pattern, output, re.IGNORECASE)
        for match in matches:
            tool_name = match.group(0).split()[0].strip("📖📂✏️📝💻🔍📁🤖📋✅🌐🔎🛠️")
            detail = match.group(1) if match.lastindex and match.group(1) else ""
            tools.append(
                {
                    "name": tool_name,
                    "timestamp": timestamp,
                    "input": {"detail": detail} if detail else {},
                }
            )

    return tools


def _build_contextual_prompt(
    history: List[ConversationMessage],
    new_prompt: str,
    max_context_messages: int = 20,
) -> str:
    """Build a prompt that includes conversation history.

    This allows the local Bun implementation to have persistent context
    even though it doesn't natively support session resumption.

    Args:
        history: Previous conversation messages
        new_prompt: The new user message
        max_context_messages: Maximum number of historical messages to include

    Returns:
        A combined prompt with context
    """
    if not history:
        return new_prompt

    # Take only the most recent messages to avoid context overflow
    recent_history = history[-max_context_messages:]

    context_parts = [
        "=== CONVERSATION CONTEXT ===",
        "The following is the conversation history. Please respond to the last message.",
        "",
    ]

    for msg in recent_history:
        role_label = "User" if msg.role == MessageRole.USER else "Assistant"
        context_parts.append(f"{role_label}: {msg.content}")

    context_parts.extend(
        [
            "",
            "=== NEW MESSAGE ===",
            f"User: {new_prompt}",
            "",
            "Assistant:",
        ]
    )

    return "\n".join(context_parts)


class LocalBunManager:
    """Manage local Bun-based Claude Code implementation.

    This manager calls the local claude-code-local project via Bun
    instead of using the official Claude CLI SDK.
    """

    def __init__(
        self,
        config: Settings,
        security_validator: Optional[SecurityValidator] = None,
        message_storage: Optional[MessageHistoryStorage] = None,
    ):
        """Initialize local Bun manager with configuration."""
        self.config = config
        self.security_validator = security_validator
        self.message_storage = message_storage
        self.project_root = self._find_project_root()

        # Maximum number of historical messages to include in context
        self.max_context_messages = 50

        logger.info(
            "Initialized LocalBunManager",
            project_root=str(self.project_root),
            has_message_storage=message_storage is not None,
        )

    def _find_project_root(self) -> Path:
        """Find the local Claude Code project root.

        Tries to find it relative to the Telegram bot, or uses environment variable.
        """
        # Check environment variable first
        env_path = os.environ.get("CLAUDE_LOCAL_PROJECT_PATH")
        if env_path:
            path = Path(env_path)
            if path.exists() and (path / "src" / "entrypoints" / "cli.tsx").exists():
                return path
            logger.warning(
                "CLAUDE_LOCAL_PROJECT_PATH set but invalid",
                path=str(path),
            )

        # Try relative to current file (assuming standard structure)
        # claude-code-telegram/src/claude/ -> claude-code-local/
        current_file = Path(__file__).resolve()
        possible_roots = [
            # Sibling directory
            current_file.parent.parent.parent.parent.parent / "claude-code-local",
            current_file.parent.parent.parent.parent.parent / "claudecode",
            # Parent of telegram bot
            current_file.parent.parent.parent.parent.parent.parent
            / "claude-code-local",
            current_file.parent.parent.parent.parent.parent.parent / "claudecode",
        ]

        for root in possible_roots:
            if root.exists() and (root / "src" / "entrypoints" / "cli.tsx").exists():
                logger.info("Found local Claude Code project", root=str(root))
                return root

        # Fallback: assume current working directory
        cwd = Path.cwd()
        if (cwd / "src" / "entrypoints" / "cli.tsx").exists():
            return cwd

        raise RuntimeError(
            "Could not find local Claude Code project. "
            "Please set CLAUDE_LOCAL_PROJECT_PATH environment variable "
            "to the directory containing src/entrypoints/cli.tsx"
        )

    def _build_cli_command(
        self,
        prompt: str,
        working_directory: Path,
        env_vars: Optional[Dict[str, str]] = None,
    ) -> Tuple[List[str], Dict[str, str]]:
        """Build the CLI command to execute.

        Returns:
            Tuple of (command args, environment variables)
        """
        # Base command
        cmd = [
            "bun",
            "--env-file=.env",
            "./src/entrypoints/cli.tsx",
            "-p",  # Print mode (headless)
            prompt,
        ]

        # Prepare environment
        env = os.environ.copy()

        # Set working directory for the command
        env["PWD"] = str(working_directory)

        # Pass through API configuration from our config
        if self.config.anthropic_api_key_str:
            env["ANTHROPIC_API_KEY"] = self.config.anthropic_api_key_str
        if self.config.claude_model:
            env["ANTHROPIC_MODEL"] = self.config.claude_model

        # Add timeout
        env["API_TIMEOUT_MS"] = str(self.config.claude_timeout_seconds * 1000)

        # Disable telemetry
        env["DISABLE_TELEMETRY"] = "1"
        env["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] = "1"

        # Add any additional env vars
        if env_vars:
            env.update(env_vars)

        return cmd, env

    async def execute_command(
        self,
        prompt: str,
        working_directory: Path,
        session_id: Optional[str] = None,
        continue_session: bool = False,
        stream_callback: Optional[Callable[[StreamUpdate], None]] = None,
        interrupt_event: Optional[asyncio.Event] = None,
        images: Optional[List[Dict[str, str]]] = None,
    ) -> ClaudeResponse:
        """Execute Claude Code command via local Bun implementation with persistent context.

        This implementation now supports persistent conversation context by:
        1. Storing all messages in message_storage
        2. Retrieving history when continuing a session
        3. Prepending history to the prompt for context
        """
        start_time = asyncio.get_event_loop().time()

        # Generate or use provided session ID
        effective_session_id = (
            session_id or f"local_{hash(str(working_directory)) % 10000000}"
        )

        logger.info(
            "Starting local Bun Claude command",
            working_directory=str(working_directory),
            session_id=effective_session_id,
            continue_session=continue_session,
            prompt_length=len(prompt),
            has_message_storage=self.message_storage is not None,
        )

        # Security validation
        if self.security_validator:
            valid, resolved, error = self.security_validator.validate_path(
                str(working_directory), working_directory
            )
            if not valid:
                raise ClaudeProcessError(f"Directory validation failed: {error}")

        # Store user message if we have message storage
        if self.message_storage and effective_session_id:
            try:
                await self.message_storage.add_message(
                    session_id=effective_session_id,
                    role=MessageRole.USER,
                    content=prompt,
                    metadata={"working_directory": str(working_directory)},
                )
                logger.debug("User message stored", session_id=effective_session_id)
            except Exception as e:
                logger.warning("Failed to store user message", error=str(e))

        # Handle images
        if images:
            image_note = f"\n\n[Note: {len(images)} image(s) were provided but local implementation may not support image analysis]"
            prompt = prompt + image_note
            logger.warning(
                "Images provided but local implementation has limited multimodal support",
                image_count=len(images),
            )

        # Build contextual prompt with conversation history
        final_prompt = prompt
        conversation_history = []

        if self.message_storage and effective_session_id and continue_session:
            try:
                conversation_history = (
                    await self.message_storage.get_conversation_history(
                        session_id=effective_session_id,
                        limit=self.max_context_messages,
                    )
                )

                if conversation_history:
                    # Build contextual prompt with history
                    final_prompt = _build_contextual_prompt(
                        conversation_history,
                        prompt,
                        max_context_messages=self.max_context_messages,
                    )
                    logger.info(
                        "Built contextual prompt with history",
                        session_id=effective_session_id,
                        history_messages=len(conversation_history),
                        final_prompt_length=len(final_prompt),
                    )
            except Exception as e:
                logger.warning(
                    "Failed to retrieve conversation history",
                    error=str(e),
                    session_id=effective_session_id,
                )

        # Build command
        cmd, env = self._build_cli_command(final_prompt, working_directory)

        # Pass session info via environment
        env["CLAUDE_SESSION_ID"] = effective_session_id
        if continue_session:
            env["CLAUDE_CONTINUE_SESSION"] = "1"

        try:
            stdout_lines: List[str] = []
            stderr_lines: List[str] = []
            interrupted = False

            # Create subprocess
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.project_root,
                env=env,
            )

            # Read output with timeout and interrupt support
            async def _read_output() -> Tuple[str, str]:
                """Read stdout and stderr from process."""
                stdout_data = []
                stderr_data = []

                async def _read_stream(stream, data_list, name):
                    """Read a stream and optionally call stream callback."""
                    while True:
                        line = await stream.readline()
                        if not line:
                            break
                        text = line.decode("utf-8", errors="replace")
                        data_list.append(text)

                        # Call stream callback if provided
                        if stream_callback and name == "stdout":
                            try:
                                update = StreamUpdate(
                                    type="stream_delta",
                                    content=text,
                                )
                                # Stream callback may be sync or async
                                result = stream_callback(update)
                                if asyncio.iscoroutine(result):
                                    await result
                            except Exception as e:
                                logger.warning("Stream callback failed", error=str(e))

                # Read both streams concurrently
                await asyncio.gather(
                    _read_stream(process.stdout, stdout_data, "stdout"),
                    _read_stream(process.stderr, stderr_data, "stderr"),
                )

                return "".join(stdout_data), "".join(stderr_data)

            # Run with timeout and interrupt checking
            try:
                if interrupt_event:
                    # Poll for interrupt while waiting
                    output_task = asyncio.create_task(_read_output())

                    while not output_task.done():
                        if interrupt_event.is_set():
                            interrupted = True
                            process.terminate()
                            try:
                                await asyncio.wait_for(process.wait(), timeout=5.0)
                            except asyncio.TimeoutError:
                                process.kill()
                                await process.wait()
                            break
                        await asyncio.sleep(0.1)

                    if not interrupted:
                        stdout, stderr = await output_task
                    else:
                        stdout, stderr = "", "Command interrupted by user"
                else:
                    # Simple timeout
                    stdout, stderr = await asyncio.wait_for(
                        _read_output(),
                        timeout=self.config.claude_timeout_seconds,
                    )

                # Wait for process to complete (if not already done)
                if process.returncode is None:
                    try:
                        await asyncio.wait_for(
                            process.wait(),
                            timeout=5.0,
                        )
                    except asyncio.TimeoutError:
                        process.kill()
                        await process.wait()

            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                raise ClaudeTimeoutError(
                    f"Local Claude command timed out after {self.config.claude_timeout_seconds}s"
                )

            # Calculate duration
            duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)

            # Check exit code
            exit_code = process.returncode or 0

            if exit_code != 0 and not interrupted:
                error_msg = stderr.strip() or f"Process exited with code {exit_code}"
                logger.error(
                    "Local Claude command failed",
                    exit_code=exit_code,
                    stderr_preview=stderr[:500] if stderr else None,
                )

                # Check for MCP errors
                if "mcp" in error_msg.lower():
                    raise ClaudeMCPError(f"MCP error: {error_msg}")

                raise ClaudeProcessError(f"Local Claude command failed: {error_msg}")

            # Extract content
            content = stdout.strip()

            # Store assistant response if we have message storage
            if self.message_storage and effective_session_id and content:
                try:
                    await self.message_storage.add_message(
                        session_id=effective_session_id,
                        role=MessageRole.ASSISTANT,
                        content=content,
                        metadata={
                            "working_directory": str(working_directory),
                            "duration_ms": duration_ms,
                        },
                    )
                    logger.debug(
                        "Assistant response stored", session_id=effective_session_id
                    )
                except Exception as e:
                    logger.warning("Failed to store assistant response", error=str(e))

            # Extract tools used from output
            tools_used = _extract_tools_from_output(content)

            # Estimate cost (local implementation doesn't track cost)
            estimated_cost = 0.0

            logger.info(
                "Local Claude command completed",
                session_id=effective_session_id,
                duration_ms=duration_ms,
                output_length=len(content),
                tools_used_count=len(tools_used),
                interrupted=interrupted,
                had_context=len(conversation_history) > 0,
            )

            return ClaudeResponse(
                content=content,
                session_id=effective_session_id,
                cost=estimated_cost,
                duration_ms=duration_ms,
                num_turns=len(conversation_history) // 2 + 1
                if conversation_history
                else 1,
                tools_used=tools_used,
                interrupted=interrupted,
            )

        except asyncio.TimeoutError:
            raise ClaudeTimeoutError(
                f"Local Claude command timed out after {self.config.claude_timeout_seconds}s"
            )
        except subprocess.SubprocessError as e:
            logger.error("Subprocess error", error=str(e))
            raise ClaudeProcessError(f"Failed to execute local Claude: {str(e)}")
        except Exception as e:
            logger.error(
                "Unexpected error in local Bun manager",
                error=str(e),
                error_type=type(e).__name__,
            )
            raise ClaudeProcessError(f"Unexpected error: {str(e)}")

    async def _handle_stream_message(
        self, line: str, stream_callback: Callable[[StreamUpdate], Any]
    ) -> None:
        """Handle streaming output line."""
        try:
            update = StreamUpdate(
                type="stream_delta",
                content=line,
            )
            result = stream_callback(update)
            if asyncio.iscoroutine(result):
                await result
        except Exception as e:
            logger.warning("Stream callback failed", error=str(e))
