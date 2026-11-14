# Monopoly Arena — Clean Architecture & Serverless Backend

Arquitectura inicial desacoplada para documentar y gestionar partidas de **Monopoly Clásico** y futuras **expansiones/variantes** sin alterar el núcleo de reglas.

---

## 🏛️ Principios de Arquitectura Limpia y SOLID

```
                             ┌──────────────────────────────────────┐
                             │       Presentation (FastAPI)         │
                             │   Routers, Schemas, Mangum Handler   │
                             └──────────────────┬───────────────────┘
                                                │ (Depends DI)
                                                ▼
                             ┌──────────────────────────────────────┐
                             │       Application (Use Cases)        │
                             │  BuyPropertyUseCase, TransferMoney   │
                             └──────────┬───────────────────────────┘
                                        │
                    ┌───────────────────┴───────────────────┐
                    ▼                                       ▼
     ┌───────────────────────────────┐     ┌───────────────────────────────────┐
     │      Domain (Protocols)       │     │     Domain (Entities & Rules)     │
     │  *RepositoryProtocol (typing) │     │ Game, Player, Strategy Pattern    │
     └──────────────▲────────────────┘     └───────────────────────────────────┘
                    │ (Implements)
     ┌──────────────┴────────────────┐
     │  Infrastructure (SQLAlchemy)  │
     │  Supabase Postgres, ORM Models│
     └───────────────────────────────┘
```

1. **S - Single Responsibility:**
   - **Presentation:** Los routers HTTP sólo validan DTOs de entrada y devuelven respuestas HTTP.
   - **Application:** Los Casos de Uso (`BuyPropertyUseCase`, etc.) únicamente orquestan las reglas del juego.
   - **Infrastructure:** Los repositorios se limitan a la persistencia en PostgreSQL (Supabase).
2. **O - Open/Closed (Abierto a Extensión, Cerrado a Modificación):**
   - El motor de casillas utiliza el patrón **Strategy** (`TileActionStrategy`). Casillas especiales, ferrocarriles y calles tienen algoritmos de renta independientes.
   - Las reglas están registradas en `BoardRuleRegistry`. Para añadir variantes (ej: *Monopoly Edición Especial* o *Monopoly Gamer*), basta con registrar una nueva variante sin alterar el Monopoly clásico.
3. **L - Liskov Substitution & I - Interface Segregation:**
   - Uso de `typing.Protocol` en `domain/interfaces/` (`GameRepositoryProtocol`, `PlayerRepositoryProtocol`, `PropertyRepositoryProtocol`, `TransactionRepositoryProtocol`).
   - Contratos granulares y pequeños. Las pruebas o futuros adaptadores de base de datos pueden sustituirse sin herencia forzada.
4. **D - Dependency Inversion:**
   - La lógica de negocio (`src/application`) depende exclusivamente de abstracciones (Protocolos), nunca de SQLAlchemy o PostgreSQL.
   - FastAPI inyecta las implementaciones de infraestructura mediante `Depends` en `src/presentation/dependencies.py`.
5. **Agnóstico de Interfaz:**
   - Los casos de uso reciben DTOs puros de Python. Una interfaz web basada en React/Vue, o un bot de Telegram/WhatsApp consumen exactamente los mismos casos de uso.

---

## 🚀 Despliegue Serverless en Vercel & Supabase

### 1. Variables de Entorno (`.env`)
En Supabase, dirígete a **Project Settings > Database > Connection Pooling**:
- Copia la cadena en **Transaction Mode** (puerto `6543`), ideal para Serverless en Vercel:
```env
DATABASE_URL=postgresql://postgres.[PROJECT_REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres
ENVIRONMENT=production
DEBUG=False
```

### 2. Configuración de Vercel (`vercel.json`)
La API se ejecuta a través de `api/index.py` utilizando `Mangum`:
```json
{
  "version": 2,
  "builds": [
    {
      "src": "api/index.py",
      "use": "@vercel/python"
    }
  ],
  "routes": [
    {
      "src": "/(.*)",
      "dest": "api/index.py"
    }
  ]
}
```

---

## 📁 Estructura del Proyecto

