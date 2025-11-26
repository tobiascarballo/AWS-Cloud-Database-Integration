import socket
import sys
import argparse
import json
import uuid

# El tiempo (seg) que el cliente va a esperar una respuesta
CLIENT_TIMEOUT = 10.0 

def get_cpu_id():
    """Obtiene el ID de la CPU/MAC como string."""
    return str(uuid.getnode())

def main():
    parser = argparse.ArgumentParser(
        description="Cliente para enviar acciones 'get/set/list' al Servidor TPFI."
    )
    parser.add_argument('-i', '--input', required=True, help='Archivo JSON de entrada con la acción.')
    parser.add_argument('-o', '--output', help='(Opcional) Archivo de salida para la respuesta JSON.')
    parser.add_argument('-s', '--server', default='localhost', help='Host del servidor (default: localhost)')
    parser.add_argument('-p', '--port', type=int, default=8080, help='Puerto del servidor (default: 8080)')
    parser.add_argument('-v', '--verbose', action='store_true', help='Activa el modo verboso para depuración.')
    args = parser.parse_args()

    # 1 Definimos una función de log que sigue el -v
    def log_verbose(*message):
        if args.verbose:
            print("[Verbose]", *message, file=sys.stderr)

    # 2 Lectura del archivo de entrada
    log_verbose(f"Leyendo archivo de entrada: {args.input}")
    try:
        with open(args.input, 'r') as f:
            request_data = json.load(f)
    except FileNotFoundError:
        print(f"Error: No se encontró el archivo de entrada '{args.input}'.", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"Error: El archivo '{args.input}' no contiene un JSON válido.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error inesperado al leer el archivo '{args.input}': {e}", file=sys.stderr)
        sys.exit(1)

    # 3 Preparación del Request
    if "UUID" not in request_data:
        log_verbose("UUID no encontrado en el JSON. Añadiendo ID de la CPU...")
        request_data["UUID"] = get_cpu_id()
    
    try:
        request_json_bytes = json.dumps(request_data).encode('utf-8')
    except TypeError as e:
        print(f"Error: No se pudo convertir el request a JSON: {e}", file=sys.stderr)
        sys.exit(1)

    # 4 Conexión y Comunicación con el Servidor
    log_verbose(f"Intentando conectar a {args.server}:{args.port}...")
    try:
        # 'with' asegura que el socket se cierre solo
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            # 4 se añade un Timeout
            sock.settimeout(CLIENT_TIMEOUT) 
            
            sock.connect((args.server, args.port))
            log_verbose(f"¡Conectado! Enviando {len(request_json_bytes)} bytes.")
            
            sock.sendall(request_json_bytes)
            
            # Bucle de recepcion, porque TCP es un stream y la respuesta puede llegar en muchas partes.
            buffer = b""
            while True:
                # Se espera recibir hasta 1024 bytes a la vez
                data_chunk = sock.recv(1024) 
                if not data_chunk:
                    # Si recibe 0 bytes, el servidor cerro la conexión
                    break 
                buffer += data_chunk
            
            response_data = buffer.decode('utf-8')
            log_verbose(f"Respuesta recibida ({len(response_data)} bytes).")

    except socket.timeout:
        print(f"Error: El servidor no respondió en {CLIENT_TIMEOUT} segundos.", file=sys.stderr)
        sys.exit(1)
    except socket.error as e:
        print(f"Error de conexión: No se pudo conectar a {args.server}:{args.port}.", file=sys.stderr)
        print("Detalle:", e, file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error inesperado de red: {e}", file=sys.stderr)
        sys.exit(1)

    # 5 Manejo de la Salida
    if args.output:
        log_verbose(f"Escribiendo respuesta en el archivo: {args.output}")
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(response_data)
            print(f"Respuesta guardada exitosamente en {args.output}")
        except IOError as e:
            print(f"Error al escribir en el archivo de salida '{args.output}': {e}", file=sys.stderr)
    else:
        try:
            # Intentar Pretty-Print si es JSON
            pretty_json = json.dumps(json.loads(response_data), indent=4, ensure_ascii=False)
            print(pretty_json)
        except json.JSONDecodeError:
            # Si no es JSON (ej un error de texto), imprimir tal cual
            print(response_data)

if __name__ == "__main__":
    main()