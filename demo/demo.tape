# VHS tape for Artifact-Scythe demo GIF
#
# How to render
# -------------
# Recommended: let CI do it. Push a change to demo/demo.tape (or run the
# "Render demo GIF" workflow manually) and a Linux runner will produce
# demo/demo.gif and commit it back. See .github/workflows/demo.yml.
#
# Locally (Linux / macOS / WSL only — VHS does not currently render
# reliably on native Windows because of ttyd PTY limitations):
#
#   1. Install VHS:           https://github.com/charmbracelet/vhs
#                             (brew install vhs / go install ...)
#   2. Install ttyd + ffmpeg  (VHS uses them under the hood)
#   3. Install scythe so the recording uses your actual binary:
#        pipx install -e .
#   4. Have python on PATH — demo/fixture.py builds and tears down a
#      cross-platform fake project tree (no bash-only commands).
#
#   vhs demo/demo.tape

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
# Set up a believable demo tree (~225 MB across Node / Python / Rust).
# Hidden so the GIF starts on a clean prompt.
# ---------------------------------------------------------------------------
Hide
Type "python demo/fixture.py setup"
Enter
Sleep 1500
Type "clear"
Enter
Show

# ---------------------------------------------------------------------------
# Scene 1 — the pain: 225 MB of build junk hiding in three projects
# ---------------------------------------------------------------------------
Type "# A year of dev work leaves a lot of stale build artifacts behind."
Enter
Sleep 1200
Type "python demo/fixture.py size"
Sleep 400
Enter
Sleep 1800

# ---------------------------------------------------------------------------
# Scene 2 — scan: see what's there, grouped by ecosystem
# ---------------------------------------------------------------------------
Type "scythe scan /tmp/scythe-demo"
Sleep 400
Enter
Sleep 4500

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
Type "python demo/fixture.py size"
Sleep 400
Enter
Sleep 2500

# ---------------------------------------------------------------------------
# Scene 6 — pitch the advanced flags, end on a tagline
# ---------------------------------------------------------------------------
Type "# scan + clean also support --only, --older-than, --interactive, JSON reports."
Enter
Sleep 2200

# Cleanup (hidden so it doesn't show up in the GIF)
Hide
Type "python demo/fixture.py cleanup"
Enter
Show
Sleep 500
