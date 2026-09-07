"""
streamlit_app.py

*** CAPA DESECHABLE - SOLO PARA DEMO / ENTREGA PARCIAL ***

Esta interfaz NO forma parte de la arquitectura del proyecto. Es una capa
delgada que únicamente CONSUME lo que ya existe en core/, energy_sources/,
billing/ y simulation/ para mostrar el avance de forma visual. No agrega
lógica de negocio nueva, no introduce patrones de diseño propios y está
pensada para ser reemplazada (o eliminada) cuando el proyecto avance hacia
una interfaz definitiva o hacia los patrones estructurales/de comportamiento.

Ejecutar con:
    streamlit run streamlit_app.py
"""
import random as _random
import pandas as pd
import streamlit as st

from core.grid_monitor import GridMonitor
from core.load_balancer import LoadBalancer
from core.anomaly_detector import AnomalyDetector
from energy_sources.factory import EnergySourceFactory
from billing.billing_system import SistemadeFacturacionDinamico
from simulation.data_simulator import simulate_daily_demand
from simulation.electrical_simulator import simulate_electrical_metrics

st.set_page_config(page_title="Smart Grid - Demo", layout="wide")


def build_grid(source_config):
    """Misma idea que build_grid() en main.py: crea fuentes via Factory
    y las registra en el GridMonitor (Singleton)."""
    monitor = GridMonitor.instance()
    monitor.reset()
    for source_type, name, capacity in source_config:
        source = EnergySourceFactory.create_source(source_type, name, capacity)
        monitor.register_source(source)
    return monitor


def run_simulation(source_config, peak_threshold_kw, base_load_kw, peak_load_kw, seed):
    monitor = build_grid(source_config)
    balancer = LoadBalancer(peak_threshold_kw=peak_threshold_kw)
    detector = AnomalyDetector()
    billing = SistemadeFacturacionDinamico()

    demand_by_hour = simulate_daily_demand(
        base_load_kw=base_load_kw, peak_load_kw=peak_load_kw, seed=seed
    )

    rows = []
    for hour, demand in demand_by_hour.items():
        total_generation = balancer.balance(hour, demand)
        renewable_generation = sum(
            s.generate_output(hour) for s in monitor.sources
            if s.category.value == "renovable"
        )
        renewable_ratio = (renewable_generation / total_generation) if total_generation else 0.0

        metrics = simulate_electrical_metrics(hour, demand, renewable_ratio)
        anomalies = detector.detect(
            hour, metrics["voltage"], metrics["current"], metrics["power_factor"]
        )
        for msg in anomalies:
            monitor.register_alert(msg)

        balancer.stabilize_voltage(hour, renewable_ratio, anomalies)

        reading = monitor.record_reading(
            hour, demand, total_generation,
            voltage=metrics["voltage"], current=metrics["current"],
            power_factor=metrics["power_factor"],
            technical_loss_kw=metrics["technical_loss_kw"],
        )
        invoice_item = billing.bill_reading(hour, demand, total_generation, renewable_generation)
        billing.record_technical_loss(
            hour, metrics["technical_loss_kw"], invoice_item["price_per_kwh"]
        )

        rows.append({
            "Hora": hour,
            "Demanda (kW)": demand,
            "Generación (kW)": total_generation,
            "Balance (kW)": reading["balance_kw"],
            "Voltaje (V)": round(metrics["voltage"], 1),
            "Corriente (A)": round(metrics["current"], 1),
            "Factor de potencia": round(metrics["power_factor"], 2),
            "Pérdida técnica (kW)": round(metrics["technical_loss_kw"], 2),
            "Tarifa": invoice_item["tariff"],
            "Costo ($)": invoice_item["cost"],
        })

    return monitor, billing, pd.DataFrame(rows)


# ---------------- Sidebar: configuración ----------------
st.sidebar.title("Configuración de la red")
st.sidebar.caption("Interfaz de demo — no forma parte de la arquitectura final.")

peak_threshold = st.sidebar.slider("Umbral de pico (kW)", 40, 120, 70, step=5)
base_load = st.sidebar.slider("Carga base (kW)", 10, 60, 30, step=5)
peak_load = st.sidebar.slider("Carga pico (kW)", 60, 150, 90, step=5)

usar_seed_fija = st.sidebar.checkbox("Usar semilla fija (resultado reproducible)", value=False)
if usar_seed_fija:
    seed = st.sidebar.number_input("Semilla de simulación", value=42, step=1)
else:
    seed = _random.randint(0, 100_000)
    st.sidebar.caption(f"Semilla usada en esta ejecución: {seed}")

st.sidebar.markdown("**Fuentes de energía registradas**")
solar_cap = st.sidebar.slider("Capacidad solar (kW)", 0, 100, 40, step=5)
wind_cap = st.sidebar.slider("Capacidad eólica (kW)", 0, 100, 25, step=5)
hydro_cap = st.sidebar.slider("Capacidad hidroeléctrica (kW)", 0, 100, 20, step=5)
thermal_cap = st.sidebar.slider("Capacidad térmica / respaldo (kW)", 0, 150, 60, step=5)

source_config = [
    ("solar", "Panel Solar Norte", solar_cap),
    ("eolica", "Turbina Eolica 1", wind_cap),
    ("hidroelectrica", "Mini Hidroelectrica", hydro_cap),
    ("termica", "Planta de Respaldo", thermal_cap),
]

