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
| Monitoreo de consumo energético en tiempo real | `core/grid_monitor.py` (`GridMonitor`) + `core/anomaly_detector.py` (`AnomalyDetector`) |
| Balanceo de carga y gestión de picos          | `core/load_balancer.py` (`LoadBalancer`)     |
| Integración con energías renovables           | `energy_sources/` (`EnergySourceFactory`) + estabilización de voltaje en `LoadBalancer` |
| Sistema de facturación dinámica               | `billing/` (`TariffFactory` + `DynamicBillingSystem`) + seguimiento de pérdidas técnicas |

## Versión 2: cierre de brechas frente al alcance original

Una revisión del documento de alcance del proyecto identificó que la
versión inicial cumplía **balanceo de carga** y **facturación dinámica**,
pero dejaba brechas en **monitoreo** (sin estado eléctrico ni detección de
anomalías) y en **integración renovable** (sin ningún mecanismo de
estabilización de voltaje). Esta versión las cierra de forma aditiva, sin
modificar el comportamiento de Singleton ni de Factory ya existentes:

| Brecha identificada | Qué se agregó | Dónde |
|---|---|---|
| No se medía voltaje, corriente ni factor de potencia | `simulate_electrical_metrics()`: genera estas tres métricas por hora a partir de la demanda y el % de energía renovable, sin sensores ni ML | `simulation/electrical_simulator.py` |
| No había detección de anomalías/fallas | `AnomalyDetector`: reglas por umbral (voltaje fuera de ±5%, factor de potencia bajo, sobrecorriente) | `core/anomaly_detector.py` |
| No se modelaban pérdidas técnicas | `DynamicBillingSystem.record_technical_loss()`: cuantifica energía generada que se pierde en transmisión y su costo | `billing/billing_system.py` |
| La integración renovable no "estabilizaba" nada | `LoadBalancer.stabilize_voltage()`: si hay una anomalía de voltaje y la generación fue mayoritariamente renovable, refuerza con generación estable (hidro/térmica) | `core/load_balancer.py` |

`GridMonitor.record_reading()` se extendió con parámetros opcionales
(`voltage`, `current`, `power_factor`, `technical_loss_kw`) — las llamadas
antiguas que solo pasaban `hour/demand_kw/generation_kw` siguen funcionando
igual (ver `tests/test_new_features.py`, que prueba explícitamente esta
compatibilidad hacia atrás).

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
│   ├── load_balancer.py           # balanceo de carga / picos + estabilización
│   └── anomaly_detector.py        # detección de anomalías por umbral
├── energy_sources/
│   ├── base.py                    # interfaz EnergySource
│   ├── sources.py                 # Solar, Eólica, Hidro, Térmica
│   └── factory.py                 # Factory de fuentes
├── billing/
│   ├── tariff.py                  # estrategias de tarifa
│   ├── tariff_factory.py          # Factory de tarifas
│   └── billing_system.py          # facturación dinámica + pérdidas técnicas
├── simulation/
│   ├── data_simulator.py          # curva de demanda día/noche (sin IoT)
│   └── electrical_simulator.py    # voltaje, corriente, FP, pérdidas técnicas
└── tests/
    ├── test_patterns.py           # valida Singleton y Factory
    └── test_new_features.py       # valida anomalías, pérdidas y estabilización
```

## Qué se reutilizó del repositorio de referencia (analizado antes) y qué no

**Se reutilizó (a nivel de concepto, no de código ni de ML):**
- La idea de generar una curva de demanda día/noche con funciones
  senoidales (`data_generation.py` del repo original) para simular
  consumo eléctrico realista sin sensores.
- La lógica de umbrales para decidir cuándo algo requiere atención
  (allí eran fallas eléctricas vía Isolation Forest; aquí es
  "pico de demanda" y "anomalía eléctrica" vía umbrales simples en
  `LoadBalancer` y `AnomalyDetector`).

**Explícitamente NO se usó:**
- Ningún sensor, microcontrolador ni fuente de datos externa (nada de
  IoT). Todo el consumo y el estado eléctrico se simulan con código puro.
- Modelos de Machine Learning (Isolation Forest, XGBoost, LSTM, Random
  Forest). La detección de anomalías es 100% basada en reglas/umbrales,
  igual que el resto del proyecto — no hay entrenamiento ni inferencia
  estadística. Este proyecto es de **arquitectura de software orientada
  a objetos** (patrones de diseño), no de ciencia de datos.

## Cómo ejecutar

No requiere dependencias externas (solo Python estándar, 3.9+).

```bash
cd smart-grid-management
python3 main.py
```

Para correr las pruebas:

```bash
python3 -m tests.test_patterns
python3 -m tests.test_new_features
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

Muestra cuatro pestañas: monitoreo en tiempo real (demanda/generación y
alertas), **calidad de la red** (voltaje, factor de potencia y pérdidas
técnicas), fuentes de energía registradas, y facturación dinámica con el
resumen de costos por tarifa y el costo de las pérdidas técnicas.

## Próximos pasos sugeridos

- Agregar más patrones (Strategy explícito para el balanceo de carga y
  para la estabilización de voltaje, Observer para que la facturación y
  el detector de anomalías reaccionen automáticamente a nuevas lecturas
  del `GridMonitor` en vez de que `main.py`/`streamlit_app.py` los
  conecten manualmente).
- Persistir el historial (`GridMonitor.history`) en una base de datos o
  archivo, en vez de mantenerlo solo en memoria.
- Sustituir `simulation/data_simulator.py` y `electrical_simulator.py`
  por una fuente de datos real si el proyecto decide incorporar IoT en
  una fase futura.

