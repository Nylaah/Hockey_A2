import socket
import threading
import queue


class ClientConnection:
    """
    Encapsule un socket client avec un thread d'envoi dédié.
    Tous les appels à send() sont non-bloquants : le message est mis en file
    et envoyé par un thread séparé. Cela évite tout blocage dans broadcast_all.
    """

    def __init__(self, conn: socket.socket, addr):
        self._conn  = conn
        self._addr  = addr
        # Désactive l'algorithme de Nagle : les petits paquets (POS, BALL…)
        # sont envoyés immédiatement sans attendre d'en accumuler d'autres.
        conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self._queue: queue.Queue[str | None] = queue.Queue()

        self._send_thread = threading.Thread(target=self._send_loop, daemon=True)
        self._send_thread.start()

    def _send_loop(self):
        while True:
            try:
                msg = self._queue.get(timeout=1.0)
                if msg is None:   # signal d'arrêt
                    break
                self._conn.sendall((msg + "\n").encode("utf-8"))
            except queue.Empty:
                continue
            except Exception:
                break

    def send(self, msg: str):
        """Enqueue un message (non-bloquant)."""
        self._queue.put(msg)

    def recv(self, size: int) -> bytes:
        return self._conn.recv(size)

    def close(self):
        self._queue.put(None)   # arrête le thread d'envoi
        try:
            self._conn.close()
        except Exception:
            pass

    @property
    def addr(self):
        return self._addr
