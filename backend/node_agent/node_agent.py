async def collect_metrics():
    # Call the existing sync collect_metrics function in a thread
    import asyncio
    def _collect():
        # Place your actual metrics collection logic here
        try:
            metrics = {
                "timestamp": datetime.now().isoformat(),
                "system": get_system_info(),
                "cpu": {
                    "usage_percent": psutil.cpu_percent(interval=1),
                    "per_cpu": psutil.cpu_percent(interval=1, percpu=True),
                    "count": psutil.cpu_count(),
                    "count_logical": psutil.cpu_count(logical=True),
                    "load_avg": list(os.getloadavg()) if hasattr(os, 'getloadavg') else None,
                },
                "memory": {
                    **psutil.virtual_memory()._asdict(),
                    "swap": psutil.swap_memory()._asdict(),
                },
                "disk": {
                    "partitions": [p._asdict() for p in psutil.disk_partitions()],
                    "usage": {
                        p.mountpoint: psutil.disk_usage(p.mountpoint)._asdict() 
                        for p in psutil.disk_partitions() 
                        if os.path.exists(p.mountpoint)
                    },
                },
                "network": {
                    "io": psutil.net_io_counters()._asdict(),
                    "io_per_nic": {
                        k: v._asdict() for k, v in psutil.net_io_counters(pernic=True).items()
                    },
                    "connections": len(psutil.net_connections()),
                },
                "services": [],
                "processes": {
                    "count": len(psutil.pids()),
                },
            }
            return metrics
        except Exception as e:
            return {"error": str(e)}
    return await asyncio.to_thread(_collect)

async def list_files(path):
    import asyncio
    def _list():
        try:
            p = Path(path)
            if not p.exists():
                return {"error": f"Path does not exist: {path}"}
            if p.is_file():
                return {"files": [str(p)]}
            return {"files": [str(f) for f in p.iterdir()]}
        except Exception as e:
            return {"error": str(e)}
    return await asyncio.to_thread(_list)
#Node Agent for Alterion Panel
import asyncio
import websockets
import ssl
import os
import sys
import json
import logging
import platform
import base64
import uuid
import hashlib
import socket
import subprocess
from pathlib import Path
from datetime import datetime
import psutil
import node_crypto_utils as crypto_utils

# Base configuration - server_url must be provided via server_config.json
AGENT_CONFIG = {
    "server_url": None,  # Must be set via server_config.json
    "agent_id_file": "agent_id.json",
    "reconnect_delay": 5,
    "serverid_path": "serverid.dat",
    "connection_timeout": 30,  # Timeout for websocket operations
}

# Load server config (created during SSH onboarding) - REQUIRED
server_config_file = Path("server_config.json")
if server_config_file.exists():
    try:
        with open(server_config_file, 'r') as f:
            server_config = json.load(f)
            AGENT_CONFIG.update(server_config)
            print(f"✓ Loaded server configuration from {server_config_file}")
            print(f"  Server URL: {AGENT_CONFIG['server_url']}")
    except Exception as e:
        print(f"✗ ERROR: Failed to load server_config.json: {e}")
        sys.exit(1)
else:
    print(f"✗ ERROR: server_config.json not found!")
    print(f"  This file should be created during SSH onboarding.")
    print(f"  Please run the SSH onboarding process from the panel.")
    sys.exit(1)

# Verify server_url is set
if not AGENT_CONFIG.get("server_url"):
    print(f"✗ ERROR: server_url not configured in server_config.json")
    sys.exit(1)


# --- Setup logging ---
log_file = 'node_agent.log'
pid_file = 'node_agent.pid'
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("alterion_node_agent")
logger.setLevel(logging.DEBUG)

# File to persist API responses that couldn't be delivered due to disconnects
PENDING_RESPONSES_FILE = Path("pending_responses.json")


def _load_pending_responses():
    try:
        if PENDING_RESPONSES_FILE.exists():
            return json.loads(PENDING_RESPONSES_FILE.read_text()) or []
    except Exception as e:
        logger.warning(f"Failed to load pending responses: {e}")
    return []


