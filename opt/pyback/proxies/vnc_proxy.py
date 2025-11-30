"""
VNC WebSocket proxy handler.

This module provides WebSocket proxy functionality for VNC connections,
bridging browser WebSocket connections to QEMU VNC TCP sockets.
"""

import logging
import asyncio
from aiohttp import web

logger = logging.getLogger(__name__)


async def vnc_proxy_handler(request):
    """
    Handles the WebSocket connection from the browser and proxies raw TCP data 
    to the QEMU VNC server on localhost. This bridges the protocols.
    """
    vnc_port = request.match_info.get('port')
    
    if not vnc_port or not vnc_port.isdigit():
        return web.Response(status=400, text="Invalid VNC port specified.")

    vnc_port = int(vnc_port)
    vnc_host = '127.0.0.1'
    
    # 1. Initiate WebSocket connection with the client (browser)
    ws_client = web.WebSocketResponse()
    await ws_client.prepare(request)
    logger.debug(f"VNC: WebSocket connection opened for port {vnc_port}.")

    # 2. Open raw TCP socket connection to the local QEMU VNC server
    try:
        qemu_reader, qemu_writer = await asyncio.open_connection(vnc_host, vnc_port)
        logger.debug(f"VNC: TCP connection established to QEMU VNC at {vnc_host}:{vnc_port}.")
    except ConnectionRefusedError:
        logger.error(f"VNC: Connection refused to QEMU VNC at {vnc_host}:{vnc_port}. Is the VM running?")
        await ws_client.close(code=1006, message=b"Connection refused by VNC server (QEMU).")
        return ws_client
    except Exception as e:
        logger.error(f"VNC: Failed to establish TCP connection to QEMU: {e}")
        await ws_client.close(code=1006, message=b"Internal proxy error.")
        return ws_client

    # 3. Create concurrent tasks for two-way proxying
    
    bytes_sent = 0
    bytes_received = 0
    
    # Task 1: Read from QEMU (TCP) and send to Client (WebSocket)
    async def qemu_to_client():
        nonlocal bytes_sent
        try:
            while not ws_client.closed:
                # Read raw data from QEMU VNC server
                data = await qemu_reader.read(8192)  # Increased buffer size
                if not data:
                    logger.debug("VNC: QEMU closed the TCP connection.")
                    break
                
                bytes_sent += len(data)
                if bytes_sent <= 100:  # Log first few bytes for debugging
                    logger.debug(f"VNC: Sending {len(data)} bytes to client (total: {bytes_sent})")
                
                # Send the raw data through the WebSocket as binary
                await ws_client.send_bytes(data)
                
        except asyncio.CancelledError:
            logger.debug("VNC: qemu_to_client task cancelled.")
        except Exception as e:
            logger.error(f"VNC: qemu_to_client task error: {e}")
        finally:
            logger.debug(f"VNC: qemu_to_client task ended. Total bytes sent: {bytes_sent}")

    # Task 2: Read from Client (WebSocket) and send to QEMU (TCP)
    async def client_to_qemu():
        nonlocal bytes_received
        try:
            async for msg in ws_client:
                if msg.type == web.WSMsgType.BINARY:
                    # Received binary data from the client, write it to QEMU's TCP socket
                    bytes_received += len(msg.data)
                    if bytes_received <= 100:  # Log first few bytes for debugging
                        logger.debug(f"VNC: Received {len(msg.data)} bytes from client (total: {bytes_received})")
                    
                    qemu_writer.write(msg.data)
                    await qemu_writer.drain()
                    
                elif msg.type == web.WSMsgType.TEXT:
                    logger.warning(f"VNC: Received text message (expected binary): {msg.data}")
                    
                elif msg.type == web.WSMsgType.CLOSE:
                    logger.debug("VNC: Client sent close frame.")
                    break
                    
        except asyncio.CancelledError:
            logger.debug("VNC: client_to_qemu task cancelled.")
        except Exception as e:
            logger.error(f"VNC: client_to_qemu task error: {e}")
        finally:
            logger.debug(f"VNC: client_to_qemu task ended. Total bytes received: {bytes_received}")
    
    # Run the two tasks concurrently until one of them finishes
    qemu_task = asyncio.create_task(qemu_to_client())
    client_task = asyncio.create_task(client_to_qemu())

    try:
        # Wait for either the client or the QEMU side to close the connection
        done, pending = await asyncio.wait(
            [qemu_task, client_task],
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
        logger.error(f"VNC: Exception in main proxy loop: {e}")
    finally:
        # Close connections
        try:
            qemu_writer.close()
            await qemu_writer.wait_closed()
        except Exception as e:
            logger.warning(f"VNC: Error closing QEMU writer: {e}")
            
        if not ws_client.closed:
            await ws_client.close()

    logger.debug(f"VNC: Proxy finished for port {vnc_port}. Sent: {bytes_sent}, Received: {bytes_received}")
    return ws_client
