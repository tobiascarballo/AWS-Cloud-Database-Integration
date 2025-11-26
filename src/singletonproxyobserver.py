import socket #importar socket para conexiones
import sys # importar sys para sys.exit
import argparse # importar argparse para argumentos de linea de comando
import json # importar json para manejo de json
import uuid # importar uuid para generar ids unicos
import threading # importar threading para manejar hilos
import logging # importar logging para logs
from decimal import Decimal # importar Decimal para manejar decimales de dynamoDB

# 2 Importar los módulos
from modules.db_singleton import DatabaseSingleton
from modules.data_proxy import DataProxy
from modules.observer import NotificationManager

VERSION = "1.1-Refactor" # version del servidor

# Obtenemos un logger para este módulo
logger = logging.getLogger(__name__) # __name__ es: singletonproxyobserver

class DecimalEncoder(json.JSONEncoder): # define una clase que hereda el JSONEncoder 
    """Clase Helper para convertir Decimal a str en JSON."""
    def default(self, obj): # define default para sobreescribir el metodo
        if isinstance(obj, Decimal): # si el objeto es decimal
            return str(obj) # devuelve string
        return super(DecimalEncoder, self).default(obj) # devuelve metodo default del padre

class Server: # server para manejar los patrones
    """
    Clase principal del Servidor.
    Orquesta los patrones Singleton, Proxy y Observer.
    """
    def __init__(self, host, port): # constructor que recibe host y port    
        self.host = host # guarda el host 
        self.port = port # guarda el port
        
        logger.info("Inicializando componentes del servidor...")
        # DataProxy internamente obtendrá el Singleton
        self.data_proxy = DataProxy() # crea el proxy de datos
        self.notifier = NotificationManager() # crea el manager de notificaciones (observer)
        logger.info("--- Servidor listo para escuchar ---")

    def _send_response(self, conn, data, status_code=200): # funcion privada para enviar respuestas
        """Helper para enviar respuestas JSON al cliente."""
        try:
            # Usamos cls=DecimalEncoder para manejar los decimales de dynamo
            msg = json.dumps(data, cls=DecimalEncoder, indent=4).encode('utf-8') # convierte la info a json
            conn.sendall(msg) # envia la info al cliente
            logger.debug(f"Enviada respuesta (Status: {status_code})") 
        except socket.error as e: # error de socket 
            logger.warning(f"Error de socket al enviar respuesta: {e}")

    def handle_client_connection(self, conn, addr): # funcion para manejar la conexion del cliente
        """
        Esta función se ejecuta en un hilo separado por cada cliente, maneja el ciclo de vida completo de una conexión.
        """
        # Formato de log para saber quien es el cliente
        client_log_prefix = f"Cliente [{addr[0]}:{addr[1]}]" # prejifo del log
        logger.info(f"{client_log_prefix} - Conexión aceptada en hilo {threading.current_thread().name}") # log info
        
        is_subscriber = False # bandera para saber si es suscriptor
        client_uuid = "UUID_DESCONOCIDO" # uuid del cliente desconocido
        
        try:
            # Recibimos el request (máx 4096 bytes)
            request_raw = conn.recv(4096) # recibe info del cliente
            if not request_raw: # si no recibe nada
                logger.warning(f"{client_log_prefix} - Cliente desconectado sin enviar datos.") # mensaje de warning
                return

            data = json.loads(request_raw.decode('utf-8')) # decodifica la info recibida
            action = data.get("ACTION") # obtiene la accion del json
            client_uuid = data.get("UUID", client_uuid) # obtiene el uuid de json o usa el desconocido
            session_id = str(uuid.uuid4()) # genera un id de sesion unico
            
            logger.info(f"{client_log_prefix} (UUID: {client_uuid}) -> Acción solicitada: {action}") # log info
            
            #router de acciones
            if action == "get": # si la accion es get
                item_id = data.get("ID") # obtiene el id del json
                if item_id: # si existe el id
                    resp_data, status = self.data_proxy.get_item(item_id, client_uuid, session_id) # llama al metodo get_item del proxy
                else: # si no existe el id
                    resp_data, status = {"error": "Acción 'get' requiere un 'ID'"}, 400 # bad request
            
            elif action == "set": # si la accion es set
                if "id" in data: # si existe el id en los datos
                    resp_data, status = self.data_proxy.set_item(data, client_uuid, session_id) # llama al metodo set_item del proxy
                    if status == 200: # si esta bien
                        logger.info(f"{client_log_prefix} - 'set' exitoso. Notificando observadores...") # log info
                        self.notifier.notify(resp_data, DecimalEncoder) # notifica a los observadores
                else: # sino existe el id en los datos
                    resp_data, status = {"error": "Acción 'set' requiere un 'id' en los datos"}, 400 # bad request
            
            elif action == "list": # si la accion es list
                resp_data, status = self.data_proxy.list_items(client_uuid, session_id) # llama al list_items del proxy
            
            elif action == "list_logs":
                resp_data, status = self.data_proxy.list_logs(client_uuid, session_id)
            
            elif action == "subscribe": # si la accion es subscribe
                # 4 método del proxy para auditar esta acción.
                if self.data_proxy._log_action(client_uuid, session_id, "subscribe"): # si la auditoria funciona
                    self.notifier.subscribe(conn, client_uuid) # subscribe al cliente
                    is_subscriber = True # marca como suscriptor
                    resp_data, status = {"status": "OK", "message": "Suscrito exitosamente"}, 200 # bien
                else:
                    # Si la auditoría falla, no suscribimos al cliente
                    resp_data, status = {"error": "Fallo interno al registrar suscripción (auditoría)"}, 500 # error
            
            else: # si la accion es desconocida 
                resp_data, status = {"error": f"Acción '{action}' desconocida."}, 400 # bad request

            # Enviamos la respuesta (menos si es un suscriptor que se queda escuchando)
            if not is_subscriber: # si no es suscriptor
                self._send_response(conn, resp_data, status) # envia la respuesta al cliente 
            elif status != 200: # Si la suscripción fallo, enviamos error y cierra
                self._send_response(conn, resp_data, status) # envia la respuesta al cliente
                is_subscriber = False # desmarca como suscriptor
            else: # Si la suscripción fue buena, se envia OK y nos quedamos
                self._send_response(conn, resp_data, status) # envia respuesta

            # Si es suscriptor, se mantiene la conexión abierta
            if is_subscriber:
                logger.info(f"{client_log_prefix} - Hilo en modo 'escucha' (suscriptor).")
                # Bucle para detectar desconexión
                while conn.recv(1024): # para que siga vivo 
                    pass # no hace nada, solo espera
                logger.info(f"{client_log_prefix} - Suscriptor detectado como desconectado.")

        except json.JSONDecodeError: # error de json malformado
            logger.warning(f"{client_log_prefix} - Error: JSON malformado recibido.") # log warning
            self._send_response(conn, {"error": "JSON malformado o inválido"}, 400) # bad request
        
        except (socket.error, ConnectionResetError) as e: # error de socket o conexion reseteada
            logger.warning(f"{client_log_prefix} - Error de socket: {e}") # log warning
            
        except Exception as e: # error inesperado
            logger.error(f"{client_log_prefix} - Error inesperado en hilo: {e}", exc_info=True) # log error  
            self._send_response(conn, {"error": f"Error interno inesperado del servidor."}, 500) # error de servidor
            
        finally: # siempre se ejecuta
            if is_subscriber: # si es suscriptor
                #limpia al suscriptor de la lista
                self.notifier.unsubscribe(conn)
            
            conn.close() # cierra la conexion
            logger.info(f"{client_log_prefix} - Conexión cerrada. Finalizando hilo.")

    def start(self): # start del servidor
        """Inicia el bucle principal del servidor."""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # crea el socket
            
            # 3 Opción de socket reusador
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # permite reusar la direccion
            
            self.server_socket.bind((self.host, self.port)) # bind (bind es asociar el socket a una direccion y puerto) a host y port
            self.server_socket.listen(5) # hasta 5 conexiones en cola
            logger.info(f"Servidor {VERSION} escuchando en http://{self.host}:{self.port}") # log info
            
            # Bucle principal para aceptar clientes
            while True:
                conn, addr = self.server_socket.accept() # acepta la conexion del cliente
                
                # Inicia un nuevo hilo para manejar al cliente
                threading.Thread(
                    target=self.handle_client_connection,  # funcion a ejecutar
                    args=(conn, addr),  # argumentos de la funcion
                    daemon=True # hilo daemon para que termine con el programa
                ).start() # inicia el hilo

        except socket.error as e: # error de socket
            logger.error(f"Error de Socket (¿Puerto {self.port} ya en uso?): {e}") # log error
            sys.exit(1) # sale del programa con error
        except KeyboardInterrupt: # captura Ctrl+C
            logger.info("\nCerrando el servidor por petición del usuario (Ctrl+C)...") # log info
        finally: # siempre se ejecuta
            if hasattr(self, 'server_socket') and self.server_socket: # si existe el server_socket
                self.server_socket.close() # cierra el socket
            logger.info("Servidor detenido.")

if __name__ == "__main__": # si es el main
    parser = argparse.ArgumentParser(description="Servidor TPFI - Proxy/Singleton/Observer") # crea el parser (parser es para argumentos de linea de comando)
    parser.add_argument('-p', '--port', type=int, default=8080, help='Puerto en el que escuchar (default: 8080)') # agrega el argumento del puerto
    args = parser.parse_args() # parsea los argumentos
    
    # Define en qué host va a escuchar '0.0.0.0'
    host = '0.0.0.0' 
    Server(host, args.port).start()