def _save_pending_responses(responses):
    try:
        PENDING_RESPONSES_FILE.write_text(json.dumps(responses))
    except Exception as e:
        logger.error(f"Failed to save pending responses: {e}")


async def _queue_response(response_obj):
    """Store a response locally to resend after reconnect."""
    try:
        responses = _load_pending_responses()
        responses.append(response_obj)
        _save_pending_responses(responses)
        logger.info(f"Queued response for later delivery: {response_obj.get('request_id')}")
    except Exception as e:
        logger.error(f"Failed to queue response: {e}")


async def _try_send_or_queue(ws, response_obj):
    """Attempt to send over ws; if it fails, queue locally."""
    try:
        await ws.send(json.dumps(response_obj))
        return True
    except Exception as e:
        logger.warning(f"Failed to send response (will queue): {e}")
        try:
            await _queue_response(response_obj)
        except Exception:
            # queue failure already logged
            pass
        return False


def write_pid():
    try:
        with open(pid_file, 'w') as f:
            f.write(str(os.getpid()))
    except Exception as e:
        logger.error(f"Failed to write PID file: {e}")

def remove_pid():
    try:
        if os.path.exists(pid_file):
            os.remove(pid_file)
    except Exception as e:
        logger.error(f"Failed to remove PID file: {e}")

def stop_all_agents():
    import signal
    import psutil
    if not os.path.exists(pid_file):
        print("No node_agent.pid file found. Is the agent running?")
        return
    try:
        with open(pid_file, 'r') as f:
            pid = int(f.read().strip())
        print(f"Stopping node agent process {pid} and all children...")
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)
        for child in children:
            try:
                child.terminate()
            except Exception:
                pass
        gone, alive = psutil.wait_procs(children, timeout=3)
        try:
            parent.terminate()
        except Exception:
            pass
        parent.wait(3)
        remove_pid()
        print("Node agent stopped.")
    except Exception as e:
        print(f"Failed to stop node agent: {e}")

# --- Background/daemon support ---
def run_in_background():
    if platform.system() == "Windows":
        if not hasattr(sys, 'frozen') and os.getenv('NODE_AGENT_BG') != '1':
            DETACHED_PROCESS = 0x00000008
            subprocess.Popen([sys.executable, __file__], creationflags=DETACHED_PROCESS, 
                           env={**os.environ, 'NODE_AGENT_BG': '1'})
            sys.exit(0)
    else:
        if os.getenv('NODE_AGENT_BG') != '1':
            pid = os.fork()
            if pid > 0:
                sys.exit(0)
            os.setsid()
            pid = os.fork()
            if pid > 0:
                sys.exit(0)
            os.environ['NODE_AGENT_BG'] = '1'
            sys.stdout.flush()
            sys.stderr.flush()
            with open('/dev/null', 'wb', 0) as devnull:
                os.dup2(devnull.fileno(), sys.stdin.fileno())
                os.dup2(devnull.fileno(), sys.stdout.fileno())
                os.dup2(devnull.fileno(), sys.stderr.fileno())

def ensure_background():
    if os.getenv('NODE_AGENT_BG') != '1':
        run_in_background()

# --- Node UID generation ---
def get_or_create_server_id():
    server_id_path = Path(AGENT_CONFIG["serverid_path"]).resolve()
    if server_id_path.exists():
        try:
            sid = server_id_path.read_text().strip()
            if sid:
                logger.info(f"Loaded existing server ID: {sid}")
                return sid
        except Exception:
            pass
    
    try:
        mac = uuid.getnode()
        mac_str = f"{mac:012x}"
    except Exception:
        mac_str = "unknownmac"
    
    disk = "unknowndisk"
    mb = "unknownmb"
    
    try:
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
    except Exception:
        ip = "unknownip"
    
    raw = f"{mac_str}-{disk}-{mb}-{ip}"
    server_id = hashlib.sha256(raw.encode()).hexdigest()[:16]
    
    try:
        server_id_path.write_text(server_id)
        logger.info(f"Created new server ID: {server_id}")
    except Exception as e:
        logger.error(f"Failed to save server ID: {e}")
    
    return server_id

