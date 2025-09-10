# Server Manager CLI

A simple tool to wrangle your Python and Node.js development servers. Because juggling multiple terminals is annoying.

## What it does

- Manages multiple servers from one place
- Restarts crashed servers automatically 
- Shows you logs without opening a million files
- Tracks CPU/memory usage so you know what's hogging resources
- Lets you send commands to running servers

## Getting started

You'll need Python 3.6+(created in 3.11) and the psutil package:

```bash
pip install psutil
python server_manager.py
```

That's it. The tool creates folders for servers and logs as needed.

## Quick examples

```bash
# Create a new Python server
create myapi py

# Start it up
start myapi

# Watch the logs live
log myapi

# See what it's doing to your CPU
usage myapi

# Send it a command
send myapi reload config

# Check on all your servers
list
```

## Commands you'll actually use

**Managing servers:**
- `create <name> <py|node>` - Make a new server with basic template
- `add <path>` - Import an existing server file
- `start/stop/restart <name>` - Do what you'd expect
- `list` - See everything and their status

**Debugging:**
- `log <name>` - Interactive log viewer (type 'exit' to quit)
- `usage <name>` - Live CPU/memory stats (press Enter to exit)
- `send <name> <message>` - Send input to a running server

**Utility:**
- `open <name>` - Opens server file in your editor
- `monitor <name> on/off` - Enable background resource tracking
- `help` - When you forget stuff
- `exit` - Get out of here

## How it works

The tool keeps your servers in a `servers/` folder and logs everything to `logs/`. Server configs live in `servers.json` so they persist between sessions.

When servers crash (and they will), it tries restarting them up to 3 times. If monitoring is on, you get live resource usage in the server list.

## Common gotchas

- **Server won't start?** Check the log file, probably a path or dependency issue
- **No usage stats?** Make sure you ran `pip install psutil`
- **Lost your server?** Use `list` to see everything, or `path <name>` to find the file

## That's basically it

It's not rocket science - just a convenient way to manage multiple dev servers without losing your mind. The interactive log viewer is pretty handy for debugging, and auto-restart saves you from babysitting crashed processes.

Type `help` in the CLI for the full command list.