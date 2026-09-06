# Sistema de Gestión de Redes Inteligentes (Smart Grid)

Proyecto base construido desde cero para el sector **Energía/Utilities**,
siguiendo el punto 15 de "Proyectos del Sector Energía/Utilities":
**Sistema de Gestión de Redes Inteligentes (Smart Grid)**.

Cubre sus cuatro pilares de forma **funcional y simulada, sin usar IoT ni
hardware externo**: toda la "red eléctrica" vive en memoria y los datos de
consumo se generan matemáticamente (curvas día/noche), igual que se haría
con datos sintéticos, pero orientado a demostrar arquitectura de software,
no modelos de Machine Learning.

## Requisito de la imagen -> Componente del proyecto

| Requisito                                   | Componente                                   |
|----------------------------------------------|-----------------------------------------------|
| Monitoreo de consumo energético en tiempo real | `core/grid_monitor.py` (`GridMonitor`)       |
| Balanceo de carga y gestión de picos          | `core/load_balancer.py` (`LoadBalancer`)     |
| Integración con energías renovables           | `energy_sources/` (`EnergySourceFactory`)    |
| Sistema de facturación dinámica               | `billing/` (`TariffFactory` + `DynamicBillingSystem`) |

## Patrones de diseño implementados

### 1. Singleton -> `GridMonitor`
La red solo debe tener **un** panel de monitoreo central. Si cada módulo
(balanceo de carga, facturación, reportes) tuviera su propia copia del
estado (fuentes registradas, historial de lecturas, alertas), podrían
desincronizarse entre sí. `GridMonitor` garantiza una única instancia
compartida por todo el sistema, con implementación thread-safe
(`__new__` + `threading.Lock`, double-checked locking) pensada para poder
escalar a un servidor concurrente más adelante.

```python
from core.grid_monitor import GridMonitor

m1 = GridMonitor()
m2 = GridMonitor.instance()
assert m1 is m2  # misma instancia siempre
```

### 2. Factory -> `EnergySourceFactory` y `TariffFactory`
Se usa el patrón en **dos** lugares del proyecto:

- **`EnergySourceFactory`**: crea fuentes de energía (`SolarSource`,
  `WindSource`, `HydroSource`, `ThermalSource`) a partir de un
  identificador de texto. El resto del sistema nunca instancia las
  clases concretas directamente, así que agregar una nueva fuente
  renovable (geotérmica, biomasa, etc.) no requiere tocar código
  existente — solo registrar el nuevo tipo en la fábrica.

- **`TariffFactory`**: decide qué tarifa (`PeakTariff`,
  `OffPeakTariff`, `StandardTariff`, `RenewableIncentiveTariff`) aplicar
  según la hora y el porcentaje de energía renovable despachada. Esta
  es la pieza central de la "facturación dinámica".

```python
from energy_sources.factory import EnergySourceFactory

panel = EnergySourceFactory.create_source("solar", "Panel Norte", 40)
```

## Estructura del proyecto

```
smart-grid-management/
├── main.py                        # orquesta la simulación de 24h
├── core/
│   ├── grid_monitor.py            # Singleton
│   └── load_balancer.py           # balanceo de carga / picos
├── energy_sources/
│   ├── base.py                    # interfaz EnergySource
│   ├── sources.py                 # Solar, Eólica, Hidro, Térmica
│   └── factory.py                 # Factory de fuentes
├── billing/
│   ├── tariff.py                  # estrategias de tarifa
│   ├── tariff_factory.py          # Factory de tarifas
│   └── billing_system.py          # facturación dinámica
├── simulation/
│   └── data_simulator.py          # curva de demanda día/noche (sin IoT)
└── tests/
    └── test_patterns.py           # valida Singleton y Factory
```

## Qué se reutilizó del repositorio de referencia (analizado antes) y qué no

**Se reutilizó (a nivel de concepto, no de código ni de ML):**
- La idea de generar una curva de demanda día/noche con funciones
  senoidales (`data_generation.py` del repo original) para simular
  consumo eléctrico realista sin sensores.
- La lógica de umbrales para decidir cuándo algo requiere atención
  (allí eran fallas eléctricas vía Isolation Forest; aquí es
  "pico de demanda" vía un umbral simple en `LoadBalancer`).

**Explícitamente NO se usó:**
- Ningún sensor, microcontrolador ni fuente de datos externa (nada de
  IoT). Todo el consumo se simula con código puro.
- Modelos de Machine Learning (Isolation Forest, XGBoost, LSTM, Random
  Forest). Este proyecto es de **arquitectura de software orientada a
  objetos** (patrones de diseño), no de ciencia de datos.

## Cómo ejecutar

No requiere dependencias externas (solo Python estándar, 3.9+).

```bash
cd smart-grid-management
python3 main.py
```

Para correr las pruebas de los patrones:

```bash
python3 -m tests.test_patterns
```

## Demo visual (capa desechable)

`streamlit_app.py` es una **interfaz gráfica desechable**, agregada únicamente
para mostrar avance en una entrega parcial. No es parte de la arquitectura del
proyecto: solo consume `core/`, `energy_sources/`, `billing/` y `simulation/`
tal como están, sin agregar lógica de negocio ni patrones propios. Se puede
eliminar o reemplazar sin afectar el resto del sistema.

```bash
pip install streamlit pandas
streamlit run streamlit_app.py
```

Muestra tres pestañas: monitoreo en tiempo real (gráficas de demanda/generación
y alertas de pico), fuentes de energía registradas, y facturación dinámica con
el resumen de costos por tarifa.

## Próximos pasos sugeridos

- Agregar más patrones (Strategy explícito para el balanceo de carga,
  Observer para que la facturación reaccione automáticamente a nuevas
  lecturas del `GridMonitor` en vez de que `main.py` los conecte
  manualmente).
- Persistir el historial (`GridMonitor.history`) en una base de datos o
  archivo, en vez de mantenerlo solo en memoria.
- Sustituir `simulation/data_simulator.py` por una fuente de datos real
  si el proyecto decide incorporar IoT en una fase futura.