def load_or_create_identity():
    """Load or create agent identity"""
    keys_dir = Path("keys")
    keys_dir.mkdir(exist_ok=True)
    id_path = Path(AGENT_CONFIG["agent_id_file"])
    
    # Check for agent_private.pem first, then fallback to keys/agent_private.pem
    privkey_paths = [Path("agent_private.pem"), keys_dir / "agent_private.pem"]
    pubkey_paths = [Path("agent_public.pem"), keys_dir / "agent_public.pem"]
    
    privkey_path = None
    pubkey_path = None
    
    # Find existing keys
    for p in privkey_paths:
        if p.exists():
            privkey_path = p
            break
    
    for p in pubkey_paths:
        if p.exists():
            pubkey_path = p
            break
    
    node_uid = get_or_create_server_id()
    
    # Try to load existing identity
    if privkey_path and pubkey_path and id_path.exists():
        try:
            with open(id_path, "r") as f:
                data = json.load(f)
            priv = crypto_utils.load_private_key(privkey_path.read_bytes())
            pub = crypto_utils.load_public_key(pubkey_path.read_bytes())
            logger.info(f"✓ Loaded identity: agent_id={data.get('agent_id')}, serverid={data.get('serverid')}")
            return {
                "private_key": priv,
                "public_key": pub,
                "agent_id": data.get("agent_id"),
                "node_uid": data.get("serverid", node_uid),
                "private_key_file": str(privkey_path),
                "public_key_file": str(pubkey_path),
                "code": data.get("code"),
            }
        except Exception as e:
            logger.warning(f"Failed to load existing identity: {e}. Creating new one.")
    
    # If we have keys but no agent_id.json, try to load just the keys
    if privkey_path and pubkey_path:
        try:
            priv = crypto_utils.load_private_key(privkey_path.read_bytes())
            pub = crypto_utils.load_public_key(pubkey_path.read_bytes())
            logger.info(f"✓ Loaded existing keys (no agent_id.json), serverid={node_uid}")
            
            # Create agent_id.json
            data = {
                "serverid": node_uid,
                "agent_id": None,
                "private_key_file": str(privkey_path),
                "public_key_file": str(pubkey_path),
            }
            with open(id_path, "w") as f:
                json.dump(data, f)
            
            return {
                "private_key": priv,
                "public_key": pub,
                "agent_id": None,
                "node_uid": node_uid,
                "private_key_file": str(privkey_path),
                "public_key_file": str(pubkey_path),
            }
        except Exception as e:
            logger.warning(f"Failed to load existing keys: {e}. Generating new keypair.")
    
    # Generate new keypair
    logger.info("Generating new keypair...")
    priv, pub = crypto_utils.generate_rsa_keypair()
    privkey_bytes = crypto_utils.serialize_private_key(priv)
    pubkey_bytes = crypto_utils.serialize_public_key(pub)
    
    # Use root directory for keys (not keys/ subdirectory) to match SSH onboarding
    privkey_path = Path("agent_private.pem")
    pubkey_path = Path("agent_public.pem")
    
    with open(privkey_path, "wb") as f:
        f.write(privkey_bytes)
    os.chmod(privkey_path, 0o600)
    
    with open(pubkey_path, "wb") as f:
        f.write(pubkey_bytes)
    os.chmod(pubkey_path, 0o644)
    
    data = {
        "serverid": node_uid,
        "agent_id": None,
        "private_key_file": str(privkey_path),
        "public_key_file": str(pubkey_path),
    }
    with open(id_path, "w") as f:
        json.dump(data, f)
    
    logger.info("✓ Created new identity")
    return {
        "private_key": priv,
        "public_key": pub,
        "agent_id": None,
        "node_uid": node_uid,
        "private_key_file": str(privkey_path),
        "public_key_file": str(pubkey_path),
    }

