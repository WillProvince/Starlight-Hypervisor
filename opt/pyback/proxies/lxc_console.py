"""
LXC console WebSocket proxy handler.

This module provides WebSocket proxy functionality for LXC container console access,
managing PTY connections and terminal I/O.
"""

import os
import pty
import fcntl
import struct
import termios
import logging
import asyncio
import libvirt
from aiohttp import web
from xml.etree import ElementTree as ET

from ..utils.libvirt_connection import get_connection, get_domain_by_name

logger = logging.getLogger(__name__)


async def lxc_console_handler(request):
    """
    Handles the WebSocket connection from the browser and proxies to the LXC console
    via nsenter command with PTY. This bridges the WebSocket protocol to the LXC console.
    """
    container_name = request.match_info.get('name')
    
    if not container_name:
        return web.Response(status=400, text="Invalid container name specified.")
    
    # 1. Initiate WebSocket connection with the client (browser)
    ws_client = web.WebSocketResponse()
    await ws_client.prepare(request)
    logger.info(f"LXC Console: WebSocket connection opened for container {container_name}.")
    
    # 2. Get container PID
    try:
        # First, get the container's init PID
        conn = get_connection('lxc')
        if not conn:
            error_msg = "Failed to connect to LXC driver"
            logger.error(f"LXC Console: {error_msg}")
            await ws_client.send_str(f"Error: {error_msg}\r\n")
            await ws_client.close(code=1006, message=b"Failed to connect to LXC.")
            return ws_client
        
        domain = get_domain_by_name(conn, container_name)
        if not domain:
            error_msg = f"Container {container_name} not found"
            logger.error(f"LXC Console: {error_msg}")
            conn.close()
            await ws_client.send_str(f"Error: {error_msg}\r\n")
            await ws_client.close(code=1006, message=b"Container not found.")
            return ws_client
        
        if not domain.isActive():
            error_msg = f"Container {container_name} is not running"
            logger.error(f"LXC Console: {error_msg}")
            conn.close()
            await ws_client.send_str(f"Error: {error_msg}\r\n")
            await ws_client.close(code=1006, message=b"Container not running.")
            return ws_client
        
        # Get the domain ID first
        domain_id = domain.ID()
        
        # Get the actual container init PID from XML or cgroup
        # For LXC, domain.ID() may not be reliable, so we parse the domain XML
        xml_desc = domain.XMLDesc(0)
        root = ET.fromstring(xml_desc)
        
        # Try to find PID from domain XML metadata
        init_pid = None
        
        # Method 1: Check if there's a PID in the domain's running state
        # For LXC, we need to find the actual init process
        # We'll search for it in /sys/fs/cgroup or use virsh commands
        
        conn.close()
        
        # Method 2: Find the container's init PID from systemd-machined
        try:
            # Get the machine name from libvirt - it's lxc-<domain_id>-<name>
            machine_name = f"lxc-{domain_id}-{container_name}"
            logger.info(f"LXC Console: Attempting machinectl with machine name: {machine_name}")
            
            # Use machinectl to get the leader PID
            process_info = await asyncio.create_subprocess_exec(
                'machinectl', 'show', '-p', 'Leader', machine_name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process_info.communicate()
            
            logger.info(f"LXC Console: machinectl returned code {process_info.returncode}, stdout: {stdout.decode()}, stderr: {stderr.decode()}")
            
            if process_info.returncode == 0:
                output = stdout.decode('utf-8').strip()
                # Output format: "Leader=12345"
                if 'Leader=' in output:
                    init_pid = int(output.split('=')[1])
                    logger.info(f"LXC Console: Found container init PID via machinectl: {init_pid}")
                else:
                    logger.warning(f"LXC Console: machinectl succeeded but no Leader= in output: {output}")
            else:
                logger.warning(f"LXC Console: machinectl failed with return code {process_info.returncode}")
        except Exception as e:
            logger.warning(f"LXC Console: Could not get PID from machinectl: {e}")
        
        # Method 3: Fallback - search for the init process in cgroup
        if not init_pid:
            try:
                # Look for the container's cgroup and find init PID
                # Path format: /sys/fs/cgroup/machine.slice/machine-lxc\x2d{domain_id}\x2d{container_name}.scope/cgroup.procs
                cgroup_path = f"/sys/fs/cgroup/machine.slice/machine-lxc\\x2d{domain_id}\\x2d{container_name}.scope/cgroup.procs"
                if os.path.exists(cgroup_path):
                    with open(cgroup_path, 'r') as f:
                        pids = f.read().strip().split('\n')
                        if pids and pids[0]:
                            init_pid = int(pids[0])  # First PID should be init
                            logger.info(f"LXC Console: Found container init PID from cgroup: {init_pid}")
            except Exception as e:
                logger.warning(f"LXC Console: Could not get PID from cgroup: {e}")
        
        # Method 4: Last resort - use domain ID
        if not init_pid:
            init_pid = domain_id
            logger.warning(f"LXC Console: Using domain ID as PID (may not be correct): {init_pid}")
        
        if not init_pid or init_pid <= 0:
            error_msg = f"Could not get PID for container {container_name}"
            logger.error(f"LXC Console: {error_msg}")
            await ws_client.send_str(f"Error: {error_msg}\r\n")
            await ws_client.close(code=1006, message=b"Could not get container PID.")
            return ws_client
        
        logger.info(f"LXC Console: Container {container_name} will use PID: {init_pid}")
        
    except Exception as e:
        logger.error(f"LXC Console: Failed to get container info: {e}")
        await ws_client.send_str(f"Error: {e}\r\n")
        await ws_client.close(code=1006, message=b"Failed to get container info.")
        return ws_client
    
    # 3. Create PTY and start nsenter with it
    master_fd = None
    process = None
    
    try:
        # Create a PTY pair
        master_fd, slave_fd = pty.openpty()
        
        # Set master to non-blocking mode
        flags = fcntl.fcntl(master_fd, fcntl.F_GETFL)
        fcntl.fcntl(master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
        
        # Use script command to wrap nsenter - this properly handles PTY allocation
        # script -qfc runs a command with a PTY and exits immediately
        # We set the environment variables that /bin/sh needs to work properly
        cmd = f"script -qfc 'nsenter -t {init_pid} -a env TERM=xterm-256color PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin HOME=/root PS1=\"/ # \" /bin/sh' /dev/null"
        
        process = await asyncio.create_subprocess_shell(
            cmd,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd
        )
        
        # Close slave_fd in parent - child has its own copy
        os.close(slave_fd)
        
        logger.info(f"LXC Console: Started nsenter shell for {container_name} (PID: {process.pid})")
        
    except Exception as e:
        logger.error(f"LXC Console: Failed to create PTY and start nsenter: {e}")
        if master_fd is not None:
            try:
                os.close(master_fd)
            except:
                pass
        await ws_client.send_str(f"Error: Failed to start console: {e}\r\n")
        await ws_client.close(code=1006, message=b"Failed to start console.")
        return ws_client
    
    bytes_sent = 0
    bytes_received = 0
    
    # Task 1: Read from PTY and send to Client (WebSocket)
    async def pty_to_client():
        nonlocal bytes_sent
        try:
            while not ws_client.closed:
                # Read data from PTY (non-blocking)
                try:
                    data = os.read(master_fd, 8192)
                    if not data:
                        logger.debug("LXC Console: PTY closed.")
                        break
                    
                    bytes_sent += len(data)
                    
                    # Send the data through the WebSocket as text
                    try:
                        await ws_client.send_str(data.decode('utf-8', errors='replace'))
                    except Exception as e:
                        logger.error(f"LXC Console: Error sending data to client: {e}")
                        break
                        
                except BlockingIOError:
                    # No data available, sleep briefly
                    await asyncio.sleep(0.01)
                except OSError as e:
                    logger.debug(f"LXC Console: PTY read error (process may have exited): {e}")
                    break
                
        except asyncio.CancelledError:
            logger.debug("LXC Console: pty_to_client task cancelled.")
        except Exception as e:
            logger.error(f"LXC Console: pty_to_client task error: {e}")
        finally:
            logger.debug(f"LXC Console: pty_to_client task ended. Total bytes sent: {bytes_sent}")
    
    # Task 2: Read from Client (WebSocket) and write to PTY
    async def client_to_pty():
        nonlocal bytes_received
        try:
            async for msg in ws_client:
                if msg.type == web.WSMsgType.TEXT:
                    # Received text data from the client, write it to PTY
                    data = msg.data.encode('utf-8')
                    bytes_received += len(data)
                    
                    try:
                        os.write(master_fd, data)
                    except Exception as e:
                        logger.error(f"LXC Console: Error writing to PTY: {e}")
                        break
                    
                elif msg.type == web.WSMsgType.BINARY:
                    logger.warning(f"LXC Console: Received binary message (expected text)")
                    
                elif msg.type == web.WSMsgType.CLOSE:
                    logger.debug("LXC Console: Client sent close frame.")
                    break
                    
        except asyncio.CancelledError:
            logger.debug("LXC Console: client_to_pty task cancelled.")
        except Exception as e:
            logger.error(f"LXC Console: client_to_pty task error: {e}")
        finally:
            logger.debug(f"LXC Console: client_to_pty task ended. Total bytes received: {bytes_received}")
    
    # Run the two tasks concurrently until one of them finishes
    pty_task = asyncio.create_task(pty_to_client())
    client_task = asyncio.create_task(client_to_pty())
    
    try:
        # Wait for either the client or the PTY side to close the connection
        done, pending = await asyncio.wait(
            [pty_task, client_task],
            return_when=asyncio.FIRST_COMPLETED
        )
        
        # Cancel the remaining task
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
                
    except Exception as e:
        logger.error(f"LXC Console: Exception in main proxy loop: {e}")
    finally:
        # Close connections
        try:
            if master_fd is not None:
                os.close(master_fd)
        except Exception as e:
            logger.warning(f"LXC Console: Error closing PTY: {e}")
        
        try:
            if process is not None:
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=2.0)
                except asyncio.TimeoutError:
                    process.kill()
                    await process.wait()
        except Exception as e:
            logger.warning(f"LXC Console: Error terminating process: {e}")
            
        if not ws_client.closed:
            await ws_client.close()
    
    logger.debug(f"LXC Console: Proxy finished for {container_name}. Sent: {bytes_sent}, Received: {bytes_received}")
    return ws_client

