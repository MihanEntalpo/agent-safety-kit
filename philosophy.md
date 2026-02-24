# Project Philosophy

## 1. The Core Problem

With the spread of AI coding agents, a problem emerged:

- On one side, an agent is very easy to install, and it can quickly produce working code, which feels like magic.
- On the other side, an agent can destroy an entire project, introduce changes that break working code and cannot be repaired anymore, and damage the whole system.

The key reason for risk:

An AI agent is not a reasoning system that understands consequences. It is a probabilistic model. It performs statistically plausible actions, and no matter how much it is trained to be “safe,” it will never be fully safe.

Implication:

Even with built-in sandboxes (cgroups, internal checkpoints, etc.), it is impossible to fully exclude:

- jailbreaks through external sources,
- generation of malicious code,
- attempts to bypass constraints,
- incorrect code edits with no ability to restore everything as it was,
- destruction of an entire project that is not in Git and has no backups,
- uncontrolled resource consumption.

We assume an AI agent is dangerous by default and do not rely on its internal restrictions.

---

## 2. Target Audience

The project is aimed at:

- regular developers,
- AI enthusiasts,
- users who do not want to dive into container internals and manual backup setup.

Principle:

Installing and using an agent safely should be almost as simple as  
`npm install codex` / `npm install qwen-code` / `npm install claude-code`,  
but significantly more reliable than the default execution approach.

---

## 3. Architectural Choice: Virtual Machine as the Base Security Unit

Containers (Docker, LXC, LXD) were deliberately excluded as the foundation for these reasons:

- containers share the host kernel;
- isolation is weaker than with a full VM;
- configuration mistakes are easy to make;
- constraint conflicts can happen (agent cgroups vs Docker cgroups);
- instability and side effects can impact the main system.

### 3.1. Containers Are the Target Development Environment

In modern development, Docker is a standard delivery and build environment. A normal agent workflow is:

- generate a `Dockerfile`,
- create `docker-compose.yml`,
- build images,
- run containers,
- verify service behavior.

If the agent itself runs inside a container, a problem appears:

- running Docker-in-Docker typically requires privileged mode;
- or you must mount the host Docker socket (`/var/run/docker.sock`), which effectively grants host-level root power to that container;
- safely and fully running container infrastructure inside a restricted container is not feasible without weakening isolation.

Implication:

A container as the base environment is incompatible with containers as the target development environment.

If an agent must:

- design container architecture,
- build images,
- run services,
- test orchestration,

its execution environment must be:

- either a physical machine,
- or a full virtual machine.

### 3.2. Why a Virtual Machine Was Chosen

A virtual machine provides:

- strict CPU, RAM, and disk limits;
- a higher barrier for escaping the environment;
- minimal impact on the host;
- the ability to run Docker safely inside itself;
- a correct model for modern development workflows.

A VM is used not only because isolation is stronger, but also because it preserves the architectural integrity of the DevOps process.

---

## 4. Why Multipass

Multipass (Ubuntu VM) was chosen because of:

- simple startup,
- low entry barrier,
- no need to hand-write complex machine configs (compared to Vagrant),
- focus on mainstream users.

Its limitations (for example, no RPM-native distributions) are considered acceptable because:

- Ubuntu/Debian cover most user scenarios;
- Docker inside the VM can be used for specialized cases when needed.

---

## 5. System Principles

### 5.1. Secure by Default

- The agent runs in isolation.
- Resources are limited.
- User data is not directly exposed.
- Potentially dangerous operations happen inside the VM.
- Automatic backup is built in.
- Data-sharing boundaries must be enforceable per directory: mounts can explicitly allow only selected agent profiles (for example, self-hosted only for NDA-sensitive folders).

### 5.2. State Transparency

The user should be able to see:

- which VMs are running;
- which VMs belong to this system;
- which folders are mounted;
- which agents are active;
- which processes are running;
- CPU/RAM usage;
- which ports are forwarded;
- whether backups are currently working.

### 5.3. Infrastructure Control

The system includes:

- VM creation and lifecycle management;
- generation of independent SSH keys;
- SSH-based port forwarding (without relying on changing VM IP addresses);
- SOCKS proxy support;
- a systemd daemon that manages:
  - backups,
  - agent processes,
  - port forwarding,
  - state monitoring,
  - centralized system status output.

---

## 6. Backup Position

Backups are a foundational part of the safety architecture.

### 6.1. Backups by Default

- Backups are enabled automatically.
- The user should not have to remember to enable protection.
- “No backups” is not the default state.

### 6.2. Automation and Independence

- Backups can run independently of the agent lifecycle.
- An agent process may be short-lived.
- Backups may run continuously or on schedule.
- Starting/stopping an agent should not be required to control data protection.

### 6.3. Explicit Opt-Out

- Disabling backups is possible.
- It requires explicit user action.
- It should not happen accidentally.
- It is not the default behavior.

---

## 7. TODO: Installation Simplicity

Current `pip`-based installation is inconvenient for a system tool with a daemon.

Goal:

- make installation system-level;
- minimize manual setup;
- distribute through Snap (logical, since Multipass itself is distributed via snap).

Future direction:

- Windows support (via WSL),
- macOS support (through an alternative package system, e.g. Homebrew).

---

## 8. Core Philosophical Position

1. AI agents are inherently risky.
2. Built-in sandboxes are not sufficient.
3. Containers are a compromise, not full isolation.
4. A full virtual machine is the minimum acceptable safety level.
5. Users should not have to become DevOps engineers just to run an agent safely.
6. Safety, transparency, and control are more important than maximum performance.
7. Backups should be automatic and mandatory by default.
8. Access to sensitive project folders must be constrained by policy, not by user memory.

---

## 9. Project Formula

The project is:

A simplified, system-managed, isolated runtime for AI agents, aimed at regular users and built around a virtual machine as the core security unit.
