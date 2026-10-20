import random as _random
import pandas as pd
import streamlit as st

# Importamos el Facade (¡la pieza clave!)
from core.smart_grid_facade import SmartGridFacade
from core.grid_composite import GridSector
from core.adapters import JSONConfigAdapter, CSVConfigAdapter
from simulation.consumption_flyweight import ConsumptionProfileFactory
from billing.calculation import (
    PerKWhCalculation, TimeOfUseCalculation,
    DemandChargeCalculation, ReactivePenaltyCalculation,
)

st.set_page_config(page_title="Smart Grid · Panel de operación",
                   layout="wide")


# =====================================================================
# Función auxiliar: convierte el DataFrame del Facade a un DataFrame de pandas
# =====================================================================
def build_dataframe_from_monitor(monitor, billing):
    """Extrae el historial del monitor y lo convierte en un DataFrame para la UI."""
    history = monitor.get_history()
    rows = []
    for reading in history:
        hour = reading["hour"]
        invoice_item = next(
            (item for item in billing.invoice_items if item["hour"] == hour),
            None
        )
        rows.append({
            "Hora": hour,
            "Demanda (kW)": reading["demand_kw"],
            "Generación (kW)": reading["generation_kw"],
            "Balance (kW)": reading["balance_kw"],
            "Voltaje (V)": reading["voltage"],
            "Corriente (A)": reading["current"],
            "Factor de potencia": reading["power_factor"],
            "Pérdida técnica (kW)": reading["technical_loss_kw"],
            "Tarifa": invoice_item["tariff"] if invoice_item else "N/A",
            "Cálculo": invoice_item["calculation"] if invoice_item else "N/A",
            "Decoradores": ", ".join(invoice_item["decorators"]) if invoice_item else "N/A",
            "Costo ($)": invoice_item["cost"] if invoice_item else 0.0,
        })
    return pd.DataFrame(rows)


# =====================================================================
# Función auxiliar: dibuja el árbol Composite en Streamlit
# =====================================================================
def render_tree(node, level=0):
    """Dibuja recursivamente un GridSector o SourceLeaf en Streamlit."""
    indent = "&nbsp;" * (level * 4)

    # Comprobamos si es un sector (tiene hijos)
    if hasattr(node, "children"):
        st.markdown(f"{indent}**{node.name}**", unsafe_allow_html=True)
        for child in node.children:
            render_tree(child, level + 1)
    else:
        # Es un SourceLeaf (tiene atributo 'source')
        icon = "🌱" if node.source.category.value == "renovable" else ""
        st.markdown(
            f"{indent}{icon} `{node.source.name}` "
            f"({node.source.category.value}, {node.source.capacity_kw} kW)",
            unsafe_allow_html=True
        )
# =====================================================================
# Sidebar — configuración del operador
# =====================================================================

st.sidebar.title("Panel de operación")
st.sidebar.caption("Configura la red y ejecuta la simulación del día.")

# --- Configuración de entrada ---
st.sidebar.subheader("Configuración de la red")
modo_config = st.sidebar.radio(
    "¿Cómo quieres definir la red?",
    [
        "Manual (ajustar capacidades)",
        "Cargar archivo del proyecto (JSON)",
        "Cargar archivo del proyecto (CSV)",
        "Subir archivo propio (JSON o CSV)",
    ],
    index=0,
    help="Puedes armar la red tú mismo, cargar un archivo del proyecto, "
         "o subir tu propio archivo JSON/CSV."
)

external_config = None

# ============ OPCIÓN 1: JSON del proyecto ============
if modo_config == "Cargar archivo del proyecto (JSON)":
    try:
        external_config = JSONConfigAdapter().load("configs/utility_example.json")
        st.sidebar.success("Configuración cargada desde JSON del proyecto.")
    except FileNotFoundError:
        st.sidebar.error("No se encontró configs/utility_example.json")

