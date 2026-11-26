import asyncio
from typing import Dict, Set, Any
from fastapi import WebSocket


class ConnectionManager:
    """
    Gestor desacoplado de conexiones WebSocket para salas de Monopoly en tiempo real.
    Permite notificar eventos a todos los clientes conectados a una partida (SRP).
    """

    def __init__(self):
        self._active_connections: Dict[int, Set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    def get_connected_count(self, game_id: int) -> int:
        return len(self._active_connections.get(game_id, set()))

    async def connect(self, game_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            if game_id not in self._active_connections:
                self._active_connections[game_id] = set()
            self._active_connections[game_id].add(websocket)

    async def disconnect(self, game_id: int, websocket: WebSocket) -> None:
        async with self._lock:
            if game_id in self._active_connections:
                self._active_connections[game_id].discard(websocket)
                if not self._active_connections[game_id]:
                    del self._active_connections[game_id]

    async def broadcast(self, game_id: int, event_type: str, data: Any = None) -> None:
        """Difunde un evento estructurado a todos los clientes conectados a la partida."""
        message = {
            "event": event_type,
            "game_id": game_id,
            "data": data or {},
        }
        conns: Set[WebSocket] = set()
        async with self._lock:
            if game_id in self._active_connections:
                conns = set(self._active_connections[game_id])

        dead_connections = []
        for ws in conns:
            try:
                await ws.send_json(message)
            except Exception:
                dead_connections.append(ws)

        if dead_connections:
            async with self._lock:
                if game_id in self._active_connections:
                    for ws in dead_connections:
                        self._active_connections[game_id].discard(ws)


connection_manager = ConnectionManager()


def broadcast_game_event_sync(game_id: int, event_type: str, data: Any = None) -> None:
    """Helper no bloqueante para emitir eventos WebSocket desde endpoints sincrónicos."""
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(connection_manager.broadcast(game_id, event_type, data))
    except RuntimeError:
        # No hay loop en ejecución (ej: pruebas unitarias síncronas puras)
        pass
