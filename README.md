# computer-ctrl

`cctl` is a computer-use toolkit that works with any harness. One tool contract ([`contract/tools.json`](contract/tools.json)) is served two ways: over MCP (`cctl mcp`), and as a CLI (`cctl <tool> --key value`, which prints one JSON line with images saved to disk). An Agent Skill ([`skills/computer-use`](skills/computer-use/SKILL.md)) teaches the loop. Underneath, [Cua Driver](https://github.com/trycua/cua) (pinned, unforked) provides capture, accessibility trees and element actions. cctl adds what Cua lacks:

- coordinate frames that survive resizing and zooming
- a zoom that actually magnifies
- Unicode-safe typing that verifies by reading the field back
- detection of locked or blank displays
- compact output (26 tools in ~18 KB of schema, against Cua's 199 KB)
- process listing
- a remote mode over SSH
- browser control by element refs (Phase 1b)
- screen clips summarized as annotated contact sheets
- system/mic audio capture with levels and a local Whisper transcript
- OCR with clickable line and word boxes (Phase 2)

Status and decisions: [`.project/tracker.md`](.project/tracker.md). Research and plan: [`reports/`](reports/). Install per harness: [`packaging/README.md`](packaging/README.md).

```bash
uv run --group dev pytest                       # unit tests (any OS)
python3 acceptance/phase1.py --cmd "cctl --host user@linux-vm mcp"   # live acceptance against the VM
```