# ============ OPCIÓN 2: CSV del proyecto ============
elif modo_config == "Cargar archivo del proyecto (CSV)":
    try:
        external_config = CSVConfigAdapter().load("configs/scada_example.csv")
        st.sidebar.success("Configuración cargada desde CSV del proyecto.")
    except FileNotFoundError:
        st.sidebar.error("No se encontró configs/scada_example.csv")

# ============ OPCIÓN 3: SUBIR ARCHIVO PROPIO ============
elif modo_config == "Subir archivo propio (JSON o CSV)":
    # --- Botones de descarga de ejemplos (para que el usuario sepa el formato) ---
    st.sidebar.markdown("**Descarga un ejemplo para ver el formato esperado:**")

    col1, col2 = st.sidebar.columns(2)
    with col1:
        try:
            with open("configs/utility_example.json", "rb") as f:
                st.download_button(
                    "📄 JSON ejemplo",
                    data=f,
                    file_name="utility_example.json",
                    mime="application/json",
                    use_container_width=True,
                )
        except FileNotFoundError:
            st.caption("(ejemplo JSON no disponible)")

    with col2:
        try:
            with open("configs/scada_example.csv", "rb") as f:
                st.download_button(
                    "📄 CSV ejemplo",
                    data=f,
                    file_name="scada_example.csv",
                    mime="text/csv",
                    use_container_width=True,
                )
        except FileNotFoundError:
            st.caption("(ejemplo CSV no disponible)")

    # --- File uploader ---
    uploaded_file = st.sidebar.file_uploader(
        "Sube tu archivo de configuración",
        type=["json", "csv"],
        help="El archivo debe tener la estructura esperada por el Adapter."
    )

    if uploaded_file is not None:
        import tempfile
        import os

        suffix = ".json" if uploaded_file.name.endswith(".json") else ".csv"

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(uploaded_file.read())
            tmp_path = tmp.name

        try:
            if suffix == ".json":
                adapter = JSONConfigAdapter()
            else:
                adapter = CSVConfigAdapter()

            external_config = adapter.load(tmp_path)
            st.sidebar.success(
                f" Archivo '{uploaded_file.name}' cargado correctamente "
                f"({adapter.describe()})."
            )
        except Exception as e:
            st.sidebar.error(f" Error al procesar el archivo: {e}")
        finally:
            os.unlink(tmp_path)  # Limpiamos el archivo temporal

# --- Esquema tarifario (Bridge: Implementor) ---
st.sidebar.subheader("Esquema tarifario")
esquema = st.sidebar.selectbox(
    "¿Cómo se cobra la energía?",
    [
        "Por consumo (kWh)",
        "Por horario (punta / valle)",
        "Con cargo por demanda pico",
        "Con recargo por baja calidad (FP)",
    ],
    help="Determina cómo se calcula el costo de cada lectura horaria (Bridge)."
)
CALCULOS = {
    "Por consumo (kWh)": PerKWhCalculation(),
    "Por horario (punta / valle)": TimeOfUseCalculation(),
    "Con cargo por demanda pico": DemandChargeCalculation(charge_per_kw=5.0),
    "Con recargo por baja calidad (FP)": ReactivePenaltyCalculation(min_pf=0.90),
}
selected_calc = CALCULOS[esquema]

# --- Flyweight (perfil de consumo) ---
st.sidebar.subheader("Perfil de consumo")
usar_flyweight = st.sidebar.checkbox(
    "Usar perfiles compartidos (Flyweight)",
    value=False,
    help="Ahorra memoria reutilizando curvas de consumo base."
)
perfil_flyweight = st.sidebar.selectbox(
    "Tipo de perfil",
    ["residencial", "comercial", "industrial"],
    disabled=not usar_flyweight
)

# --- Rol de usuario (Proxy) ---
st.sidebar.subheader("Rol de usuario (Proxy)")
rol_usuario = st.sidebar.selectbox(
    "Rol",
    ["admin", "operator", "invitado"],
    help="Controla qué operaciones puedes realizar (Proxy)."
)
if rol_usuario == "admin":
    st.sidebar.success(" Admin: control total.")
