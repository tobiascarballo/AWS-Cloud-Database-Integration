# 🧭 AWS Cloud — Proxy / Singleton / Observer (Servidor TCP con DynamoDB)

![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB?style=flat-square&logo=python&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat-square&logo=docker&logoColor=white)
![AWS](https://img.shields.io/badge/AWS-FF9900?style=flat-square&logo=amazon-aws&logoColor=white)
![Boto3](https://img.shields.io/badge/boto3-232F3E?style=flat-square)
![Patterns](https://img.shields.io/badge/Patterns-Singleton%20%7C%20Proxy%20%7C%20Observer-red?style=flat-square)

Este repositorio contiene un pequeño servidor TCP que ejemplifica tres patrones de diseño clásicos (**Singleton, Proxy y Observer**) conectándose a **DynamoDB (AWS)** para persistencia y auditoría.

La intención del proyecto es didáctica: mostrar cómo desacoplar acceso a la base (Singleton / Proxy) y notificar subscriptores (Observer) cuando hay cambios. Hay además clientes de ejemplo para ejecutar acciones (`get`, `set`, `list`) y para abrir una conexión en modo "observador" (suscriptor) que recibe notificaciones en tiempo real.

---

## 🏗️ Arquitectura y Flujo de Datos

```mermaid
sequenceDiagram
    participant Client
    participant Server as TCP Server
    participant Proxy as DataProxy (Log)
    participant Singleton as DB Singleton
    participant AWS as AWS DynamoDB
    participant Observer as Observer Manager

    Client->>Server: Envía comando (SET/GET)
    Server->>Proxy: Delega petición
    Proxy->>Proxy: Registra Auditoría (Log)
    Proxy->>Singleton: Solicita Instancia DB
    Singleton->>AWS: Ejecuta Operación (Boto3)
    AWS-->>Singleton: Retorna Resultado
    
    alt es una operación de escritura (SET)
        Singleton->>Observer: Notifica cambio
        Observer-->>Client: Envía evento a suscriptores
    end
    
    Singleton-->>Proxy: Retorna Datos
    Proxy-->>Server: Retorna Datos
    Server-->>Client: Respuesta JSON

---

## 🛠️ 1. Tecnologías y Componentes Clave

| Componente | Archivo/Módulo | Rol en el Flujo |
| :--- | :--- | :--- |
| **Servidor TCP (app)** | `src/singletonproxyobserver.py` | Servidor multihilo que expone acciones por TCP y orquesta los patrones. |
| **Cliente sincrónico** | `src/singletonclient.py` | Cliente para ejecutar `get`, `set`, `list` y recibir la respuesta del server. |
| **Cliente Observador (Subscriber)** | `src/observerclient.py` | Cliente que se suscribe y permanece recibiendo notificaciones en tiempo real. |
| **Proxy DB** | `src/modules/data_proxy.py` | Intermediario que añade auditoría cuando se accede a DynamoDB. |
| **Singleton DB** | `src/modules/db_singleton.py` | Singleton thread-safe que crea y reutiliza la conexión a DynamoDB. |
| **Observer (Notifier)** | `src/modules/observer.py` | Gestiona subscriptores y notifica en un hilo separado cuando ocurre un `set`. |
| **Tests de aceptación / Conexión** | `tests/test_acceptance.py`, `tests/test_conexion.py` | Automatizados para validar el flujo cliente ↔ servidor ↔ DynamoDB. |
| **Datos de ejemplo** | `data/*.json` | Payloads de pruebas/usos (ej: `acceptance_set.json`, `acceptance_get.json`). |

---

## 🔁 2. Flujo principal (resumido)

1. Cliente realiza una petición JSON por TCP al servidor (ej. `set` / `get` / `list`). Client: `singletonclient.py`.
2. `singletonproxyobserver.py` parsea la acción y delega en `DataProxy` (proxy) para acceder a DynamoDB.
3. `DataProxy` usa `DatabaseSingleton` para obtener la instancia de resource DynamoDB y registra una auditoría en `CorporateLog` antes de operar.
4. Si la acción es `set` y se escribe correctamente, se notifica a los subscriptores (Observer) con `NotificationManager`.
5. Los clientes observadores abiertos (observerclient) reciben la notificación en tiempo real y la imprimen.

> Nota: El servidor es multihilo (hilos por conexión) y la abstracción `NotificationManager` envía notificaciones de forma asíncrona para no bloquear las operaciones.

---

## 🚀 3. Requisitos y cómo ejecutar

### Requisitos

- Python 3.9+ (recomendado)
- Credenciales de AWS configuradas localmente (aws cli `aws configure`) con permisos para DynamoDB
- Tablas DynamoDB existentes: `CorporateData` y `CorporateLog` (los tests y el servidor lo esperan)
- (Opcional) Docker para simular infra o servicios locales — pero este proyecto usa DynamoDB real por boto3.

### Instalar dependencias

En el entorno del proyecto:

```powershell
python -m pip install -r requirements.txt
```

### Ejecutar el servidor

Por defecto escucha en el puerto 8080. Puedes cambiar el puerto con `-p`.

```powershell
python src\singletonproxyobserver.py -p 8080
```

### Enviar peticiones con el cliente

Ejemplo `set` (usa los JSON en `data/`):

```powershell
python src\singletonclient.py -i data\test_set.json -p 8080
```

Ejemplo `get`:

```powershell
python src\singletonclient.py -i data\test_get.json -p 8080
```

Suscribirte como observador (recibirás notificaciones sobre `set`):

```powershell
python src\observerclient.py -s localhost -p 8080
```

---

## ✅ 4. Tests y validación

Hay tests de aceptación que esperan tablas DynamoDB creadas y accesibles por las credenciales configuradas.

- Ejecutar tests de aceptación (requiere las tablas):

```powershell
python -m unittest tests/test_acceptance.py -v
```

- Prueba de conexión a DynamoDB (útil para verificar credenciales y tablas):

```powershell
python tests/test_conexion.py
```

Si necesitas correr pruebas unitarias/rápidas puedes usar pytest (si lo deseas):

```powershell
pytest -q
```

---

## 🧩 Notas técnicas y consideraciones

- El `DatabaseSingleton` implementa un pattern thread-safe (double-checked locking) para asegurar una sola instancia de resource boto3.
- `DataProxy` centraliza auditoría y acceso a tablas (separa responsabilidad y facilita testing/mocking).
- `NotificationManager` implementa envío no bloqueante a subscriptores registrados; si un envío falla, limpia el subscritor.
- Los tests de aceptación crean y eliminan elementos en la tabla `CorporateData`, por lo que no deben ejecutarse contra una tabla de producción.

---
**Desarrollado por Tobías Carballo**
*Estudiante de Licenciatura en Sistemas | UADER*
[LinkedIn](https://www.linkedin.com/in/tobias-carballo/)