@echo off
cd /d D:\cc\claude-code-haha
bun --env-file=.env .\src\entrypoints\cli.tsx %*
