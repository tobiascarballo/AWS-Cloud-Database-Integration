# src/modules/observer.py
import threading
import json
import socket
import logging

logger = logging.getLogger(__name__)  # __name__ = 'modules.observer'

class NotificationManager:
    """
    Implementa el Patrón Observer.
    Gestiona una lista de suscriptores (observers) y les notifica cuando ocurre un evento (ej: un 'set' en la DB).
    """

    def __init__(self):
        self._observers = []  # Lista de sockets de clientes
        self._lock = threading.Lock()  # Candado para proteger la lista
        logger.info("NotificationManager (Observer) inicializado.")

    def subscribe(self, client_socket, client_uuid):
        """Añade un nuevo suscriptor (socket) a la lista."""
        with self._lock:
            if client_socket not in self._observers:
                self._observers.append(client_socket)
                logger.info(f"OBSERVER: Nuevo suscriptor (UUID: {client_uuid}). Total: {len(self._observers)}")
            else:
                logger.warning(f"OBSERVER: Intento de suscribir a un cliente ya suscrito (UUID: {client_uuid}).")

    def unsubscribe(self, client_socket):
        """Elimina un suscriptor (socket) de la lista."""
        with self._lock:
            if client_socket in self._observers:
                self._observers.remove(client_socket)
                logger.info(f"OBSERVER: Suscriptor desconectado. Total: {len(self._observers)}")

    def _send_notification(self, message_bytes):
        """
        Envía datos a todos los suscriptores.
        Se ejecuta en un hilo separado para no bloquear el flujo principal.
        """
        with self._lock:
            if not self._observers:
                return

            logger.info(f"OBSERVER: Notificando a {len(self._observers)} suscriptor(es)...")
            for obs_socket in list(self._observers):
                try:
                    obs_socket.sendall(message_bytes)
                except socket.error as e:
                    logger.warning(f"OBSERVER: Error enviando a suscriptor ({e}). Eliminándolo.")
                    self._observers.remove(obs_socket)

    def notify(self, data, encoder_class):
        """
        Envía datos (notificación) a todos los suscriptores en un hilo separado.
        Si un envío falla, elimina al suscriptor de la lista.
        """
        try:
            message_bytes = json.dumps(
                {"EVENT": "update", "DATA": data}, cls=encoder_class
            ).encode("utf-8")
        except Exception as e:
            logger.error(f"OBSERVER: No se pudo codificar el mensaje de notificación: {e}", exc_info=True)
            return

        # Notificación asíncrona (no bloquea al servidor principal)
        notify_thread = threading.Thread(target=self._send_notification, args=(message_bytes,), daemon=True)
        notify_thread.start()