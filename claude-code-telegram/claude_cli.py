"""Claude CLI wrapper that launches claude-code-haha via bun subprocess.
This is designed to be called by claude-agent-sdk with stdin/stdout pipes.
"""
import os
import sys
import subprocess

# Change to claude-code-haha directory so bunfig.toml/preload.ts are found
os.chdir(r"D:\cc\claude-code-haha")

BUN_EXE = r"C:\Users\rrr\AppData\Roaming\npm\node_modules\bun\bin\bun.exe"

args = [
    BUN_EXE,
    "--env-file=.env.gpt54",
    r"src\entrypoints\cli.tsx",
    "--dangerously-skip-permissions",
] + sys.argv[1:]

proc = subprocess.Popen(
    args,
    stdin=sys.stdin,
    stdout=sys.stdout,
    stderr=sys.stderr,
)
sys.exit(proc.wait())