elif rol_usuario == "operator":
    st.sidebar.info(" Operator: puede registrar fuentes, no resetear.")
else:
    st.sidebar.warning("Invitado: solo lectura.")

# --- Parámetros de la red ---
if external_config is None:
    st.sidebar.subheader("Demanda esperada")
    peak_threshold = st.sidebar.slider("Umbral de pico (kW)", 40, 120, 70, step=5)
    base_load = st.sidebar.slider("Consumo base (kW)", 10, 60, 30, step=5)
    peak_load = st.sidebar.slider("Consumo pico (kW)", 60, 150, 90, step=5)

    st.sidebar.subheader("Reproducibilidad")
    usar_seed_fija = st.sidebar.checkbox("Usar semilla fija", value=False)
    if usar_seed_fija:
        seed = st.sidebar.number_input("Semilla", value=42, step=1)
    else:
        seed = _random.randint(0, 100_000)
        st.sidebar.caption(f"Semilla usada: {seed}")

    st.sidebar.subheader("Fuentes de generación")
    solar_cap = st.sidebar.slider("Solar (kW)", 0, 100, 40, step=5)
    wind_cap = st.sidebar.slider("Eólica (kW)", 0, 100, 25, step=5)
    hydro_cap = st.sidebar.slider("Hidroeléctrica (kW)", 0, 100, 20, step=5)
    thermal_cap = st.sidebar.slider("Térmica de respaldo (kW)", 0, 150, 60, step=5)

    source_config = [
        ("solar", "Panel Solar Norte", solar_cap),
        ("eolica", "Turbina Eolica 1", wind_cap),
        ("hidroelectrica", "Mini Hidroelectrica", hydro_cap),
        ("termica", "Planta de Respaldo", thermal_cap),
    ]
else:
    peak_threshold = external_config.peak_threshold_kw
    base_load = external_config.base_load_kw
    peak_load = external_config.peak_load_kw
    seed = external_config.seed
    source_config = external_config.sources_spec

run_clicked = st.sidebar.button("▶ Ejecutar simulación de 24 h",
                                type="primary", use_container_width=True)


# =====================================================================
# Cuerpo principal
# =====================================================================

st.title("Smart Grid · Panel de operación")
st.caption("Simulación de 24 horas de una red de distribución con fuentes renovables.")

# Reiniciamos las estadísticas del Flyweight en cada nueva simulación
if run_clicked:
    ConsumptionProfileFactory.reset_stats()

if run_clicked or "df" not in st.session_state:
    # Construimos la configuración usando el Builder (igual que en main.py)
    from core.grid_builder import GridBuilder
    builder = GridBuilder()
    for (t, n, c) in source_config:
        builder.add_source(t, n, c)
    config = (builder
              .set_peak_threshold(peak_threshold)
              .set_demand_curve(base_load_kw=base_load, peak_load_kw=peak_load)
              .set_seed(int(seed))
              .build())

    # ---- LLAMADA AL FACADE (¡La clave de todo!) ----
    facade = SmartGridFacade(calculation=selected_calc, user_role=rol_usuario)

    try:
        billing, monitor = facade.run_simulation_cycle(
            config, verbose=False,
            use_flyweight=usar_flyweight,
            profile_type=perfil_flyweight
        )
    except PermissionError as e:
        st.error(f" El Proxy bloqueó la operación: {e}")
        st.stop()

    # Guardamos los resultados en session_state para que persistan
    st.session_state.update({
        "billing": billing,
        "monitor": monitor,
        "df": build_dataframe_from_monitor(monitor, billing),
        "facade": facade,
        "config_usada": {
            "modo": modo_config,
            "esquema": esquema,
            "peak_threshold": peak_threshold,
            "base_load": base_load,
            "peak_load": peak_load,
            "seed": seed,
            "sources": source_config,
            "flyweight": usar_flyweight,
            "perfil": perfil_flyweight if usar_flyweight else "N/A",
            "rol": rol_usuario,
        }
    })

