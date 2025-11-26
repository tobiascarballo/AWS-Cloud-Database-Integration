import socket
import sys
import argparse
import json
import uuid
import time

def get_cpu_id():
    """Obtiene el ID de la CPU/MAC como string."""
    return str(uuid.getnode())

def log_status(message, force_verbose=False):
    """
    Similar a un logger - Si force_verbose es True, solo imprime si -v está activo.
    """
    if force_verbose and not G_VERBOSE:
        return
    # Imprimimos logs, errores y mensajes de estado a stderr
    print(f"[Estado] {message}", file=sys.stderr)

def main():
    global G_VERBOSE # Variable global
    
    parser = argparse.ArgumentParser(
        description="Cliente Observador (Suscriptor) para el Servidor TPFI."
    )
    parser.add_argument('-s', '--server', default='localhost', help='Host del servidor (default: localhost)')
    parser.add_argument('-p', '--port', type=int, default=8080, help='Puerto del servidor (default: 8080)')
    # 1 Argumento para el delay de reintento
    parser.add_argument('-r', '--retry', type=int, default=30, help='Segundos para reintentar conexión (default: 30)')
    parser.add_argument('-v', '--verbose', action='store_true', help='Activa el modo verboso.')
    
    args = parser.parse_args()
    G_VERBOSE = args.verbose
    
    client_uuid = get_cpu_id()
    # Preparamos el único mensaje que enviaremos
    subscribe_request = json.dumps({
        "ACTION": "subscribe", 
        "UUID": client_uuid
    })
    
    log_status(f"Cliente Observador iniciado. UUID: {client_uuid}")
    log_status(f"Conectando a {args.server}:{args.port}. Reintentos cada {args.retry} seg.")

    # Reconexión, el bucle se ejecuta indefinidamente. Si la conexión falla, el bloque except al final "duerme" y el bucle empieza de nuevo.
    while True:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                # timeout para conexión inicial
                sock.settimeout(10.0) 
                
                log_status(f"Intentando conectar a {args.server}:{args.port}...", force_verbose=True)
                sock.connect((args.server, args.port))
                
                # Una vez conectado, quitamos el timeout para el bucle de escucha
                sock.settimeout(None) 
                
                log_status("¡Conectado! Enviando suscripción...")
                sock.sendall(subscribe_request.encode('utf-8'))

                # Esperamos respuesta de confirmación del servidor
                response_raw = sock.recv(1024).decode('utf-8')
                response = json.loads(response_raw)

                if response.get("status") != "OK":
                    # 4 Error de suscripción
                    log_status(f"Error al suscribirse: {response.get('message', 'Respuesta no OK')}")
                    raise ConnectionError("Fallo en la suscripción, reintentando...")
                
                log_status(f"Suscripción exitosa. Escuchando notificaciones...")

                # - Bucle de Escucha
                while True:
                    notification_raw = sock.recv(4096)
                    if not notification_raw:
                        # Servidor cerró la conexión
                        raise ConnectionError("Servidor cerró la conexión.")
                    
                    # 2 Imprime la data limpia a stdout
                    try:
                        parsed = json.loads(notification_raw.decode('utf-8'))
                        # 'ensure_ascii=False' para ñ y acentos
                        print(json.dumps(parsed, indent=4, ensure_ascii=False)) 
                    except json.JSONDecodeError:
                        # Si no es JSON, imprimir raw
                        print(notification_raw.decode('utf-8'))

        except (socket.error, socket.timeout, ConnectionError, ConnectionResetError, json.JSONDecodeError) as e:
            log_status(f"Conexión perdida: {e}")
            log_status(f"Reintentando conexión en {args.retry} segundos...")
            time.sleep(args.retry) # Espera antes de que el while True reintente
        
        except KeyboardInterrupt:
            log_status("\nCerrando cliente observador por petición del usuario.")
            break # Rompe el bucle y termina

if __name__ == "__main__":
    main()