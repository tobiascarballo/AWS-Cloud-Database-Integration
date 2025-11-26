# src/modules/db_singleton.py
import boto3
import sys
import logging
import threading
from botocore.exceptions import ClientError, NoCredentialsError

# - Configuración del Logging
# level=logging.INFO muestra mensajes informativos y de error.
# format= define cómo se ve cada línea de log.
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout  # Se envian los logs a la consola
)
# Se obtiene un logger específico para este archivo.
logger = logging.getLogger(__name__) # __name__ = modules.db_singleton

class DatabaseSingleton:
    """
    Implementa un Singleton thread-safe para la conexión a DynamoDB.
    Asegura que solo va a haber una instancia de conexión en toda la app, manejando mejor su inicialización.
    """
    
    _instance = None
    _lock = threading.Lock() # 2 Se añade un candado (Lock) a nivel de clase

    def __new__(cls):
        # 2 Se implementa el "Double-Checked Locking"
        
        # Primer chequeo - rapido - Evita adquirir el "candado" si la instancia ya existe.
        if cls._instance is None:
            
            # Si no existe, agarramos el "candado"
            with cls._lock:
                
                # Segundo chequeo - necesario por si dos hilos pasaron el primer if a la vez.
                # El primer hilo crea la instancia, el segundo ve que ya no es None.
                if cls._instance is None:
                    logger.info("Creando nueva instancia de DatabaseSingleton...")
                    cls._instance = super(DatabaseSingleton, cls).__new__(cls)
                    cls._instance._initialized = False
        
        return cls._instance

    def __init__(self):
        """
        Inicializa la conexión a DynamoDB.
        Gracias a '_initialized', el código "pesado" solo se ejecuta una vez
        """
        # Evita reinicializar
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        logger.info("Inicializando conexión a DynamoDB...")
        
        # 3 try/except
        try:
            self.dynamodb = boto3.resource('dynamodb')
            
            # Cargar punteros de las tablas
            self.table_corporate_data = self.dynamodb.Table('CorporateData')
            self.table_corporate_log = self.dynamodb.Table('CorporateLog')
            
            # Verificar la conexión y que las tablas existan
            logger.info("Verificando conexión y tabla 'CorporateData'...")
            self.table_corporate_data.load()
            
            logger.info("Verificando conexión y tabla 'CorporateLog'...")
            self.table_corporate_log.load()
            
            logger.info("Conexión a DynamoDB y tablas verificadas exitosamente.")
            self._initialized = True # inicializa

        except NoCredentialsError: # 3 por si no hay credenciales
            logger.error("Error fatal: No se encontraron credenciales de AWS.")
            logger.error("Por favor, ejecuta 'aws configure' con las credenciales correctas.")
            sys.exit(1) # Salida

        except ClientError as e: # 3 errores de AWS
            error_code = e.response.get('Error', {}).get('Code')
            
            if error_code == 'ResourceNotFoundException':
                logger.error("Error fatal: Una o ambas tablas (CorporateData, CorporateLog) no existen.")
                logger.error("Verifica que las tablas estén creadas en la región correcta de AWS.")
            elif error_code == 'UnrecognizedClientException':
                logger.error("Error fatal: Credenciales de AWS inválidas (Access Key o Secret Key).")
                logger.error("Vuelve a ejecutar 'aws configure'.")
            else:
                logger.error(f"Error fatal (ClientError) no manejado: {error_code} - {e}")
            
            sys.exit(1) # Salida

        except Exception as e: # 3 cualquier otro error
            logger.error(f"Error fatal inesperado durante la inicialización de DB: {e}", exc_info=True)
            sys.exit(1) # Salida

    def get_corporate_data_table(self):
        """Devuelve la instancia de la tabla CorporateData."""
        return self.table_corporate_data

    def get_corporate_log_table(self):
        """Devuelve la instancia de la tabla CorporateLog."""
        return self.table_corporate_log