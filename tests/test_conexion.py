import boto3
import sys
from botocore.exceptions import ClientError

print("--- Iniciando prueba de conexión de AWS ---")

try:
    # 1. Intentar conectar a DynamoDB
    print("Intentando conectar a DynamoDB con las credenciales...")
    dynamodb = boto3.resource('dynamodb')

    # 2. Intentar "tocar" las tablas (como en IS2_TPFI_test.py)
    print("Accediendo a la tabla 'CorporateData'...")
    table_data = dynamodb.Table('CorporateData')
    table_data.load()  # Esto fuerza la conexión
    print(
        f"-> ÉXITO. Tabla 'CorporateData' encontrada. (Fecha de creación: {table_data.creation_date_time})")

    print("Accediendo a la tabla 'CorporateLog'...")
    table_log = dynamodb.Table('CorporateLog')
    table_log.load()
    print(
        f"-> ÉXITO. Tabla 'CorporateLog' encontrada. (Fecha de creación: {table_log.creation_date_time})")

    # 3. Intentar leer el dato inicial (como en IS2_TPFI_demo.py)
    print("Intentando leer el ítem 'UADER-FCYT-IS2' de 'CorporateData'...")
    response = table_data.get_item(Key={'id': 'UADER-FCyT-IS2'})

    if 'Item' in response:
        print(f"-> ÉXITO. Se encontró el ítem:")
        print(response['Item'])
    else:
        print("-> ERROR: No se encontró el ítem 'UADER-FCYT-IS2'.")
        print("   (El servidor funcionará, pero 'get' a este ID fallará hasta que se cree)")

    print("\n--- ¡Prueba de conexión finalizada! ---")

except ClientError as e:
    if e.response['Error']['Code'] == 'UnrecognizedClientException':
        print("\n*** ERROR GRAVE: Problema de Credenciales. ***")
        print("Las 'Access Key' o 'Secret Key' son incorrectas.")
        print("Vuelve a ejecutar 'aws configure' con las claves correctas.")
    elif e.response['Error']['Code'] == 'ResourceNotFoundException':
        print("\n*** ERROR GRAVE: Tablas no encontradas. ***")
        print(f"No se encontró una de las tablas ('CorporateData' o 'CorporateLog').")
        print("Asegúrate de que la 'region' en 'aws configure' sea la correcta.")
    else:
        print(f"\n*** ERROR INESPERADO: {e} ***")

except Exception as e:
    print(f"\n*** ERROR: {e} ***")
