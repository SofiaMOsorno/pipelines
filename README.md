# Pipeline de Procesamiento de Transacciones BTC
## Descripción de la actividad:
En esta actividad, los estudiantes deberán diseñar e implementar un pipeline con 5 filtros para procesar una transacción de compra de Bitcoin (BTC) usando distintas monedas base (USD, EUR o GBP).

El objetivo es comprender cómo los patrones arquitectónicos de tipo pipeline permiten estructurar un flujo de procesamiento en etapas secuenciales, cada una con responsabilidades bien definidas, promoviendo la separación de preocupaciones, la reutilización y la mantenibilidad del código.

Cada filtro representará una etapa específica del procesamiento de una transacción y deberá implementarse como un módulo independiente, comunicándose con el siguiente a través de una interfaz común.

## Equipo de Desarrollo
- Sofía Maisha Osorno Aimar
- Mateo Hernández Gutiérrez
- Rodrigo López Coronado
- Jose Antonio Caballero

## Arquitectura
El sistema utiliza el patrón Chain of Responsibility donde cada filtro procesa la transacción secuencialmente:

- ValidationFilter: Verifica que la transacción contenga datos válidos
- AuthFilter: Confirma la identidad y estado del usuario
- TransformFilter: Convierte BTC a la moneda base usando tasas de cambio
- FeeFilter: Calcula y agrega la comisión fija en la moneda correspondiente
- StorageFilter: Persiste la transacción procesada en SQLite

## Estructura del Proyecto
```
pipeline/
│
├── pipeline_btc.py          # Código principal del pipeline
├── transactions.db          # Base de datos SQLite (generada automáticamente)
└── README.md               # Este archivo
```

## Requisitos

- Python 3.8 o superior
- SQLite3 (incluido en Python estándar)

No se requieren dependencias externas adicionales.

## Instalación

1. Clonar o descargar el repositorio:

```
git clone <url-del-repositorio>
cd pipeline-btc
```

1. Verificar la instalación de Python:

```
python --version
```

## Ejecución
Ejecución básica

Para ejecutar el programa con las transacciones de ejemplo incluidas:

```
python pipeline_btc.py
```

### Salida esperada
El programa genera una salida JSON con los resultados del procesamiento:

```[
  {
    "ok": true,
    "transaction": {
      "user_id": "u001",
      "btc_amount": 0.01,
      "base_currency": "USD",
      "btc_price_in_base": 65000.0,
      "subtotal_base": 650.0,
      "commission_usd": 5.0,
      "commission_base": 5.0,
      "total_base": 655.0,
      "ts_epoch": 1234567890
    },
    "user": {
      "user_id": "u001",
      "name": "Alice",
      "active": true
    },
    "storage_result": "ok"
  }
]
```
