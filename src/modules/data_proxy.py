import sys
import uuid
import json
import logging
from datetime import datetime
from decimal import Decimal
from botocore.exceptions import ClientError
from modules.db_singleton import DatabaseSingleton

# Se obtiene el logger
logger = logging.getLogger(__name__) # __name__ es: modules.data_proxy

class DataProxy:
    """
    Implementa el Patrón Proxy. Actúa como intermediario para el acceso a la base de datos (obtenida del Singleton) para añadir funcionalidad de auditoría a cada operación.
    """
    
    def __init__(self): #constructor
        try: # para manejar errores
            # 1 Obtener la única instancia de la base de datos
            db = DatabaseSingleton() # si existe la reutilza, si no crea una nueva
            self.table_data = db.get_corporate_data_table() # obtener los punteros de la tabla data
            self.table_log = db.get_corporate_log_table() # obtener los punteros de la tabla log
            logger.info("DataProxy inicializado y conectado a tablas.") # imprime info con logger
        except Exception as e:
            # Si el Singleton fallo, esto va a fallar
            logger.error(f"Error fatal al inicializar DataProxy: {e}", exc_info=True)
            sys.exit(1) # sale del programa

    def _log_action(self, client_uuid, session_id, action, details=""): # funcion privada por el _
        """
        Metodo privado para registrar la acción de auditoría en CorporateLog - Si el log falla, da False. Si no True.
        """
        try:
            item = { #lista de atributos del item
                'id': str(uuid.uuid4()), # Clave primaria única
                'CPUid': str(client_uuid),
                'sessionid': str(session_id),
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'action': action,
                'details': details
            }
            self.table_log.put_item(Item=item) # insertar el item en la tabla log
            logger.info(f"AUDITORÍA: Acción '{action}' registrada para UUID {client_uuid}.") # impre info con logger
            return True # si esta bien devuelve True
        except ClientError as e: # error de aws
            # 2 Error de auditoría
            logger.error(f"FALLO DE AUDITORÍA - No se pudo registrar la acción '{action}': {e}")
            return False # si falla da False
        except Exception as e: # error inesperado
            logger.error(f"FALLO DE AUDITORÍA INESPERADO - No se pudo registrar la acción '{action}': {e}", exc_info=True)
            return False

    def get_item(self, item_id, client_uuid, session_id): # funcion que recibe item: id,uuid,sessionID
        # 2 Lógica de auditoría
        if not self._log_action(client_uuid, session_id, "get", f"ID: {item_id}"):
            # Si el log falla, no se sigue. Se devuelve un error de servidor.
            return {"error": "Fallo interno de auditoría"}, 500
        
        # Si el log funciona, se sigue
        try:
            response = self.table_data.get_item(Key={'id': item_id}) # obtiene el item de la tabla data
            
            if 'Item' in response: # si encuentra el item
                return response['Item'], 200 # bien
            else:
                return {"error": f"Item con ID '{item_id}' no encontrado."}, 404 # No encontro
        
        except ClientError as e: # error de aws
            logger.error(f"Error de AWS en get_item: {e}")
            return {"error": e.response['Error']['Message']}, 500 # error de servidor

    def set_item(self, item_data, client_uuid, session_id): # funcion que recibe item: data, uudid, sessionID
        # 1 Obtener el ID del item
        item_id = item_data.get('id', 'ID_NO_PROVISTO')
        
        # 2 Lógica de auditoría
        if not self._log_action(client_uuid, session_id, "set", f"ID: {item_id}"): # si el log falla
            return {"error": "Fallo interno de auditoría"}, 500 # error de servidor
        
        # 3 Manejo de errores para set_item
        try:
            # Conversión de float a Decimal para DynamoDB
            item_data_decimal = json.loads(json.dumps(item_data), parse_float=Decimal) # convierte los float a decimal
            
            self.table_data.put_item(Item=item_data_decimal) # inserta el item en la tabla data
            return item_data, 200 # bien
        
        except (json.JSONDecodeError, TypeError) as e: # error de datos
            logger.warning(f"Error de conversión de datos en set_item (ID: {item_id}): {e}") # logger warning
            return {"error": f"Datos JSON o formato inválido. {e}"}, 400 # bad request
        
        except ClientError as e: # error de aws
            logger.error(f"Error de AWS en set_item (ID: {item_id}): {e}") # logger error
            return {"error": e.response['Error']['Message']}, 500 # error de servidor
        
        except Exception as e: # error inesperado
            logger.error(f"Error inesperado en set_item (ID: {item_id}): {e}", exc_info=True) # logger error
            return {"error": "Error interno inesperado"}, 500 # error de servidor


    def list_items(self, client_uuid, session_id): # funcion que recibe item: uuid, sessionID
        # 2. Lógica de auditoría
        if not self._log_action(client_uuid, session_id, "list"): # si el log falla
            return {"error": "Fallo interno de auditoría"}, 500 # error del servidor
        
        try:
            # table.scan() lee la tabla entera - costoso para tablas grandes. Se usa para cumplir el Listado database completo.
            response = self.table_data.scan()
            
            # Devolvemos Items si existe, o sino una lista vacía
            return (response.get('Items', []), 200)
        
        except ClientError as e: # error de aws 
            logger.error(f"Error de AWS en list_items: {e}") # logger error
            return {"error": e.response['Error']['Message']}, 500 # error del servidor
        
    def list_logs(self, client_uuid, session_id):
        # 1. Auditamos que alguien está pidiendo ver los logs
        # (Sí, auditamos la auditoría)
        if not self._log_action(client_uuid, session_id, "list_logs", "Revisando CorporateLog"):
            return {"error": "Fallo interno de auditoría"}, 500
        
        try:
            # 2. Hacemos un scan() PERO a la tabla de logs
            response = self.table_log.scan()
            
            # 3. Devolvemos los logs
            return (response.get('Items', []), 200)
        
        except ClientError as e:
            logger.error(f"Error de AWS en list_logs: {e}")
            return {"error": e.response['Error']['Message']}, 500