df = st.session_state["df"]
monitor = st.session_state["monitor"]
billing = st.session_state["billing"]
facade = st.session_state["facade"]
cfg_usada = st.session_state["config_usada"]


# ---------- KPIs superiores ----------
k1, k2, k3, k4 = st.columns(4)
k1.metric("Demanda promedio", f'{df["Demanda (kW)"].mean():.1f} kW')
k2.metric("Generación promedio", f'{df["Generación (kW)"].mean():.1f} kW')
k3.metric("Cobertura renovable", f'{(df["Generación (kW)"].sum() / df["Demanda (kW)"].sum() * 100):.1f} %')
k4.metric("Costo total del día", f'${billing.total_cost():.2f}')

st.divider()


# ---------- Pestañas orientadas al negocio ----------
t1, t2, t3, t4, t5, t6 = st.tabs([
    "Resumen del día",
    "Operación de la red",
    "Fuentes y renovables",
    "Topología de red",
    "Facturación",
    "Configuración",
])


# =========================================================
# 1) RESUMEN DEL DÍA
# =========================================================
with t1:
    st.subheader("Demanda vs. Generación")
    st.line_chart(df.set_index("Hora")[["Demanda (kW)", "Generación (kW)"]])

    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Balance horario")
        st.bar_chart(df.set_index("Hora")["Balance (kW)"])
    with col_b:
        st.subheader("Pérdidas técnicas por hora")
        st.bar_chart(df.set_index("Hora")["Pérdida técnica (kW)"])

    st.subheader("Puntos clave del día")
    hora_max_demanda = int(df.loc[df["Demanda (kW)"].idxmax(), "Hora"])
    c1, c2, c3 = st.columns(3)
    c1.info(f"**Mayor demanda:** {hora_max_demanda:02d}:00 ({df['Demanda (kW)'].max():.1f} kW)")
    c2.info(f"**Mayor generación:** {int(df.loc[df['Generación (kW)'].idxmax(), 'Hora']):02d}:00")
    c3.warning(f"**Mayor déficit:** {int(df.loc[df['Balance (kW)'].idxmin(), 'Hora']):02d}:00")


# =========================================================
# 2) OPERACIÓN DE LA RED
# =========================================================
with t2:
    st.subheader("Estado eléctrico de la red")
    col1, col2, col3 = st.columns(3)
    col1.metric("Voltaje promedio", f'{df["Voltaje (V)"].mean():.1f} V')
    col2.metric("Factor de potencia promedio", f'{df["Factor de potencia"].mean():.2f}')
    col3.metric("Pérdidas técnicas", f'{df["Pérdida técnica (kW)"].sum():.1f} kWh')

    st.markdown("**Voltaje horario** (nominal 220 V ± 5 %)")
    st.line_chart(df.set_index("Hora")["Voltaje (V)"])
    st.markdown("**Factor de potencia** (mínimo 0.90)")
    st.line_chart(df.set_index("Hora")["Factor de potencia"])

    if monitor.get_alerts():
        st.subheader("Alertas operativas")
        for alert in monitor.get_alerts():
            st.warning(alert)
    else:
        st.success("Sin alertas ni anomalías en la simulación.")


# =========================================================
# 3) FUENTES Y RENOVABLES
# =========================================================
with t3:
    st.subheader("Fuentes de generación de la red")
    for s in monitor.sources:
        with st.container(border=True):
            c1, c2, c3 = st.columns([3, 1, 1])
            c1.markdown(f"**{s.name}**")
            c2.markdown(f"Categoría: `{s.category.value}`")
            c3.markdown(f"Capacidad: **{s.capacity_kw} kW**")

    st.subheader("Aporte de cada fuente en el día")
    contrib = []
    for s in monitor.sources:
        aporte = sum(s.generate_output(h) for h in range(24))
        contrib.append({"Fuente": s.name, "Energía (kWh)": round(aporte, 2)})
    contrib_df = pd.DataFrame(contrib)
    st.dataframe(contrib_df, use_container_width=True, hide_index=True)
    st.bar_chart(contrib_df.set_index("Fuente"))


