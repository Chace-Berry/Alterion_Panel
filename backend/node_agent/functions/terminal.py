

import asyncio
import json
import sys

# For API contract: this is a stub for one-shot terminal open (not used for streaming)
async def terminal_open(_payload):
    return {"status": "error", "message": "Use terminal_ws_session for streaming terminal"}

async def terminal_ws_session(ws, _payload):
    """
    Persistent terminal session over WebSocket, adapted from TerminalConsumer logic.
    """
    session_id = None
    process = None
    try:
        if sys.platform == 'win32':
            process = _create_windows_process()
        else:
            process = _create_unix_process()  # noqa: unreachable code on Windows
        session_id = str(process.pid)
        await ws.send(json.dumps({"type": "connected", "session_id": session_id}))

        if sys.platform == 'win32':
            output_task = asyncio.create_task(_read_output_windows(ws, session_id, process))
        else:
            output_task = asyncio.create_task(_read_output_unix(ws, session_id, process))

        try:
            while True:
                msg = await ws.recv()
                msg_data = json.loads(msg)
                if msg_data.get('type') == 'input':
                    user_input = msg_data.get('data', '')
                    if sys.platform == 'win32':
                        _send_input_windows(process, user_input)
                    else:
                        _send_input_unix(process, user_input)
                elif msg_data.get('type') == 'resize':
                    # Resize not implemented for now
                    pass
                elif msg_data.get('type') == 'close':
                    process.terminate()
                    break
        except Exception as e:
            await ws.send(json.dumps({'type': 'error', 'message': f'Input error: {str(e)}'}))
        finally:
            output_task.cancel()
            try:
                await output_task
            except:
                pass
    except Exception as e:
        await ws.send(json.dumps({'type': 'error', 'message': str(e)}))
    finally:
        if process:
            process.terminate()

def _create_windows_process():
    import subprocess
    return subprocess.Popen(
        ['powershell.exe', '-NoLogo', '-NoProfile'],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        shell=False,
        bufsize=0
    )

def _create_unix_process():
    import os
    import subprocess
    import pty
    pty_master, pty_slave = pty.openpty()
    shell = os.environ.get('SHELL', '/bin/bash')
    process = subprocess.Popen(
        [shell],
        stdin=pty_slave,
        stdout=pty_slave,
        stderr=pty_slave,
        preexec_fn=os.setsid
    )
    process.pty_master = pty_master
    return process

async def _read_output_windows(ws, session_id, process):
    import asyncio
    try:
        while True:
            data = await asyncio.to_thread(process.stdout.read, 1024)
            if data:
                await ws.send(json.dumps({
                    'type': 'output',
                    'session_id': session_id,
                    'data': data.decode('utf-8', errors='replace')
                }))
            else:
                break
            await asyncio.sleep(0.01)
    except Exception as e:
        await ws.send(json.dumps({'type': 'error', 'message': f'Output error: {str(e)}'}))

async def _read_output_unix(ws, session_id, process):
    import asyncio
    import os
    import select
    try:
        pty_master = process.pty_master
        while True:
            ready, _, _ = await asyncio.to_thread(select.select, [pty_master], [], [], 0.1)
            if len(ready) > 0:
                data = await asyncio.to_thread(os.read, pty_master, 1024)
                if data:
                    await ws.send(json.dumps({
                        'type': 'output',
                        'session_id': session_id,
                        'data': data.decode('utf-8', errors='replace')
                    }))
            else:
                await asyncio.sleep(0.01)
    except Exception as e:
        await ws.send(json.dumps({'type': 'error', 'message': f'Output error: {str(e)}'}))

def _send_input_windows(process, user_input):
    process.stdin.write(user_input.encode())
    process.stdin.flush()

def _send_input_unix(process, user_input):
    import os
    os.write(process.pty_master, user_input.encode())
