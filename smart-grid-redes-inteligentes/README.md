# Red Inteligente: Sistema de Gestión de Redes Inteligentes (Smart Grid)

Simulador de un día completo (24 h) de una red eléctrica, sin sensores físicos: todo se genera por software.

## Cómo ejecutarlo

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py      # interfaz gráfica
python main.py --help               # versión de terminal
```

## Qué hace (módulos y objetivos)

| Pestaña de la interfaz | Objetivo específico que cumple |
|---|---|
| **Monitoreo** | 1. Captura, procesa y visualiza lecturas hora a hora y detecta anomalías, fallas y pérdidas de energía a tiempo. |
| **Demanda y picos** | 2. Redistribuye la demanda (consumo flexible), aplana picos y previene sobrecargas y desgaste de equipos. |
| **Energías renovables** | 3. Integra solar, eólica, hidro, geotérmica y baterías y estabiliza el voltaje ante la intermitencia. |
| **Facturación** | 4. Aplica tarifas variables por hora y % renovable, incentiva consumir fuera de pico y muestra el margen. |
| Operar la red / Reportes / Permisos | Apoyo: cambios con deshacer, puntos de guardado, reportes y control de roles. |

## Patrones de diseño y por qué se usan

Creacionales y estructurales (ya validados): Singleton (GridMonitor), Factory Method (fuentes y tarifas), Builder, Prototype, Adapter (JSON/CSV), Bridge (tarifa × cálculo), Composite (sectores/fuentes), Decorator (descuentos y recargos), Facade, Flyweight (perfiles de consumo) y Proxy (roles y auditoría).

Comportamiento, cada uno ligado a un objetivo:

| Patrón | Dónde | Por qué (objetivo) |
|---|---|---|
| Chain of Responsibility | `core/anomaly_chain.py` | **1.** Voltaje → factor de potencia → corriente → pérdidas: cada revisión es independiente y todas se aplican a cada lectura. |
| Observer | `core/events.py`, `core/observers.py` | **1.** El monitor publica lecturas y alertas al instante; los contadores se suscriben sin acoplarse. |
| Strategy | `core/dispatch_strategies.py` | **2.** Dos criterios de respaldo (ahorrar o proteger) intercambiables en ejecución. |
| State | `core/grid_state.py` | **2.** Normal/Pico/Emergencia cambian solos la estrategia de respaldo. |
| Command | `core/commands.py` | **2 y 3.** Apagar fuentes, fallas, límite de pico, modo y consumo flexible con historial y deshacer. |
| Mediator | `core/grid_mediator.py` | **1 a 4.** Coordina balanceo, medición, detección, estabilización, facturación y estado en cada hora. |
| Visitor | `core/grid_visitors.py` | **2 y 3.** Capacidad renovable, fuentes apagadas y salud de equipos sin modificar el árbol. |
| Iterator | `core/grid_iterators.py` | **1.** Recorre fuentes y lecturas (reproducción del día en vivo, faltantes). |
| Memento | `core/memento.py` | **2 y 4.** Puntos de guardado para probar cambios y volver (incluye fallas). |
| Template Method | `core/reports.py` | **1, 3 y 4.** Los tres reportes comparten esqueleto. |

Interpreter no se implementa: no hay un lenguaje que interpretar en el dominio.
