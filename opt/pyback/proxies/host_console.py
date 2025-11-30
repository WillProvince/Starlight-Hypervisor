"""
Host console WebSocket proxy handler.

This module provides WebSocket proxy functionality for host system console access,
managing PTY connections and terminal I/O. Only accessible by root user.
"""

import os
import pty
import fcntl
import logging
import asyncio
from aiohttp import web

from ..auth.middleware import get_current_user

logger = logging.getLogger(__name__)

# Constants
BUFFER_SIZE = 8192
POLL_INTERVAL = 0.01  # 10ms


async def host_console_handler(request):
    """
    Handles the WebSocket connection from the browser and proxies to the host shell
    via PTY. This bridges the WebSocket protocol to a shell running on the host system.
    
    Only accessible by the root user.
    """
    # 1. Check if user is root
    current_user = get_current_user(request)
    if not current_user:
        return web.Response(status=401, text="Authentication required")
    
    username = current_user.get('username')
    if username != 'root':
        logger.warning(f"Host Console: Unauthorized access attempt by user '{username}'")
        return web.Response(status=403, text="Only root user can access host console")
    
    # 2. Initiate WebSocket connection with the client (browser)
    ws_client = web.WebSocketResponse()
    await ws_client.prepare(request)
    logger.info("Host Console: WebSocket connection opened for root user.")
    
    # 3. Create PTY and start shell
    master_fd = None
    process = None
    
    try:
        # Create a PTY pair
        master_fd, slave_fd = pty.openpty()
        
        # Set master to non-blocking mode
        flags = fcntl.fcntl(master_fd, fcntl.F_GETFL)
        fcntl.fcntl(master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
        
        # Start a bash shell with proper PTY
        cmd = "script -qfc 'env TERM=xterm-256color PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin HOME=/root PS1=\"\\u@\\h:\\w# \" /bin/bash' /dev/null"
        
        process = await asyncio.create_subprocess_shell(
            cmd,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd
        )
        
        # Close slave_fd in parent - child has its own copy
        os.close(slave_fd)
        
        logger.info(f"Host Console: Started bash shell (PID: {process.pid})")
        
    except OSError as e:
        logger.error(f"Host Console: Failed to create PTY and start shell: {e}")
        if master_fd is not None:
            try:
                os.close(master_fd)
            except OSError:
                pass
        await ws_client.send_str("Error: Failed to start console\r\n")
        await ws_client.close(code=1006, message=b"Failed to start console.")
        return ws_client
    except Exception as e:
        logger.error(f"Host Console: Unexpected error starting shell: {e}")
        if master_fd is not None:
            try:
                os.close(master_fd)
            except OSError:
                pass
        await ws_client.send_str("Error: Failed to start console\r\n")
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
                    data = os.read(master_fd, BUFFER_SIZE)
                    if not data:
                        logger.debug("Host Console: PTY closed.")
                        break
                    
                    bytes_sent += len(data)
                    
                    # Send the data through the WebSocket as text
                    try:
                        await ws_client.send_str(data.decode('utf-8', errors='replace'))
                    except Exception as e:
                        logger.error(f"Host Console: Error sending data to client: {e}")
                        break
                        
                except BlockingIOError:
                    # No data available, sleep briefly
                    await asyncio.sleep(POLL_INTERVAL)
                except OSError as e:
                    logger.debug(f"Host Console: PTY read error (process may have exited): {e}")
                    break
                
        except asyncio.CancelledError:
            logger.debug("Host Console: pty_to_client task cancelled.")
        except Exception as e:
            logger.error(f"Host Console: pty_to_client task error: {e}")
        finally:
            logger.debug(f"Host Console: pty_to_client task ended. Total bytes sent: {bytes_sent}")
    
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
                        logger.error(f"Host Console: Error writing to PTY: {e}")
                        break
                    
                elif msg.type == web.WSMsgType.BINARY:
                    logger.warning("Host Console: Received binary message (expected text)")
                    
                elif msg.type == web.WSMsgType.CLOSE:
                    logger.debug("Host Console: Client sent close frame.")
                    break
                    
        except asyncio.CancelledError:
            logger.debug("Host Console: client_to_pty task cancelled.")
        except Exception as e:
            logger.error(f"Host Console: client_to_pty task error: {e}")
        finally:
            logger.debug(f"Host Console: client_to_pty task ended. Total bytes received: {bytes_received}")
    
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
        logger.error(f"Host Console: Exception in main proxy loop: {e}")
    finally:
        # Close connections
        try:
            if master_fd is not None:
                os.close(master_fd)
        except OSError as e:
            logger.warning(f"Host Console: Error closing PTY: {e}")
        
        try:
            if process is not None:
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=2.0)
                except asyncio.TimeoutError:
                    process.kill()
                    await process.wait()
        except OSError as e:
            logger.warning(f"Host Console: Error terminating process: {e}")
            
        if not ws_client.closed:
            await ws_client.close()
    
    logger.debug(f"Host Console: Proxy finished. Sent: {bytes_sent}, Received: {bytes_received}")
    return ws_client
