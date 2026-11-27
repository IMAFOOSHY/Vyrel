# Vyrel

A beginner-friendly programming language with built-in 2D graphics and
software 3D, implemented as a tree-walking interpreter in pure Python 3.10+
(standard library only).

## Quick start

Requirements: **Python 3.10+**.  On Arch-based Linux (EndeavourOS, CachyOS)
and ChromeOS Crostini, no extra packages are needed for the CLI or the
REPL.  The `gfx` module (2D graphics) additionally requires the `tk` system
package: `sudo pacman -S tk`.

```bash
# Run a program
python3 -m vyrel examples/hello.vyr

# Start the REPL
python3 -m vyrel

# Dump tokens or AST
python3 -m vyrel --tokens examples/fizzbuzz.vyr
python3 -m vyrel --ast examples/fizzbuzz.vyr

# Version and help
python3 -m vyrel --version
python3 -m vyrel --help