run_clicked = st.sidebar.button("Ejecutar simulación de 24h", type="primary")

# ---------------- Cuerpo principal ----------------
st.title("Sistema de Gestión de Redes Inteligentes (Smart Grid)")
st.caption(
    "Demo visual desechable sobre la arquitectura real del proyecto "
    "(Singleton + Factory). Sin IoT: todos los datos son simulados."
)

if run_clicked or "df" not in st.session_state:
    monitor, billing, df = run_simulation(
        source_config, peak_threshold, base_load, peak_load, int(seed)
    )
    st.session_state["df"] = df
    st.session_state["monitor"] = monitor
    st.session_state["billing"] = billing

df = st.session_state["df"]
monitor = st.session_state["monitor"]
billing = st.session_state["billing"]

tab_monitoreo, tab_calidad, tab_fuentes, tab_facturacion = st.tabs(
    [" Monitoreo en tiempo real", " Calidad de la red", " Fuentes de energía", " Facturación dinámica"]
)

with tab_monitoreo:
    col1, col2, col3 = st.columns(3)
    col1.metric("Demanda promedio", f'{df["Demanda (kW)"].mean():.1f} kW')
    col2.metric("Generación promedio", f'{df["Generación (kW)"].mean():.1f} kW')
    col3.metric("Costo total del día", f'${billing.total_cost():.2f}')

    st.subheader("Demanda vs. Generación por hora")
    st.line_chart(df.set_index("Hora")[["Demanda (kW)", "Generación (kW)"]])

    st.subheader("Balance de la red (Generación - Demanda)")
    st.bar_chart(df.set_index("Hora")["Balance (kW)"])

    st.subheader("Historial de lecturas (GridMonitor - Singleton)")
    st.dataframe(df, use_container_width=True, hide_index=True)

    if monitor.alerts:
        st.subheader("Alertas y anomalías detectadas")
        st.caption(
            "Incluye picos de demanda, anomalías de voltaje/corriente/factor de "
            "potencia (AnomalyDetector) y ajustes de estabilización de voltaje."
        )
        for alert in monitor.alerts:
            st.warning(alert)
    else:
        st.info("No se generaron alertas ni anomalías en esta simulación.")

with tab_calidad:
    st.subheader("Estado eléctrico de la red por hora")
    st.caption(
        "Voltaje, corriente y factor de potencia simulados (sin sensores/IoT), "
        "usados por AnomalyDetector para detectar fallas tempranas."
    )

    col1, col2, col3 = st.columns(3)
    col1.metric("Voltaje promedio", f'{df["Voltaje (V)"].mean():.1f} V')
    col2.metric("Factor de potencia promedio", f'{df["Factor de potencia"].mean():.2f}')
    col3.metric("Pérdidas técnicas del día", f'{df["Pérdida técnica (kW)"].sum():.1f} kWh')

    st.subheader("Voltaje por hora (banda normal: ±5% de 220V)")
    st.line_chart(df.set_index("Hora")["Voltaje (V)"])

    st.subheader("Factor de potencia por hora")
    st.line_chart(df.set_index("Hora")["Factor de potencia"])

    st.subheader("Pérdidas técnicas estimadas por hora")
    st.bar_chart(df.set_index("Hora")["Pérdida técnica (kW)"])

    st.caption(
        f"Pérdida técnica total del día: {billing.total_technical_loss_kwh():.2f} kWh "
        f"(equivalente a ${billing.total_technical_loss_cost():.2f} en energía generada "
        f"que nunca se facturó)."
    )

with tab_fuentes:
    st.subheader("Fuentes registradas (creadas vía EnergySourceFactory)")
    for s in monitor.sources:
        with st.container(border=True):
            c1, c2, c3 = st.columns([2, 1, 1])
            c1.markdown(f"**{s.name}**")
            c2.markdown(f"Categoría: `{s.category.value}`")
            c3.markdown(f"Capacidad: **{s.capacity_kw} kW**")

    st.caption(
        "Agregar una nueva fuente (por ejemplo, geotérmica) no requiere modificar "
        "esta pantalla ni el código de LoadBalancer: solo registrar el nuevo tipo "
        "en EnergySourceFactory."
    )

with tab_facturacion:
    st.subheader("Resumen de facturación por tipo de tarifa")
    summary = billing.summary_by_tariff()
    summary_df = pd.DataFrame(
        [{"Tarifa": k, "Costo ($)": v} for k, v in summary.items()]
    )
    st.dataframe(summary_df, use_container_width=True, hide_index=True)
    st.bar_chart(summary_df.set_index("Tarifa"))

    st.subheader("Detalle de facturación por hora")
    st.dataframe(
        df[["Hora", "Demanda (kW)", "Tarifa", "Costo ($)"]],
        use_container_width=True,
        hide_index=True,
    )

    col1, col2 = st.columns(2)
    col1.metric("Costo total del día", f'${billing.total_cost():.2f}')
    col2.metric(
        "Pérdidas técnicas (no facturadas)",
        f'${billing.total_technical_loss_cost():.2f}',
        help="Energía generada que se perdió en transmisión y nunca llegó a facturarse al cliente."
    )
