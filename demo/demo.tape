# VHS tape for Artifact-Scythe demo GIF
#
# Prerequisites:
#   1. Install VHS:           https://github.com/charmbracelet/vhs
#                             (brew install vhs / scoop install vhs / go install ...)
#   2. Install ttyd + ffmpeg  (VHS uses them under the hood)
#   3. Install scythe locally so the recording uses your actual binary:
#        pipx install -e .
#      or, if you only have pip:
#        pip install -e .
#
# Run:
#   vhs demo/demo.tape
#
# Output:
#   demo/demo.gif        (drop this at the top of the README)
#   demo/demo.mp4        (kept for higher-quality previews)
#
# Re-run any time you change the CLI output and want a fresh GIF.

Output demo/demo.gif
Output demo/demo.mp4

Set Shell "bash"
Set FontSize 16
Set Width 1100
Set Height 650
Set Theme "Catppuccin Mocha"
Set TypingSpeed 40ms
Set PlaybackSpeed 1.0
Set Padding 20

# ---------------------------------------------------------------------------
# Scene 0 — set up a believable demo tree in /tmp/scythe-demo
# ---------------------------------------------------------------------------
Hidden
Type "rm -rf /tmp/scythe-demo && mkdir -p /tmp/scythe-demo && cd /tmp/scythe-demo"
Enter
# Node project with a chunky node_modules (~80 MB simulated)
Type "mkdir -p webapp/node_modules/.cache && echo '{}' > webapp/package.json"
Enter
Type "dd if=/dev/zero of=webapp/node_modules/bundle.bin bs=1M count=80 status=none"
Enter
# Python project with a venv (~25 MB simulated)
Type "mkdir -p api/.venv/lib && echo '' > api/pyproject.toml"
Enter
Type "dd if=/dev/zero of=api/.venv/lib/site-packages.bin bs=1M count=25 status=none"
Enter
# Rust project with a target/ (~120 MB simulated)
Type "mkdir -p service/target/debug && echo '[package]' > service/Cargo.toml"
Enter
Type "dd if=/dev/zero of=service/target/debug/build.bin bs=1M count=120 status=none"
Enter
Type "clear"
Enter
Show

# ---------------------------------------------------------------------------
# Scene 1 — the pain: 225 MB of build junk hiding in three projects
# ---------------------------------------------------------------------------
Type "# A year of dev work leaves a lot of stale build artifacts behind."
Enter
Sleep 1500
Type "du -sh /tmp/scythe-demo"
Sleep 400
Enter
Sleep 1800

# ---------------------------------------------------------------------------
# Scene 2 — scan: see what's there, grouped by ecosystem
# ---------------------------------------------------------------------------
Type "scythe scan /tmp/scythe-demo"
Sleep 400
Enter
Sleep 4000

# ---------------------------------------------------------------------------
# Scene 3 — dry-run: rehearse the deletion safely
# ---------------------------------------------------------------------------
Type "scythe clean /tmp/scythe-demo --dry-run --force"
Sleep 400
Enter
Sleep 4000

# ---------------------------------------------------------------------------
# Scene 4 — do it for real
# ---------------------------------------------------------------------------
Type "scythe clean /tmp/scythe-demo --force"
Sleep 400
Enter
Sleep 4000

# ---------------------------------------------------------------------------
# Scene 5 — proof the disk space came back
# ---------------------------------------------------------------------------
Type "du -sh /tmp/scythe-demo"
Sleep 400
Enter
Sleep 2500

# ---------------------------------------------------------------------------
# Scene 6 — pitch the advanced flag, end on a tagline
# ---------------------------------------------------------------------------
Type "# scan + clean also support --only, --older-than, --interactive, JSON reports."
Enter
Sleep 2000

# Cleanup (hidden so it doesn't show up in the GIF)
Hidden
Type "rm -rf /tmp/scythe-demo"
Enter
Show
Sleep 500