# =========================================================
# 4) TOPOLOGÍA (COMPOSITE)
# ========================================================
with t4:
    root = facade.get_root_sector()
    if root is not None:
        render_tree(root)

        st.divider()
        st.markdown("**Demostración: el mismo método para hojas y ramas**")
        col1, col2, col3 = st.columns(3)
        col1.metric(
            "Generación red completa (hora 12)",
            f"{root.get_generation(12):.2f} kW"
        )
        col2.metric(
            "Generación sector renovable (hora 12)",
            f"{facade.get_sector_renovables().get_generation(12):.2f} kW"
        )
        col3.metric(
            "Generación sector convencional (hora 12)",
            f"{facade.get_sector_convencional().get_generation(12):.2f} kW"
        )


    else:
        st.warning("Ejecuta una simulación para ver la topología.")


# =========================================================
# 5) FACTURACIÓN
# =========================================================
with t5:
    st.subheader(f"Facturación del día · {esquema}")
    st.caption("El costo combina la tarifa base (Bridge) con descuentos/recargos (Decorator).")

    col1, col2 = st.columns(2)
    col1.metric("Costo total", f'${billing.total_cost():.2f}')
    col2.metric("Pérdidas técnicas (no facturadas)",
                f'${billing.total_technical_loss_cost():.2f}')

    st.markdown("**Costo por tipo de tarifa**")
    summary = billing.summary_by_tariff()
    st.dataframe(pd.DataFrame([{"Tarifa": k, "Costo ($)": v} for k, v in summary.items()]),
                 use_container_width=True, hide_index=True)

    st.markdown("**Detalle horario con decoradores aplicados (Patrón Decorator)**")
    st.dataframe(
        df[["Hora", "Demanda (kW)", "Tarifa", "Decoradores", "Costo ($)"]],
        use_container_width=True, hide_index=True
    )

    # Flyweight stats
    if cfg_usada["flyweight"]:
        st.divider()
        st.subheader("📊 Estadísticas del Flyweight")
        stats = ConsumptionProfileFactory.stats()
        col1, col2, col3 = st.columns(3)
        col1.metric("Perfiles creados", stats["perfiles_creados"])
        col2.metric("Perfiles reutilizados", stats["perfiles_reutilizados"])
        col3.metric("Objetos únicos en caché", stats["total_objetos_unicos"])
        st.caption(
            f"Perfiles en caché: {', '.join(stats['perfiles_en_cache'])}. "
            "El estado intrínseco (la curva base) se comparte entre todas las "
            "simulaciones del mismo tipo. El estado extrínseco (hora, semilla) "
            "varía en cada llamada."
        )


# =========================================================
# 6) CONFIGURACIÓN CARGADA
# =========================================================
with t6:
    st.subheader("Configuración usada")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Origen:**"); st.write(cfg_usada["modo"])
        st.markdown("**Esquema tarifario:**"); st.write(cfg_usada["esquema"])
        st.markdown("**Umbral de pico:**"); st.write(f'{cfg_usada["peak_threshold"]} kW')
        st.markdown("**Semilla:**"); st.write(cfg_usada["seed"])
        st.markdown("**Flyweight:**"); st.write(f'{cfg_usada["flyweight"]} ({cfg_usada["perfil"]})')
        st.markdown("**Rol (Proxy):**"); st.write(cfg_usada["rol"])
    with col2:
        st.markdown("**Fuentes en la red:**")
        st.dataframe(pd.DataFrame(
            [{"Tipo": t, "Nombre": n, "Capacidad (kW)": c} for (t, n, c) in cfg_usada["sources"]]
        ), use_container_width=True, hide_index=True)

    st.divider()
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("⬇ Descargar lecturas (CSV)", data=csv,
                       file_name="smart_grid_resultados.csv", mime="text/csv")