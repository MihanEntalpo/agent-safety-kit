# `pip-upgrade`

## Contents

- [Purpose](#purpose)
- [Command](#command)
- [What It Does](#what-it-does)
- [Example](#example)

## Purpose

Upgrade `agsekit` in the same Python environment that runs the current CLI.

## Command

```bash
agsekit pip-upgrade
```

## What It Does

1. Checks that `agsekit` is installed through `pip` in the current environment.
2. Reads the current installed version through `pip show agsekit`.
3. Runs `pip install agsekit --upgrade`.
4. Reads the installed version again and prints the result:
   - if the version changed, reports the old and new versions;
   - if the version did not change, reports that the latest version is already installed.

## Example

```bash
agsekit pip-upgrade
```

## See Also

- [prepare](prepare.md)
- [up](up.md)
- [Documentation index](../README.md)