def save_agent_id(agent_id, code=None):
    id_path = Path(AGENT_CONFIG["agent_id_file"])
    if id_path.exists():
        with open(id_path, "r") as f:
            data = json.load(f)
    else:
        data = {}

    data["agent_id"] = agent_id
    if code:
        data["code"] = code

    # Fix: Remove 'valid' field if present, so it doesn't persist after failed verification
    if "valid" in data:
        del data["valid"]

    with open(id_path, "w") as f:
        json.dump(data, f)
    logger.info(f"Saved agent_id={agent_id}, code={code}")

def get_system_info():
    return {
        "hostname": platform.node(),
        "platform": platform.system(),
        "platform_release": platform.release(),
        "platform_version": platform.version(),
        "architecture": platform.machine(),
        "processor": platform.processor(),
    }

shutdown_event = asyncio.Event()

async def handle_encrypted_message(msg, identity):
    """Decrypt and handle encrypted message from backend"""
    try:
        cryptdata = msg.get("cryptdata")
        data = msg.get("data")
        
        if not (cryptdata and data):
            logger.warning("Malformed encrypted message")
            return None
        
        # Decrypt payload
        payload = crypto_utils.decrypt_payload(cryptdata, data, identity["private_key"])
        logger.info(f"Decrypted message: {payload}")
        
        # Handle commands
        if payload.get("command") == "ping":
            return {"response": "pong"}
        if payload.get("command") == "close":
            logger.info("Received close command from backend. Shutting down agent...")
            shutdown_event.set()
            return {"status": "shutting down"}
        
        # Add more command handlers here
        return {"status": "ok"}
        
    except Exception as e:
        logger.error(f"Failed to decrypt/handle message: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}

async def agent_main():
    logger.info("agent_main() started")
    try:
        logger.info("Loading identity...")
        identity = load_or_create_identity()
        node_uid = identity["node_uid"]
        logger.info(f"✓ Agent initialized with node_uid: {node_uid}")
    except Exception as e:
        logger.error(f"✗ Failed to initialize identity: {e}", exc_info=True)
        logger.error("agent_main() exiting due to identity error")
        return

    logger.info("Entering main connection loop...")
    
    loop_count = 0
    while True:
        loop_count += 1
        logger.info(f"Loop iteration #{loop_count}")
        try:
            if shutdown_event.is_set():
                logger.info("Shutdown event set. Exiting agent main loop.")
                break

            logger.info("Preparing connection...")
            sys.stdout.flush()
            sys.stderr.flush()
            ws = None
            
            logger.info("Creating SSL context...")
            sys.stdout.flush()
            sys.stderr.flush()
            try:
                ssl_ctx = ssl.create_default_context()
                logger.info("✓ SSL context created")
                sys.stdout.flush()
                sys.stderr.flush()
            except Exception as ssl_error:
                logger.error(f"✗ Failed to create SSL context: {ssl_error}", exc_info=True)
                sys.stdout.flush()
                sys.stderr.flush()
                raise
            
            logger.info(f"Server URL template: {AGENT_CONFIG['server_url']}")
            logger.info(f"Node UID: {node_uid}")
            logger.info(f"Node UID type: {type(node_uid)}")
            
            try:
                ws_url = AGENT_CONFIG["server_url"].format(serverid=node_uid)
                logger.info(f"✓ Formatted WebSocket URL: {ws_url}")
            except Exception as format_error:
                logger.error(f"✗ Failed to format server URL: {format_error}", exc_info=True)
                logger.error(f"  Server URL template: {AGENT_CONFIG['server_url']}")
                logger.error(f"  Node UID: {node_uid}")
                raise
            
            logger.info(f"→ Connecting to {ws_url}...")
            
        except Exception as loop_setup_error:
            logger.error(f"✗ Error in connection setup: {loop_setup_error}", exc_info=True)
            await asyncio.sleep(AGENT_CONFIG["reconnect_delay"])
            continue

        try:

            async with websockets.connect(
                ws_url,
                ssl=ssl_ctx,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=10
            ) as ws:
                logger.info(f"✓ Connected to backend")

                # Step 1: Send hello with agent public key
                agent_pubkey_b64 = base64.b64encode(
                    crypto_utils.serialize_public_key(identity["public_key"])
                ).decode()

                hello_payload = {
                    "action": "hello",
                    "agent_public_key": agent_pubkey_b64
                }
                logger.info("→ Sending hello...")
                await ws.send(json.dumps(hello_payload))

                # Wait for backend public key response
                logger.info("← Waiting for backend public key...")
                resp = await asyncio.wait_for(ws.recv(), timeout=AGENT_CONFIG["connection_timeout"])
                resp_data = json.loads(resp)
                logger.info(f"← Received: {resp_data}")

                if resp_data.get("status") != "ok":
                    logger.error(f"Hello failed: {resp_data}")
                    await asyncio.sleep(AGENT_CONFIG["reconnect_delay"])
                    continue

                backend_pubkey_b64 = resp_data.get("backend_public_key")
                if not backend_pubkey_b64:
                    logger.error("No backend public key received")
                    await asyncio.sleep(AGENT_CONFIG["reconnect_delay"])
                    continue

                # Save backend public key
                panel_pubkey_bytes = base64.b64decode(backend_pubkey_b64)
                keys_dir = Path("keys")
                keys_dir.mkdir(exist_ok=True)
                backend_pubkey_path = keys_dir / "backend_public.pem"

                with open(backend_pubkey_path, "wb") as f:
                    f.write(panel_pubkey_bytes)
                os.chmod(backend_pubkey_path, 0o644)

                panel_pubkey = crypto_utils.load_public_key(panel_pubkey_bytes)
                identity["backend_public_key"] = panel_pubkey
                logger.info("✓ Backend public key saved")

                # Step 2: Send encrypted registration
                reg_payload = {
                    "action": "register",
                    "serverid": identity["node_uid"]
                }

                logger.info("→ Sending encrypted registration...")
                enc = crypto_utils.encrypt_payload(reg_payload, panel_pubkey)
                await ws.send(json.dumps(enc))

                # Wait for encrypted approval
                logger.info("← Waiting for approval...")
                resp = await asyncio.wait_for(ws.recv(), timeout=AGENT_CONFIG["connection_timeout"])
                resp_data = json.loads(resp)
                logger.info(f"← Received approval response")

                # Decrypt approval
                approval = crypto_utils.decrypt_payload(
                    resp_data["cryptdata"],
                    resp_data["data"],
                    identity["private_key"]
                )
                logger.info(f"✓ Decrypted approval: {approval}")

                agent_id = approval.get("node_id")
                code = approval.get("code")
                if agent_id and code:
                    save_agent_id(agent_id, code)
                    identity["agent_id"] = agent_id
                    identity["code"] = code
                    logger.info(f"✓✓✓ REGISTERED as {agent_id} with code: {code}")
                    # After successful registration, attempt to resend any queued responses
                    try:
                        pending = _load_pending_responses()
                        if pending:
                            logger.info(f"Found {len(pending)} queued responses - attempting resend...")
                            sent = []
                            for resp in pending:
                                try:
                                    await ws.send(json.dumps(resp))
                                    sent.append(resp)
                                except Exception as e:
                                    logger.warning(f"Failed to resend queued response {resp.get('request_id')}: {e}")
                            # Remove sent responses from queue
                            if sent:
                                remaining = [r for r in pending if r not in sent]
                                _save_pending_responses(remaining)
                                logger.info(f"Resent {len(sent)} queued responses, {len(remaining)} remaining")
                    except Exception as e:
                        logger.warning(f"Error while attempting to resend queued responses: {e}")
                else:
                    logger.error("Registration incomplete - no node_id or code received")
                    await asyncio.sleep(AGENT_CONFIG["reconnect_delay"])
                    continue

                # Step 3: Main message loop (handle code verification and other messages)
                logger.info("Entering main message loop (with code verification support)...")
                while True:
                    try:
                        msg = await asyncio.wait_for(ws.recv(), timeout=300)
                        logger.debug(f"[DEBUG] WebSocket message received: {repr(msg)}")
                        logger.info(f"[WS] Raw message received: {msg}")
                        # Extra debug: log every message received
                        try:
                            msg_data = json.loads(msg)
                        except Exception as e:
                            logger.warning(f"Received non-JSON message: {e}")
                            continue
                        logger.info(f"[WS] Decoded message: {msg_data}")
                        logger.debug(f"[DEBUG] Message keys: {list(msg_data.keys())}")

                        # --- Handle code verification requests ---
                        if msg_data.get("type") == "verify_code":
                            received_code = msg_data.get("code")
                            verification_id = msg_data.get("verification_id")

                            logger.info(f"[VERIFY] Verification request - ID: {verification_id}, Code: {received_code}")

                            # Always reload code from disk for verification
                            try:
                                with open(AGENT_CONFIG["agent_id_file"], "r") as f:
                                    agent_data = json.load(f)
                                current_code = agent_data.get("code")
                            except Exception as e:
                                logger.warning(f"[VERIFY] Failed to load code from file: {e}")
                                agent_data = {}
                                current_code = identity.get("code")

                            logger.info(f"[VERIFY] Comparing codes - Received: '{received_code}', Expected: '{current_code}'")

                            if received_code == current_code:
                                result = "success"
                                valid = True
                                logger.info("[VERIFY] ✓ Code verified successfully!")
                            else:
                                result = "fail"
                                valid = False
                                logger.warning(f"[VERIFY] ✗ Code verification failed!")

                            # Update only the 'valid' field in agent_id.json, do not mutate the loaded payload in memory
                            try:
                                with open(AGENT_CONFIG["agent_id_file"], "r") as f:
                                    file_data = json.load(f)
                                file_data["valid"] = valid
                                with open(AGENT_CONFIG["agent_id_file"], "w") as f:
                                    json.dump(file_data, f)
                                logger.info(f"[VERIFY] Updated agent_id.json with valid={valid}")
                            except Exception as e:
                                logger.warning(f"[VERIFY] Failed to update agent_id.json with valid: {e}")

                            # Send response with verification_id (do NOT include 'valid')
                            response = {
                                "type": "verify_code_result",
                                "result": result,
                                "verification_id": verification_id
                            }

                            logger.info(f"[VERIFY] Sending response: {response}")
                            await _try_send_or_queue(ws, response)
                            logger.info("[VERIFY] Response sent/queued to backend")
                            continue

                        # --- Handle API bridge requests (from backend middleware) ---
                        if msg_data.get("type") == "api_request":
                            api = msg_data.get("api")
                            payload = msg_data.get("payload") or {}
                            request_id = msg_data.get("request_id")
                            logger.info(f"[API_PROXY] Received API request: {api} (ID: {request_id}) with payload keys: {list(payload.keys())}")

                            # API to module mapping:
                            #   - collect_metrics: metrics (system metrics)
                            #   - list_files, upload_file, create_directory, delete, rename, read_file, write_file: file operations
                            #   - terminal_open: terminal (persistent terminal session)
                            #   - nlb_status: nlb (node load balancing)
                            from functions import metrics, terminal, file_ops, nlb

                            try:
                                # Metrics API
                                if api == "collect_metrics":
                                    result = await metrics.collect_metrics()
                                    await _try_send_or_queue(ws, {
                                        "type": "api_response",
                                        "api": api,
                                        "request_id": request_id,
                                        "result": result
                                    })
                                    logger.info(f"[API_PROXY] Sent/Queued API response for {api}")
                                
                                # File Manager APIs
                                elif api == "list_files":
                                    path = payload.get("path", ".")
                                    logger.info(f"[API_PROXY] Calling file_ops.list_files with path: {path}")
                                    result = await file_ops.list_files(path)
                                    logger.info(f"[API_PROXY] file_ops.list_files returned: {result.keys() if isinstance(result, dict) else type(result)}")
                                    if isinstance(result, dict) and 'error' in result:
                                        logger.error(f"[API_PROXY] list_files error: {result['error']}")
                                    await _try_send_or_queue(ws, {
                                        "type": "api_response",
                                        "api": api,
                                        "request_id": request_id,
                                        "result": result
                                    })
                                    logger.info(f"[API_PROXY] Sent/Queued API response for {api}")
                                
                                elif api == "upload_file":
                                    path = payload.get("path")
                                    file_name = payload.get("file_name")
                                    file_bytes = payload.get("file_bytes")
                                    # Decode base64 if needed (base64 already imported at module level)
                                    if file_bytes and isinstance(file_bytes, str):
                                        file_bytes = base64.b64decode(file_bytes)
                                    result = await file_ops.upload_file(path, file_name, file_bytes)
                                    await _try_send_or_queue(ws, {
                                        "type": "api_response",
                                        "api": api,
                                        "request_id": request_id,
                                        "result": result
                                    })
                                    logger.info(f"[API_PROXY] Sent/Queued API response for {api}")
                                
                                elif api == "create_directory":
                                    path = payload.get("path")
                                    result = await file_ops.create_directory(path)
                                    await _try_send_or_queue(ws, {
                                        "type": "api_response",
                                        "api": api,
                                        "request_id": request_id,
                                        "result": result
                                    })
                                    logger.info(f"[API_PROXY] Sent/Queued API response for {api}")
                                
                                elif api == "delete":
                                    path = payload.get("path")
                                    result = await file_ops.delete(path)
                                    await _try_send_or_queue(ws, {
                                        "type": "api_response",
                                        "api": api,
                                        "request_id": request_id,
                                        "result": result
                                    })
                                    logger.info(f"[API_PROXY] Sent/Queued API response for {api}")
                                
                                elif api == "rename":
                                    old_path = payload.get("old_path")
                                    new_path = payload.get("new_path")
                                    result = await file_ops.rename(old_path, new_path)
                                    await _try_send_or_queue(ws, {
                                        "type": "api_response",
                                        "api": api,
                                        "request_id": request_id,
                                        "result": result
                                    })
                                    logger.info(f"[API_PROXY] Sent/Queued API response for {api}")
                                
                                elif api == "read_file":
                                    path = payload.get("path")
                                    logger.info(f"[API_PROXY] Calling file_ops.read_file with path: {path}")
                                    result = await file_ops.read_file(path)
                                    logger.info(f"[API_PROXY] file_ops.read_file returned: {result.keys() if isinstance(result, dict) else type(result)}")
                                    if isinstance(result, dict) and 'error' in result:
                                        logger.error(f"[API_PROXY] read_file error: {result['error']}")
                                    await _try_send_or_queue(ws, {
                                        "type": "api_response",
                                        "api": api,
                                        "request_id": request_id,
                                        "result": result
                                    })
                                    logger.info(f"[API_PROXY] Sent/Queued API response for {api}")
                                
                                elif api == "write_file":
                                    path = payload.get("path")
                                    content = payload.get("content")
                                    result = await file_ops.write_file(path, content)
                                    await _try_send_or_queue(ws, {
                                        "type": "api_response",
                                        "api": api,
                                        "request_id": request_id,
                                        "result": result
                                    })
                                    logger.info(f"[API_PROXY] Sent/Queued API response for {api}")
                                
                                # Terminal API (streaming)
                                elif api == "terminal_open":
                                    logger.info(f"[API_PROXY] Starting persistent terminal session...")
                                    await terminal.terminal_ws_session(ws, payload)
                                    logger.info(f"[API_PROXY] Terminal session ended.")
                                
                                # NLB API
                                elif api == "nlb_status":
                                    result = await nlb.status(payload)
                                    await _try_send_or_queue(ws, {
                                        "type": "api_response",
                                        "api": api,
                                        "request_id": request_id,
                                        "result": result
                                    })
                                    logger.info(f"[API_PROXY] Sent/Queued API response for {api}")
                                
                                else:
                                    result = {"error": f"Unknown API: {api}"}
                                    await _try_send_or_queue(ws, {
                                        "type": "api_response",
                                        "api": api,
                                        "request_id": request_id,
                                        "result": result
                                    })
                                    logger.warning(f"[API_PROXY] Unknown API requested: {api}")
                            
                            except Exception as e:
                                logger.error(f"[API_PROXY] Error handling {api}: {e}", exc_info=True)
                                result = {"error": str(e)}
                                await _try_send_or_queue(ws, {
                                    "type": "api_response",
                                    "api": api,
                                    "request_id": request_id,
                                    "result": result
                                })
                                logger.info(f"[API_PROXY] Sent/Queued error response for {api}")
                            continue

                        # Normal timeout for keepalive
                        logger.debug("[DEBUG] Timeout waiting for message (keepalive)")
                        continue
                    except websockets.exceptions.ConnectionClosed:
                        logger.warning("WebSocket connection closed")
                        break
                        
        except asyncio.TimeoutError:
            logger.error("✗ Connection timeout")
        except websockets.exceptions.WebSocketException as e:
            logger.error(f"✗ WebSocket error: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"✗ Connection error: {e}", exc_info=True)
        finally:
            if ws:
                try:
                    await ws.close()
                except:
                    pass
        
            if not shutdown_event.is_set():
                logger.info(f"Reconnecting in {AGENT_CONFIG['reconnect_delay']} seconds...")
                await asyncio.sleep(AGENT_CONFIG["reconnect_delay"])
    
    logger.info("agent_main() loop exited - this should only happen on shutdown")

if __name__ == "__main__":
    import sys
    
    # Verify critical imports are available
    try:
        import websockets
        import ssl
        import psutil
        logger.info("✓ All critical imports verified")
    except ImportError as e:
        logger.error(f"✗ Missing critical import: {e}")
        print(f"\n✗ ERROR: Missing required module: {e}")
        print("Please run: pip install -r requirements.txt")
        sys.exit(1)
    
    # Log current configuration for debugging
    logger.info("=" * 60)
    logger.info("AGENT CONFIGURATION")
    logger.info("=" * 60)
    logger.info(f"Server URL: {AGENT_CONFIG.get('server_url')}")
    logger.info(f"Reconnect delay: {AGENT_CONFIG.get('reconnect_delay')}")
    logger.info(f"Connection timeout: {AGENT_CONFIG.get('connection_timeout')}")
    logger.info(f"Working directory: {os.getcwd()}")
    logger.info(f"server_config.json exists: {Path('server_config.json').exists()}")
    if Path('server_config.json').exists():
        try:
            with open('server_config.json', 'r') as f:
                logger.info(f"server_config.json contents: {f.read()}")
        except Exception as e:
            logger.error(f"Could not read server_config.json: {e}")
    logger.info("=" * 60)
    
    if '--stop' in sys.argv:
        try:
            import psutil
        except ImportError:
            print("psutil is required for --stop. Please install with 'pip install psutil'.")
            sys.exit(1)
        stop_all_agents()
        sys.exit(0)

    # Run in background unless --foreground flag is passed
    if '--foreground' not in sys.argv and '--fg' not in sys.argv:
        ensure_background()

    write_pid()
    
    # Set up exception handler for asyncio to catch unhandled exceptions
    def exception_handler(loop, context):
        logger.error("=" * 60)
        logger.error("UNHANDLED EXCEPTION IN ASYNCIO EVENT LOOP")
        logger.error("=" * 60)
        logger.error(f"Context: {context}")
        exception = context.get('exception')
        if exception:
            logger.error(f"Exception type: {type(exception).__name__}")
            logger.error(f"Exception: {exception}", exc_info=exception)
        logger.error("=" * 60)
    
    try:
        logger.info("Starting agent main loop...")
        loop = asyncio.new_event_loop()
        loop.set_exception_handler(exception_handler)
        asyncio.set_event_loop(loop)
        loop.run_until_complete(agent_main())
        loop.close()
    except KeyboardInterrupt:
        logger.info("Node agent stopped by user")
        print("\nNode agent stopped.")
    except ImportError as e:
        logger.error(f"✗ Missing required module: {e}", exc_info=True)
        logger.error("Please ensure all requirements are installed: pip install -r requirements.txt")
        print(f"\n✗ ERROR: Missing required module: {e}")
        print("Please run: pip install -r requirements.txt")
        sys.exit(1)
    except Exception as e:
        logger.error(f"✗ Fatal error in agent main: {e}", exc_info=True)
        print(f"\n✗ FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        remove_pid()