```
proyecto-nuevo/
├── api/
│   └── index.py                      # Handler Serverless Vercel (Mangum)
├── src/
│   ├── config.py                     # Configuración y variables de entorno
│   ├── domain/                       # NÚCLEO: Reglas puras del negocio
│   │   ├── exceptions.py             # Excepciones de dominio
│   │   ├── models/                   # Entidades (Game, Player, Property, Transaction)
│   │   ├── interfaces/               # Protocolos de Repositorios (SOLID L & I)
│   │   └── rules/                    # Patrón Strategy y Registry de Tableros
│   │       ├── base_strategy.py
│   │       ├── classic_rules.py
│   │       └── rule_registry.py
│   ├── application/                  # Casos de Uso (Orquestación agnóstica)
│   │   ├── dtos/                     # DTOs de entrada y salida
│   │   └── use_cases/                # BuyPropertyUseCase, TransferMoneyUseCase
│   ├── infrastructure/               # Adaptadores externos
│   │   ├── database.py               # Engine SQLAlchemy optimizado para Serverless
│   │   ├── orm/                      # Modelos SQLAlchemy para Supabase
│   │   └── repositories/             # Implementación SQL de los Protocolos
│   └── presentation/                 # Capa de entrega (FastAPI + Jinja2 + Tailwind)
│       ├── main.py                   # Fábrica de FastAPI, CORS y montaje de vistas
│       ├── dependencies.py           # Inyección de dependencias (SOLID D)
│       ├── schemas/                  # Esquemas Pydantic v2
│       ├── templates/                # Plantillas HTML5 (Tabletop Fintech)
│       │   ├── base.html             # Layout base, Tailwind CDN, Dark/Light mode FOUC-proof
│       │   ├── lobby.html            # Lobby: creación de partidas y fichas de jugadores
│       │   └── game.html             # Tablero de control: tarjetas fintech, acciones y ledger
│       └── routers/                  # Endpoints REST y Web Controllers
│           ├── views_router.py       # Rutas HTML (/, /game/{id})
│           ├── games_router.py       # API de Partidas, Jugadores y Casillas
│           └── actions_router.py     # API de Compra y Transferencias
├── tests/
│   └── test_domain_usecase_pure.py   # Test desacoplado con mocks en memoria
├── requirements.txt
├── vercel.json
└── README.md
```

---

## 🛠️ Desarrollo Local con Entorno Virtual (`venv`)

> [!IMPORTANT]
> **Requisito estricto:** El desarrollo y la ejecución local deben realizarse **obligatoriamente dentro de un entorno virtual de Python (`venv`)**. Esto aísla las dependencias del proyecto (FastAPI, SQLAlchemy, Uvicorn, Jinja2), previene conflictos con librerías globales del sistema operativo y asegura paridad exacta con el entorno Serverless de Vercel.

---

### Opción A: Scripts Automatizados de Inicio Rápido

El repositorio incluye scripts listos para usar que crean el `venv` (si aún no existe), instalan las dependencias e inician Uvicorn automáticamente:

- **Windows PowerShell:**
  ```powershell
  .\run_dev.ps1
  ```
  *(Si PowerShell restringe la ejecución de scripts, habilítala para la sesión actual con:* `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process`*)*

- **Windows CMD (Command Prompt):**
  ```cmd
  run_dev.bat
  ```

- **Linux / macOS:**
  ```bash
  chmod +x run_dev.sh
  ./run_dev.sh
  ```

---

### Opción B: Guía Paso a Paso Manual

#### 1. Crear el Entorno Virtual (`venv`)
Desde la raíz del proyecto (`proyecto-nuevo/`):
```bash
python -m venv venv
```
*(En Linux/Mac, si tienes múltiples versiones de Python, puedes usar:* `python3 -m venv venv`*)*

#### 2. Activar el Entorno Virtual

- **En Windows PowerShell:**
  ```powershell
  .\venv\Scripts\Activate.ps1
  ```

- **En Windows Command Prompt (cmd.exe):**
  ```cmd
  venv\Scripts\activate.bat
  ```

- **En Linux o macOS (bash / zsh):**
  ```bash
  source venv/bin/activate
  ```

> Cuando el entorno está activo, verás el prefijo `(venv)` al inicio de la línea de comandos de tu terminal.

#### 3. Instalar Dependencias dentro del `venv` Activo
Con el entorno virtual activo, actualiza `pip` e instala el archivo de requisitos:
```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

#### 4. Levantar el Servidor con Uvicorn
Garantiza que Uvicorn se ejecute utilizando el intérprete de Python del entorno virtual:

- **Con el entorno `venv` ya activado:**
  ```bash
  python -m uvicorn src.presentation.main:app --reload --host 127.0.0.1 --port 8000
  ```

- **O invocando directamente el binario de Python del `venv` (sin necesidad de activarlo previamente):**
  - **Windows (PowerShell o CMD):**
    ```powershell
    .\venv\Scripts\python.exe -m uvicorn src.presentation.main:app --reload --host 127.0.0.1 --port 8000
    ```
  - **Linux / macOS:**
    ```bash
    ./venv/bin/python -m uvicorn src.presentation.main:app --reload --host 127.0.0.1 --port 8000
    ```

#### 5. Ejecutar Pruebas Unitarias del Dominio
```bash
python -m unittest tests/test_domain_usecase_pure.py
```

#### 6. Desactivar el Entorno Virtual al Finalizar
Cuando termines de trabajar, sal del entorno virtual ejecutando:
```bash
deactivate
```

---

### 🌐 Accesos en Local

Una vez iniciado el servidor:
- **Lobby Web Interactivo:** [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- **Documentación Swagger UI (OpenAPI):** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Documentación ReDoc:** [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)
