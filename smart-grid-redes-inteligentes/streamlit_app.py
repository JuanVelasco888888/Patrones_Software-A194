"""Red Inteligente: simulador de operación de una red eléctrica (interfaz Streamlit).

Para cambiar la tipografía de toda la interfaz basta con editar FUENTE
(cualquier nombre de https://fonts.google.com).
"""
import time

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from billing.methods import BILLING_METHODS, method_name_of
from core.access_control import DEFAULT_ROLE_PERMISSIONS, Permission, Role
from core.adapters import CSVConfigAdapter, JSONConfigAdapter
from core.config_source import ConfigFileError
from core.grid_builder import GridBuilder
from core.grid_iterators import ReadingIterator
from core.smart_grid_facade import SmartGridFacade
from simulation.consumption_flyweight import ConsumptionProfileFactory

FUENTE = "Nunito Sans"

st.set_page_config(page_title="Red Inteligente", page_icon="⚡", layout="wide")

# ---------------------------------------------------------------- estilo
VERDE_OSCURO, VERDE, AMBAR, ROJO, AZUL, GRIS = (
    "#0f3d2e", "#1f9d6b", "#f2a33a", "#d94f4f", "#3b82c4", "#9aa8a0")
_URL_FUENTE = FUENTE.replace(" ", "+")
st.markdown(
    f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family={_URL_FUENTE}:wght@400;600;700;800&display=swap');
    html, body, .stApp, .stApp p, .stApp li, .stApp label, .stApp h1, .stApp h2, .stApp h3,
    .stApp h4, .stApp button, .stApp input, .stApp textarea, .stApp [data-baseweb="tab"],
    .stApp [data-testid="stMarkdownContainer"], .stApp [data-testid="stMetricValue"],
    .stApp [data-testid="stMetricLabel"], .stApp [data-testid="stCaptionContainer"] {{
        font-family: '{FUENTE}', system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif !important;
    }}
    .block-container {{ padding-top: 1.6rem; max-width: 1280px; }}
    .stApp h1 {{ font-weight: 800; letter-spacing: -0.01em; color: {VERDE_OSCURO}; }}
    .stApp h2, .stApp h3, .stApp h4 {{ font-weight: 700; color: {VERDE_OSCURO}; }}
    [data-baseweb="tab"] {{ font-weight: 600; }}
    [data-testid="stMetric"] {{
        background: #fff; border: 1px solid #e0e9e3; border-radius: 14px;
        padding: 14px 16px; box-shadow: 0 1px 3px rgba(15,61,46,.06);
    }}
    [data-testid="stMetricLabel"] p {{ color: #5b7367; font-size: .85rem; }}
    
    /* --- BARRA LATERAL --- */
    [data-testid="stSidebar"] {{ background: {VERDE_OSCURO}; }}
    
    /* Aplicamos color claro SOLO a textos, párrafos, listas, labels y encabezados (evitamos inputs) */
    [data-testid="stSidebar"] p, 
    [data-testid="stSidebar"] li, 
    [data-testid="stSidebar"] label, 
    [data-testid="stSidebar"] h1, 
    [data-testid="stSidebar"] h2, 
    [data-testid="stSidebar"] h3, 
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"], 
    [data-testid="stSidebar"] [data-testid="stCaptionContainer"] {{ color: #e6f4ec !important; }}
    
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {{ color: #fff !important; }}
    
    /* Estilo del selectbox (cerrado) - Fondo verde oscuro y texto claro */
    [data-testid="stSidebar"] [data-baseweb="select"] > div {{ 
        background: #174d3b !important; 
        border-color: #2a6a52 !important; 
    }}
    [data-testid="stSidebar"] [data-baseweb="select"] * {{ color: #e6f4ec !important; }}
    
    /* Estilo del menú desplegable (popover) - Fondo blanco y texto oscuro */
    div[data-baseweb="popover"] [role="listbox"] {{ background: #ffffff !important; }}
    div[data-baseweb="popover"] [role="listbox"] li,
    div[data-baseweb="popover"] [role="listbox"] span,
    div[data-baseweb="popover"] [role="listbox"] div {{ color: #0f3d2e !important; }}
    
    /* Subida de archivos */
    [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] {{ background: #174d3b; border-color: #2a6a52; }}
    [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] * {{ color: #cfe8da !important; }}
    
    /* Botones */
    [data-testid="stSidebar"] button[kind="primary"] {{
        background: #3ecf8e; color: {VERDE_OSCURO}; border: none; font-weight: 700; }}
    [data-testid="stSidebar"] button[kind="primary"] p {{ color: {VERDE_OSCURO} !important; }}
    [data-testid="stSidebar"] button[kind="secondary"] {{ background: #174d3b; border: 1px solid #2a6a52; }}
    [data-testid="stSidebar"] hr {{ border-color: #2a6a52; }}
    
    /* Tarjetas */
    .tarjeta-modulo {{
        background: #fff; border: 1px solid #e0e9e3; border-radius: 14px; padding: 18px 20px; height: 100%;
    }}
    .tarjeta-modulo h4 {{ margin: 0 0 6px 0; }}
    .tarjeta-modulo p {{ margin: 0; color: #4d6657; font-size: .95rem; }}
    </style>
    """,
    unsafe_allow_html=True,
)
# ---------------------------------------------------------------- textos
ROLES = {
    "Administrador (puede hacer todo)": "admin",
    "Operador (puede operar la red)": "operator",
    "Invitado (solo puede mirar)": "guest",
}
ROL_NOMBRE = {v: k.split(" (")[0] for k, v in ROLES.items()}

DEMANDAS = {
    "La indicada en la configuración": (False, "comercial"),
    "Residencial (casas)": (True, "residencial"),
    "Comercial (negocios)": (True, "comercial"),
    "Industrial (fábricas)": (True, "industrial"),
}

SITUACION = {"Normal": "🟢 Normal", "Pico": "🟠 Pico", "Emergencia": "🔴 Emergencia"}
COLOR_SITUACION = {"Normal": VERDE, "Pico": AMBAR, "Emergencia": ROJO}

MODOS = {
    None: "Automático (la red decide según la situación)",
    "gestion de picos": "Gestión de picos (usa respaldo solo si la demanda pasa el límite)",
    "cobertura total": "Cobertura total (usa respaldo siempre que falte energía)",
}

TIPO_FUENTE = {
    "SolarSource": "Solar", "WindSource": "Eólica", "HydroSource": "Hidroeléctrica",
    "GeothermalSource": "Geotérmica", "BatterySource": "Baterías", "ThermalSource": "Térmica (respaldo)",
}
COLOR_FUENTE = {
    "Solar": "#f2c14e", "Eólica": "#5bb8d4", "Hidroeléctrica": "#2f7fc1",
    "Geotérmica": "#b5651d", "Baterías": "#8e6bbf", "Térmica (respaldo)": "#7a7f85",
}

ACCIONES_REGISTRO = {
    "register_source": "Registrar una fuente", "set_source_active": "Encender/apagar una fuente",
    "record_reading": "Guardar una lectura", "register_alert": "Registrar una alerta",
    "reset": "Reiniciar el sistema", "create_memento": "Guardar punto (interno)",
    "restore_memento": "Restaurar punto (interno)", "save_checkpoint": "Guardar punto de guardado",
    "restore_checkpoint": "Volver a un punto de guardado", "change_peak_threshold": "Cambiar el límite de pico",
    "set_strategy": "Cambiar el modo de respaldo", "export_snapshot": "Exportar datos",
    "report_source_failure": "Simular una falla", "repair_source": "Reparar una fuente",
    "set_flexible_load": "Mover consumo flexible", "change_billing_method": "Cambiar la forma de cobro",
    "probar_permiso_reinicio": "Prueba: ¿puedo reiniciar?",
}
LECTURAS = {"get_history", "get_alerts", "sources", "audit_trail", "subscribe", "unsubscribe"}


# ---------------------------------------------------------------- utilidades
def tabla(df: pd.DataFrame) -> None:
    """Muestra una tabla a todo el ancho sin depender de la versión de Streamlit."""
    for kwargs in ({"width": "stretch"}, {"use_container_width": True}, {}):
        try:
            st.dataframe(df, hide_index=True, **kwargs)
            return
        except TypeError:
            continue


def grafico(fig: go.Figure, clave: str = None) -> None:
    fig.update_layout(
        margin=dict(l=10, r=10, t=30, b=10), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=f"{FUENTE}, sans-serif", color="#16301f"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
    )
    fig.update_xaxes(gridcolor="#e6eee9", zeroline=False)
    fig.update_yaxes(gridcolor="#e6eee9", zeroline=False)
    for kwargs in ({"width": "stretch"}, {"use_container_width": True}, {}):
        try:
            st.plotly_chart(fig, key=clave, **kwargs)
            return
        except TypeError:
            continue


def volver_a_dibujar() -> None:
    (getattr(st, "rerun", None) or st.experimental_rerun)()


def aviso(clave: str, tipo: str, texto: str) -> None:
    st.session_state[f"aviso_{clave}"] = (tipo, texto)


def mostrar_aviso(clave: str) -> None:
    pendiente = st.session_state.pop(f"aviso_{clave}", None)
    if pendiente:
        tipo, texto = pendiente
        getattr(st, tipo)(texto)


def estado_actual(facade: SmartGridFacade) -> dict:
    horas = facade.get_hour_results()
    return {
        "costo": facade.get_billing().total_cost(),
        "sin_energia": sum(1 for r in horas if r.reading["balance_kw"] < 0),
        "alertas": len(facade.monitor.get_alerts()),
        "pico_kw": max(r.reading["demand_kw"] for r in horas),
    }


def comparar(antes: dict, despues: dict) -> str:
    dc = despues["costo"] - antes["costo"]
    return (
        f"**Efecto en la red:** costo del día ${antes['costo']:.2f} → ${despues['costo']:.2f} "
        f"({'+' if dc >= 0 else ''}{dc:.2f}) · horas con falta de energía "
        f"{antes['sin_energia']} → {despues['sin_energia']} · alertas "
        f"{antes['alertas']} → {despues['alertas']} · pico de demanda "
        f"{antes['pico_kw']:.1f} → {despues['pico_kw']:.1f} kW"
    )


def aplicar(facade, clave: str, accion, mensaje_ok: str, pista_sin_efecto: bool = False) -> None:
    """Ejecuta un cambio, guarda el resultado y redibuja para que TODAS las pestañas se actualicen."""
    antes = estado_actual(facade)
    try:
        accion()
    except PermissionError:
        aviso(clave, "error", "Tu rol no tiene permiso para hacer este cambio. "
                              "Elige Administrador u Operador en la barra lateral y ejecuta de nuevo.")
    except Exception as e:  # noqa: BLE001 - se muestra el motivo al usuario
        aviso(clave, "error", str(e))
    else:
        despues = estado_actual(facade)
        texto = f"{mensaje_ok}\n\n{comparar(antes, despues)}"
        if pista_sin_efecto and antes == despues:
            texto += ("\n\nNo se notó ningún cambio: este ajuste solo influye cuando se necesitan "
                      "fuentes de respaldo y hay alguna encendida.")
        aviso(clave, "success", texto)
    volver_a_dibujar()


def leer_ejemplo(ruta: str):
    try:
        with open(ruta, "rb") as f:
            return f.read()
    except OSError:
        return None


def hhmm(h: int) -> str:
    return f"{h:02d}:00"


def fmt_pct(x: float) -> str:
    return f"{x:.0%}"


# ---------------------------------------------------------------- barra lateral
with st.sidebar:
    st.markdown("## ⚡ Red Inteligente")
    st.caption("Simulador de operación de una red eléctrica")
    st.divider()

    st.markdown("**Paso 1 · ¿Con qué rol vas a trabajar?**")
    rol_texto = st.selectbox("Rol", list(ROLES), label_visibility="collapsed",
                             help="El rol define qué acciones puedes hacer. Se aplica al ejecutar la simulación.")
    rol = ROLES[rol_texto]

    st.markdown("**Paso 2 · ¿De dónde salen los datos de la red?**")
    origen = st.radio("Origen", ["Red de ejemplo", "Subir archivo JSON", "Subir archivo CSV"],
                      label_visibility="collapsed")
    config, origen_texto = None, ""
    if origen == "Red de ejemplo":
        config, origen_texto = GridBuilder.default_template(), "Red de ejemplo"
        st.caption(f"Una red pequeña ya preparada: {len(config.sources_spec)} fuentes de energía.")
    else:
        es_json = origen.endswith("JSON")
        adaptador = JSONConfigAdapter() if es_json else CSVConfigAdapter()
        archivo = st.file_uploader(
            "Arrastra aquí tu archivo o búscalo en tu equipo",
            type=["json"] if es_json else ["csv"], key="subida_json" if es_json else "subida_csv",
        )
        ejemplo = leer_ejemplo("configs/utility_example.json" if es_json else "configs/scada_example.csv")
        if ejemplo:
            st.download_button(
                "⬇ Descargar un archivo de ejemplo", ejemplo,
                file_name="ejemplo_red.json" if es_json else "ejemplo_red.csv",
                mime="application/json" if es_json else "text/csv",
            )
        with st.expander("¿Cómo debe ser el archivo?"):
            if es_json:
                st.markdown(
                    "Un JSON con tres partes:\n"
                    "- **generators**: la lista de fuentes. Cada una con `type` (solar, eolica, "
                    "hidroelectrica, geotermica, bateria o termica), `label` (su nombre) y `cap_kw` (potencia en kW).\n"
                    "- **thresholds.peak_kw**: el límite de pico en kW.\n"
                    "- **demand**: `off_peak_kw` (consumo mínimo) y `on_peak_kw` (consumo máximo).\n\n"
                    "Opcional: `random_seed` (número que hace repetible la simulación)."
                )
            else:
                st.markdown(
                    "Una tabla separada por `;` o `,` con las columnas "
                    "`tipo_fila;tipo_fuente;nombre;potencia_w;clave;valor`.\n"
                    "- Fila de **fuente**: `fuente;solar;Parque Norte;60000;;` (la potencia va en **vatios**).\n"
                    "- Fila de **parámetro**: `parametro;;;;umbral_pico_kw;95`. Claves válidas: "
                    "`umbral_pico_kw`, `carga_base_kw`, `carga_pico_kw`, `semilla`.\n\n"
                    "Lo más fácil: descarga el ejemplo, ábrelo en Excel y cámbialo."
                )
        if archivo is not None:
            try:
                config = adaptador.load_from_bytes(archivo.getvalue())
                origen_texto = archivo.name
                st.success(f"Archivo leído: {len(config.sources_spec)} fuentes de energía, "
                           f"límite de pico {config.peak_threshold_kw:g} kW.")
            except ConfigFileError as e:
                st.error(f"No se pudo usar el archivo. {e}")
        else:
            st.info("Sube un archivo para continuar.")

    st.markdown("**Paso 3 · ¿Cómo se cobra la energía?**")
    calculo_nombre = st.selectbox("Forma de cobro", list(BILLING_METHODS), label_visibility="collapsed")
    st.caption(BILLING_METHODS[calculo_nombre][1])

    st.markdown("**Paso 4 · ¿Cómo es la demanda del día?**")
    demanda_nombre = st.selectbox("Demanda", list(DEMANDAS), label_visibility="collapsed",
                                  help="La demanda es la energía que pide la gente. Puedes usar la del archivo "
                                       "o un tipo de consumo predefinido.")
    usar_perfil, tipo_perfil = DEMANDAS[demanda_nombre]

    st.markdown("**Paso 5 · ¿Cuánto consumo se puede mover a otra hora?**")
    flexible = st.slider("Consumo flexible (%)", 0, 100, 30, step=5, label_visibility="collapsed",
                         help="Cuando la demanda pasa el límite de pico, este porcentaje del exceso se "
                              "traslada a horas con menos demanda. 0 = no mover nada.")
    st.caption("Aplana los picos: el consumo que se puede reprogramar (por ejemplo, procesos industriales) "
               "se mueve a horas más tranquilas. La energía total del día no cambia.")

    st.divider()
    if st.button("▶ Ejecutar simulación", type="primary", disabled=config is None):
        try:
            nuevo = SmartGridFacade(calculation=BILLING_METHODS[calculo_nombre][0](), user_role=rol)
            nuevo.run_simulation_cycle(config, verbose=False, use_flyweight=usar_perfil,
                                       profile_type=tipo_perfil, flexible_load_pct=flexible)
        except PermissionError:
            st.error("El rol Invitado solo puede mirar. Para ejecutar una simulación elige "
                     "Administrador u Operador en el Paso 1.")
        except Exception as e:  # noqa: BLE001
            st.error(f"No se pudo ejecutar la simulación: {e}")
        else:
            st.session_state["facade"] = nuevo
            st.session_state["origen_simulado"] = origen_texto
            st.session_state["rol_simulado"] = rol
            st.session_state.pop("comparacion_cobro", None)
            st.success("Simulación lista. Mira los resultados a la derecha →")

# ---------------------------------------------------------------- bienvenida
facade: SmartGridFacade = st.session_state.get("facade")
if facade is None or facade.get_billing() is None:
    st.title("Red Inteligente")
    st.caption("Simula un día completo (24 horas) de una red eléctrica: cuánta energía se consume, "
               "cuánta se genera, cuánto cuesta y qué pasa cuando haces cambios.")
    c1, c2 = st.columns(2)
    c1.markdown('<div class="tarjeta-modulo"><h4>📡 Monitoreo de la red</h4><p>Sigue el consumo y el estado '
                'eléctrico hora a hora y detecta a tiempo voltajes fuera de rango, sobrecargas y pérdidas de '
                'energía.</p></div>', unsafe_allow_html=True)
    c2.markdown('<div class="tarjeta-modulo"><h4>⚖️ Demanda y picos</h4><p>Reparte la energía entre las fuentes, '
                'mueve consumo de las horas más exigidas a las más tranquilas y cuida los equipos de la '
                'sobrecarga.</p></div>', unsafe_allow_html=True)
    st.write("")
    c3, c4 = st.columns(2)
    c3.markdown('<div class="tarjeta-modulo"><h4>🌞 Energías renovables</h4><p>Combina solar, eólica, '
                'hidroeléctrica, geotérmica y baterías, y estabiliza el voltaje cuando el sol o el viento '
                'cambian.</p></div>', unsafe_allow_html=True)
    c4.markdown('<div class="tarjeta-modulo"><h4>💲 Facturación dinámica</h4><p>Calcula el precio de la '
                'energía según la hora y cuánta energía limpia hay, y muestra cuánto gana la empresa.</p></div>',
                unsafe_allow_html=True)
    st.write("")
    st.info("**Para empezar:** en la barra lateral elige tus datos (puedes dejar la **red de ejemplo**) y "
            "pulsa **Ejecutar simulación**. Si una palabra no se entiende, mira la pestaña **Ayuda**.")
    st.stop()

st.title("Red Inteligente")
st.caption(f"Resultados de: **{st.session_state.get('origen_simulado', '')}** · "
           f"rol: **{ROL_NOMBRE.get(st.session_state.get('rol_simulado'), '')}**")
if st.session_state.get("rol_simulado") != rol:
    st.warning("Cambiaste el rol en la barra lateral. Pulsa **Ejecutar simulación** para que se aplique.")

billing = facade.get_billing()
horas = facade.get_hour_results()
m = facade.performance_metrics()
estado = estado_actual(facade)
H = [r.reading["hour"] for r in horas]
tipos = m["source_types"]


def etiqueta_fuente(nombre: str) -> str:
    return TIPO_FUENTE.get(tipos.get(nombre), "Otra")


def aporte_por_tipo() -> dict:
    """Energía (kW por hora) que aportó cada tipo de fuente, hora a hora."""
    datos = {}
    for i, r in enumerate(horas):
        for nombre, kw in r.trace.dispatched_by_source:
            datos.setdefault(etiqueta_fuente(nombre), [0.0] * len(horas))[i] += kw
    return datos


(t_panel, t_monitor, t_demanda, t_renov, t_fact, t_operar, t_rep, t_perm, t_ayuda) = st.tabs([
    "Panel general", "Monitoreo", "Demanda y picos", "Energías renovables", "Facturación",
    "Operar la red", "Reportes", "Permisos y actividad", "Ayuda"])

# ---------------------------------------------------------------- Panel general
with t_panel:
    if estado["sin_energia"] == 0:
        st.success("La red cubrió la demanda las 24 horas.")
    else:
        faltan = [hhmm(r.reading["hour"]) for r in horas if r.reading["balance_kw"] < 0]
        st.warning(f"En {estado['sin_energia']} horas no alcanzó la energía ({', '.join(faltan)}). "
                   "Prueba encender fuentes de respaldo, reparar una fuente o cambiar el modo en **Operar la red**.")
    lo, la = m["load_original"], m["load_applied"]
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Demanda máxima", f"{la['peak_kw']:.1f} kW",
              f"{la['peak_kw'] - lo['peak_kw']:+.1f} kW" if lo["peak_kw"] != la["peak_kw"] else None,
              delta_color="inverse", help="La hora más exigida del día (ya con el consumo flexible movido).")
    k2.metric("Energía renovable", fmt_pct(m["renewable_share"]), help="Parte de lo generado que vino de fuentes limpias.")
    k3.metric("Costo del día", f"${billing.total_cost():.2f}", help="Lo que cuesta la energía consumida (unidades de ejemplo).")
    k4.metric("Pérdidas en la red", f"{m['losses_kwh']:.1f} kWh",
              f"{m['losses_kwh'] / m['demand_kwh']:.1%} de la demanda" if m["demand_kwh"] else None,
              delta_color="off", help="Energía que se pierde por calentamiento al transportarla.")
    k5.metric("Alertas", estado["alertas"], help="Avisos de la red: picos, voltaje fuera de rango, pérdidas, fallas.")

    izq, der = st.columns([2, 1])
    with izq:
        st.markdown("**Demanda y generación durante el día (kW)**")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=H, y=[r.reading["generation_kw"] for r in horas], name="Generación",
                                 fill="tozeroy", mode="lines", line=dict(color=VERDE, width=2),
                                 fillcolor="rgba(31,157,107,.25)"))
        fig.add_trace(go.Scatter(x=H, y=[r.reading["demand_kw"] for r in horas], name="Demanda",
                                 mode="lines", line=dict(color=VERDE_OSCURO, width=3)))
        fig.add_hline(y=facade.current_peak_threshold(), line_dash="dash", line_color=AMBAR,
                      annotation_text="Límite de pico", annotation_position="top left")
        fig.update_xaxes(title="Hora del día", dtick=3)
        grafico(fig, "panel_curva")
        st.caption("Cuando la generación queda por debajo de la demanda, falta energía.")
    with der:
        st.markdown("**Energía renovable del día**")
        medidor = go.Figure(go.Indicator(
            mode="gauge+number", value=m["renewable_share"] * 100, number={"suffix": " %"},
            gauge={"axis": {"range": [0, 100]}, "bar": {"color": VERDE},
                   "steps": [{"range": [0, 40], "color": "#f6e3c4"}, {"range": [40, 70], "color": "#dcebd5"},
                             {"range": [70, 100], "color": "#bfe3cf"}]}))
        medidor.update_layout(height=260)
        grafico(medidor, "panel_medidor")
        st.caption("Con 70 % o más de energía limpia se aplica la tarifa de incentivo.")

    izq, der = st.columns(2)
    with izq:
        st.markdown("**¿Cuánto se cobra por cada tarifa? ($)**")
        resumen_tarifa = billing.summary_by_tariff()
        fig = go.Figure(go.Bar(x=list(resumen_tarifa), y=list(resumen_tarifa.values()), marker_color=VERDE,
                               text=[f"${v:.2f}" for v in resumen_tarifa.values()], textposition="outside"))
        fig.update_yaxes(title="Costo ($)")
        grafico(fig, "panel_tarifas")
    with der:
        st.markdown("**¿De dónde vino la energía?**")
        totales = {k: sum(v) for k, v in aporte_por_tipo().items() if sum(v) > 0}
        fig = go.Figure(go.Pie(labels=list(totales), values=list(totales.values()), hole=0.6,
                               marker=dict(colors=[COLOR_FUENTE.get(k, GRIS) for k in totales]),
                               textinfo="percent"))
        grafico(fig, "panel_dona")

# ---------------------------------------------------------------- Monitoreo
with t_monitor:
    st.subheader("Monitoreo de la red")
    st.caption("Cómo estaba la red en cada hora: consumo, estado eléctrico, pérdidas y avisos.")
    p1, p2, p3, p4 = st.columns(4)
    p1.metric("Lecturas procesadas", len(horas), help="Una por hora, con voltaje, corriente, factor de potencia y pérdidas.")
    p2.metric("Alertas detectadas", len(m["alerts"]))
    p3.metric("Pérdidas de energía", f"{m['losses_kwh']:.1f} kWh")
    p4.metric("Horas con falta de energía", f"{estado['sin_energia']} de 24")

    st.markdown("#### Ver el día en vivo")
    st.caption("Reproduce las 24 horas una a una, como si la red se estuviera midiendo en este momento.")
    if st.button("▶ Reproducir el día", key="mon_vivo"):
        caja = st.empty()
        acumulado = []
        try:
            lecturas = facade.monitor.get_history()
        except PermissionError:
            lecturas = []
            st.error("Tu rol no puede leer el historial de la red.")
        for lectura in ReadingIterator(lecturas):
            acumulado.append(lectura)
            with caja.container():
                a, b, c, d = st.columns(4)
                a.metric("Hora", hhmm(lectura["hour"]))
                b.metric("Demanda", f"{lectura['demand_kw']:.1f} kW")
                c.metric("Generación", f"{lectura['generation_kw']:.1f} kW", f"{lectura['balance_kw']:+.1f} kW")
                d.metric("Voltaje", f"{lectura['voltage']:.1f} V")
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=[x["hour"] for x in acumulado], y=[x["demand_kw"] for x in acumulado],
                                         name="Demanda", line=dict(color=VERDE_OSCURO, width=3)))
                fig.add_trace(go.Scatter(x=[x["hour"] for x in acumulado], y=[x["generation_kw"] for x in acumulado],
                                         name="Generación", line=dict(color=VERDE, width=2)))
                fig.update_xaxes(range=[0, 23], title="Hora del día")
                grafico(fig)
            time.sleep(0.25)

    st.markdown("#### Una hora en detalle")
    hora_mon = st.select_slider("Hora", options=H, format_func=hhmm, key="mon_hora")
    rm = next(x for x in horas if x.reading["hour"] == hora_mon)
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Demanda", f"{rm.reading['demand_kw']:.1f} kW")
    k2.metric("Generación", f"{rm.reading['generation_kw']:.1f} kW", f"{rm.reading['balance_kw']:+.1f} kW")
    raw_v = rm.trace.voltage_raw if rm.trace.voltage_raw is not None else rm.reading["voltage"]
    k3.metric("Voltaje", f"{rm.reading['voltage']:.1f} V",
              f"{rm.reading['voltage'] - raw_v:+.1f} V por estabilización" if raw_v != rm.reading["voltage"] else None,
              delta_color="off")
    k4.metric("Pérdidas", f"{rm.reading['technical_loss_kw']:.2f} kW")
    k5, k6, k7, k8 = st.columns(4)
    k5.metric("Corriente", f"{rm.reading['current']:.0f} A")
    k6.metric("Factor de potencia", f"{rm.reading['power_factor']:.2f}")
    k7.metric("Situación", SITUACION.get(rm.state_name, rm.state_name))
    k8.metric("Tarifa", rm.invoice_item["tariff"])
    for texto in rm.trace.anomalies:
        st.warning(texto)

    izq, der = st.columns(2)
    with izq:
        st.markdown("**Corriente durante el día (A)**")
        fig = go.Figure(go.Scatter(x=H, y=[r.reading["current"] for r in horas], mode="lines",
                                   line=dict(color=AZUL, width=3), fill="tozeroy", fillcolor="rgba(59,130,196,.15)"))
        fig.add_hline(y=400, line_dash="dash", line_color=ROJO, annotation_text="Límite de los equipos")
        fig.update_xaxes(title="Hora del día", dtick=3)
        grafico(fig, "mon_corriente")
    with der:
        st.markdown("**Pérdidas de energía por hora (kW)**")
        fig = go.Figure(go.Bar(x=H, y=[r.reading["technical_loss_kw"] for r in horas], marker_color=AMBAR))
        fig.update_xaxes(title="Hora del día", dtick=3)
        grafico(fig, "mon_perdidas")

    st.markdown("#### Alertas y fallas detectadas")
    filas_alerta = [{"Hora": hhmm(a["hour"]) if a["hour"] is not None else "—",
                     "Tipo": a["type"], "Detalle": a["detail"]} for a in m["alerts"]]
    filas_alerta += [{"Hora": hhmm(x.reading["hour"]), "Tipo": "Falta de energía",
                      "Detalle": f"Se generó {-x.reading['balance_kw']:.1f} kW menos de lo que se pedía."}
                     for x in horas if x.reading["balance_kw"] < 0]
    if filas_alerta:
        tipos_alerta = sorted({f["Tipo"] for f in filas_alerta})
        filtro = st.multiselect("Mostrar solo", tipos_alerta, default=tipos_alerta, key="mon_filtro")
        tabla(pd.DataFrame(sorted((f for f in filas_alerta if f["Tipo"] in filtro), key=lambda f: f["Hora"])))
    else:
        st.write("No se detectó ninguna alerta.")

    with st.expander("Lo que pasó en cada hora"):
        tabla(pd.DataFrame([{
            "Hora": hhmm(r.reading["hour"]), "Demanda (kW)": r.reading["demand_kw"],
            "Generación (kW)": r.reading["generation_kw"], "Diferencia (kW)": r.reading["balance_kw"],
            "Situación": SITUACION.get(r.state_name, r.state_name), "Modo de respaldo": r.trace.strategy_name,
            "Voltaje (V)": r.reading["voltage"], "Pérdidas (kW)": r.reading["technical_loss_kw"],
            "Avisos eléctricos": len(r.trace.anomalies), "Tarifa": r.invoice_item["tariff"],
            "Costo ($)": round(r.invoice_item["cost"], 2),
        } for r in horas]))
        st.caption("**Diferencia** = generación − demanda: si es negativa, faltó energía. "
                   "**Situación**: Normal = todo tranquilo · Pico = demanda alta o avisos · Emergencia = falta energía.")
        cambios = facade.get_state_transitions()
        if cambios:
            st.markdown("**Cambios de situación durante el día**")
            tabla(pd.DataFrame([{"Hora": hhmm(t.hour), "Pasó de": SITUACION.get(t.previous, t.previous),
                                 "A": SITUACION.get(t.current, t.current)} for t in cambios]))

# ---------------------------------------------------------------- Demanda y picos
with t_demanda:
    st.subheader("Demanda y picos")
    st.caption("Qué tan exigida estuvo la red y cómo se repartió la carga para no sobrecargar los equipos.")
    salud = facade.equipment_health()
    a, b, c, d, e = st.columns(5)
    a.metric("Demanda máxima", f"{la['peak_kw']:.1f} kW",
             f"{la['peak_kw'] - lo['peak_kw']:+.1f} kW" if lo["peak_kw"] != la["peak_kw"] else None,
             delta_color="inverse", help="La hora más exigida del día.")
    b.metric("Energía sobre el límite", f"{la['excess_kwh']:.1f} kWh",
             f"{la['excess_kwh'] - lo['excess_kwh']:+.1f} kWh" if lo["excess_kwh"] != la["excess_kwh"] else None,
             delta_color="inverse", help="Consumo que supera el límite de pico (riesgo de sobrecarga).")
    c.metric("Factor de carga", f"{la['load_factor']:.2f}",
             f"{la['load_factor'] - lo['load_factor']:+.2f}" if lo["load_factor"] != la["load_factor"] else None,
             help="Promedio ÷ máximo. Mientras más cerca de 1, más plana es la curva.")
    d.metric("Horas sobre el límite", la["hours_over_limit"],
             f"{la['hours_over_limit'] - lo['hours_over_limit']:+d}" if lo["hours_over_limit"] != la["hours_over_limit"] else None,
             delta_color="inverse")
    e.metric("Desgaste máximo de equipos", fmt_pct(salud.worst_wear),
             help="Los equipos se desgastan cuando la corriente supera su límite. Aplanar picos lo reduce.")

    if facade.current_flexible_load_pct() > 0 and la["peak_kw"] < lo["peak_kw"]:
        st.success(f"Se aplanó la curva: el pico bajó de {lo['peak_kw']:.1f} a {la['peak_kw']:.1f} kW y la energía "
                   "total del día se conservó.")
    elif facade.current_flexible_load_pct() == 0:
        st.info("Ahora no se mueve consumo. Prueba el Paso 5 de la barra lateral o **Operar la red → Mover consumo flexible**.")

    st.markdown("**Demanda del día frente al límite de pico (kW)**")
    fig = go.Figure()
    if m["demand_original"] != m["demand_applied"]:
        fig.add_trace(go.Scatter(x=list(m["demand_original"]), y=list(m["demand_original"].values()),
                                 name="Demanda original", line=dict(color=GRIS, width=2, dash="dot")))
    fig.add_trace(go.Bar(x=H, y=[r.reading["demand_kw"] for r in horas], name="Demanda",
                         marker_color=[COLOR_SITUACION.get(r.state_name, VERDE) for r in horas],
                         opacity=.85))
    fig.add_hline(y=facade.current_peak_threshold(), line_dash="dash", line_color=AMBAR,
                  annotation_text="Límite de pico", annotation_position="top left")
    fig.update_xaxes(title="Hora del día", dtick=3)
    grafico(fig, "dem_curva")
    st.caption("Color de cada barra: 🟢 normal · 🟠 pico (demanda alta o avisos) · 🔴 emergencia (falta energía).")

    izq, der = st.columns(2)
    with izq:
        st.markdown("**Salud de los equipos**")
        tabla(pd.DataFrame([{
            "Equipo": f["name"], "Capacidad (kW)": f["capacity_kw"], "Capacidad actual (kW)": f["effective_kw"],
            "Desgaste": fmt_pct(f["wear"]),
            "Estado": {"falla": "🔴 En falla", "activa": "🟢 Encendido", "apagada": "⚫ Apagado"}[f["status"]],
        } for f in salud.rows]))
    with der:
        st.markdown("**Desgaste de equipos durante el día**")
        fig = go.Figure(go.Scatter(x=H, y=[w["wear"] * 100 for w in m["wear_by_hour"]], mode="lines",
                                   line=dict(color=ROJO, width=3)))
        fig.update_yaxes(title="Desgaste (%)")
        fig.update_xaxes(title="Hora del día", dtick=3)
        grafico(fig, "dem_desgaste")
    st.caption("Cuando la corriente pasa el límite de los equipos se van desgastando; si el desgaste llega al "
               "95 %, el equipo sale de servicio. Mover consumo fuera de las horas pico protege la red.")

# ---------------------------------------------------------------- Energías renovables
with t_renov:
    st.subheader("Energías renovables")
    st.caption("Cuánto aportan el sol, el viento, el agua, la tierra y las baterías, y cómo se mantiene estable el voltaje.")
    cap = facade.capacity_summary()
    v, almacen = m["voltage"], m["storage"]
    a, b, c, d = st.columns(4)
    a.metric("Energía renovable del día", fmt_pct(m["renewable_share"]))
    b.metric("Capacidad renovable instalada", f"{cap.renewable_kw:.0f} kW", f"{cap.renewable_share:.0%} de la capacidad total",
             delta_color="off", help="Potencia máxima de las fuentes limpias (sin contar baterías).")
    c.metric("Oscilación del voltaje", f"{v['final_std']:.2f} V", f"{-v['reduction_pct']:.0%} vs sin estabilizar",
             delta_color="inverse" if v["reduction_pct"] else "off", help=f"Sin estabilizar: {v['raw_std']:.2f} V.")
    d.metric("Horas con refuerzo estable", v["reinforced_hours"],
             help="Horas en que se usó la capacidad libre de fuentes estables (hidro, geotérmica, térmica) para amortiguar al sol y al viento.")

    st.markdown("**¿Quién generó la energía en cada hora? (kW)**")
    fig = go.Figure()
    for tipo, valores in aporte_por_tipo().items():
        fig.add_trace(go.Bar(x=H, y=valores, name=tipo, marker_color=COLOR_FUENTE.get(tipo, GRIS)))
    fig.update_layout(barmode="stack")
    fig.update_xaxes(title="Hora del día", dtick=3)
    grafico(fig, "ren_reparto")
    st.caption("El sol solo aporta de día y el viento varía: cuando las renovables no alcanzan, entran las baterías y, "
               "si hace falta, el respaldo convencional.")

    izq, der = st.columns(2)
    with izq:
        st.markdown("**Voltaje durante el día (V)**")
        fig = go.Figure()
        fig.add_hrect(y0=209, y1=231, fillcolor="rgba(31,157,107,.10)", line_width=0)
        fig.add_trace(go.Scatter(x=H, y=[x.trace.voltage_raw if x.trace.voltage_raw is not None else x.reading["voltage"]
                                         for x in horas], name="Sin estabilizar", line=dict(color=GRIS, width=2, dash="dot")))
        fig.add_trace(go.Scatter(x=H, y=[x.reading["voltage"] for x in horas], name="Con estabilización",
                                 line=dict(color=VERDE, width=3)))
        fig.update_xaxes(title="Hora del día", dtick=3)
        grafico(fig, "ren_voltaje")
        st.caption("La zona verde es el rango normal (220 V ± 5 %).")
    with der:
        st.markdown("**Baterías**")
        if almacen["has_storage"]:
            e1, e2 = st.columns(2)
            e1.metric("Excedente guardado", f"{almacen['charged_kwh']:.1f} kWh")
            e2.metric("Energía entregada", f"{almacen['delivered_kwh']:.1f} kWh")
            fig = go.Figure(go.Bar(x=H, y=[r.trace.storage_charge_kw for r in horas], marker_color="#8e6bbf"))
            fig.update_yaxes(title="Excedente guardado (kW)")
            fig.update_xaxes(title="Hora del día", dtick=3)
            grafico(fig, "ren_baterias")
        else:
            st.info("Esta red no tiene baterías. Con baterías, el excedente de sol y viento se guarda para cuando falte energía.")

    st.markdown("**Fuentes de la red**")
    for sector in facade.get_root_sector().children:
        st.markdown(f"*{sector.name.replace('Sector ', '')}*")
        filas = []
        for hoja in sector.children:
            s = hoja.source
            nivel = f"{s.charge_level:.0%}" if getattr(s, "charge_level", None) is not None else "—"
            filas.append({
                "Fuente": s.name, "Tipo": TIPO_FUENTE.get(type(s).__name__, "Otra"),
                "Capacidad (kW)": s.capacity_kw,
                "Estado": "🔴 En falla" if s.failed else ("🟢 Encendida" if s.is_active else "⚫ Apagada"),
                "Carga de batería": nivel,
            })
        tabla(pd.DataFrame(filas))

# ---------------------------------------------------------------- Facturación
with t_fact:
    st.subheader("Facturación y rentabilidad")
    st.caption("Cuánto se cobra, cuánto cuesta generar y qué tan rentable fue el día.")
    p = m["profit"]
    a, b, c, d, e = st.columns(5)
    a.metric("Ingresos", f"${p['revenue']:.2f}", help="Total facturado a los clientes.")
    b.metric("Costo de generación", f"${p['generation_cost']:.2f}",
             help="Cada tipo de fuente tiene un costo por kWh (solar y eólica baratas, térmica cara).")
    c.metric("Margen", f"${p['margin']:.2f}", f"{p['margin_pct']:.0%} de los ingresos", delta_color="off",
             help="(Ingresos − costo de generación).")
    d.metric("Precio promedio", f"${p['avg_price']:.3f}/kWh", help="Ingresos ÷ energía vendida.")
    e.metric("Consumo en horas pico (18–22 h)", fmt_pct(m["peak_hours_share"]),
             help="La franja más cara: mientras menos consumo aquí, mejor.")

    izq, der = st.columns([3, 2])
    with izq:
        st.markdown("**Costo de cada hora según la tarifa aplicada ($)**")
        fig = go.Figure()
        for tarifa in sorted({r.invoice_item["tariff"] for r in horas}):
            fig.add_trace(go.Bar(x=[r.reading["hour"] for r in horas if r.invoice_item["tariff"] == tarifa],
                                 y=[r.invoice_item["cost"] for r in horas if r.invoice_item["tariff"] == tarifa],
                                 name=tarifa))
        fig.update_layout(barmode="stack")
        fig.update_xaxes(title="Hora del día", dtick=3, range=[-0.5, 23.5])
        grafico(fig, "fac_horas")
    with der:
        st.markdown("**Consumo y cobro por tarifa**")
        tabla(pd.DataFrame([{
            "Tarifa": t["tariff"], "Energía (kWh)": round(t["kwh"], 1),
            "Parte del consumo": f"{t['share']:.0%}", "Cobrado ($)": round(t["cost"], 2),
        } for t in m["tariff_table"]]))
    st.caption("La tarifa cambia con la hora y con cuánta energía renovable hay: más barata fuera de pico y con mucha "
               "renovable, más cara en la franja de 6 a 10 pm. Eso invita a consumir en horas tranquilas.")

    st.markdown("#### ¿Qué forma de cobro le conviene más a la empresa?")
    actual_cobro = method_name_of(facade.calculation)
    st.write(f"Forma de cobro actual: **{actual_cobro or 'personalizada'}**")
    mostrar_aviso("cobro")
    if st.button("Comparar las formas de cobro", key="fac_comparar"):
        st.session_state["comparacion_cobro"] = facade.compare_billing_methods()
    comparacion = st.session_state.get("comparacion_cobro")
    if comparacion:
        tabla(pd.DataFrame([{
            "Forma de cobro": o["method"], "Ingresos ($)": round(o["revenue"], 2),
            "Margen ($)": round(o["margin"], 2), "Margen (%)": f"{o['margin_pct']:.0%}",
            "Cobrado en horas pico": f"{o['peak_revenue_share']:.0%}",
        } for o in comparacion]))
        mejor = comparacion[0]
        st.success(f"La de mayor margen es **{mejor['method']}** (${mejor['margin']:.2f}).")
        if mejor["method"] != actual_cobro and st.button("Usar esta forma de cobro", key="fac_usar"):
            aplicar(facade, "cobro",
                    lambda: facade.use_billing_method(BILLING_METHODS[mejor["method"]][0]()),
                    f"Listo: ahora se cobra con «{mejor['method']}».")
    else:
        st.caption("Vuelve a calcular el mismo día con cada forma de cobro y muestra cuál deja mejor margen.")

    with st.expander("Detalle del cobro hora por hora"):
        tabla(pd.DataFrame([{
            "Hora": hhmm(r.reading["hour"]), "Demanda (kWh)": r.invoice_item["demand_kwh"],
            "Tarifa": r.invoice_item["tariff"], "Precio ($/kWh)": r.invoice_item["price_per_kwh"],
            "Ajustes de precio": ", ".join(x for x in r.invoice_item["decorators"] if x != "(ninguno)") or "—",
            "Costo ($)": round(r.invoice_item["cost"], 2),
        } for r in horas]))

# ---------------------------------------------------------------- Operar la red
with t_operar:
    st.subheader("Haz cambios y mira qué pasa")
    st.write("Cada cambio recalcula el día completo y te muestra cómo cambian los costos, "
             "las horas sin energía y las alertas. Todos se pueden deshacer.")
    mostrar_aviso("operar")
    estados = facade.source_states()
    en_falla = facade.failed_sources()

    st.markdown("#### 1. Apagar o encender una fuente")
    st.caption("Sirve para simular un mantenimiento (apagar) o la vuelta a servicio (encender).")
    nombre = st.selectbox("Fuente", list(estados), key="op_fuente")
    st.write(f"Ahora está: **{'en falla' if nombre in en_falla else ('encendida' if estados[nombre] else 'apagada')}**")
    accion = st.radio("¿Qué quieres hacer?", ["Apagarla", "Encenderla"], horizontal=True, key="op_accion")
    quiere_activa = accion == "Encenderla"
    if nombre in en_falla:
        st.info("Esa fuente está en falla: repárala en el punto 2.")
    elif quiere_activa == estados[nombre]:
        st.info(f"Esa fuente ya está {'encendida' if quiere_activa else 'apagada'}.")
    elif st.button(f"{'Encender' if quiere_activa else 'Apagar'} {nombre}", key="op_toggle"):
        aplicar(facade, "operar", lambda: facade.toggle_source(nombre, quiere_activa),
                f"Listo: «{nombre}» quedó {'encendida' if quiere_activa else 'apagada'}.")

    st.divider()
    st.markdown("#### 2. Simular una falla de equipo")
    st.caption("La fuente deja de producir, se avisa en las alertas y el resto de la red se reacomoda. Luego puedes repararla.")
    if en_falla:
        st.warning(f"Fuentes en falla ahora: {', '.join(en_falla)}")
    nombre_falla = st.selectbox("Fuente", list(estados), key="op_falla_fuente")
    motivo = st.text_input("Motivo de la falla", value="falla de equipo", key="op_falla_motivo")
    f1, f2 = st.columns(2)
    if f1.button("🔴 Provocar falla", key="op_falla", disabled=nombre_falla in en_falla):
        aplicar(facade, "operar", lambda: facade.report_source_failure(nombre_falla, motivo),
                f"Falla registrada en «{nombre_falla}».")
    if f2.button("🟢 Reparar fuente", key="op_reparar", disabled=nombre_falla not in en_falla):
        aplicar(facade, "operar", lambda: facade.repair_source(nombre_falla),
                f"«{nombre_falla}» reparada y de vuelta en servicio.")

    st.divider()
    st.markdown("#### 3. Cambiar el límite de pico")
    st.caption("Es la demanda (en kW) a partir de la cual la red se considera en «pico» y se activan "
               "las fuentes de respaldo. Un límite más bajo activa el respaldo antes (más costo, menos riesgo).")
    actual = float(facade.current_peak_threshold())
    nuevo_limite = st.number_input("Nuevo límite de pico (kW)", min_value=1.0, value=actual, step=5.0,
                                   key=f"op_umbral_{actual}")
    st.write(f"Límite actual: **{actual:g} kW**")
    if st.button("Aplicar nuevo límite", key="op_limite", disabled=nuevo_limite == actual):
        aplicar(facade, "operar", lambda: facade.change_peak_threshold(nuevo_limite),
                f"Listo: el límite de pico ahora es {nuevo_limite:g} kW.", pista_sin_efecto=True)

    st.divider()
    st.markdown("#### 4. Modo de respaldo")
    st.caption("Define cuándo se usan las fuentes de respaldo (las convencionales).")
    modo_actual = facade.current_strategy_name()
    claves = list(MODOS)
    elegido = st.radio("Modo", claves, index=claves.index(modo_actual), format_func=MODOS.get,
                       label_visibility="collapsed", key=f"op_modo_{modo_actual}")
    if st.button("Aplicar modo", key="op_modo_btn", disabled=elegido == modo_actual):
        aplicar(facade, "operar", lambda: facade.set_strategy(elegido),
                f"Listo: modo de respaldo → {MODOS[elegido].split(' (')[0]}.", pista_sin_efecto=True)

    st.divider()
    st.markdown("#### 5. Mover consumo flexible")
    st.caption("Cuando la demanda pasa el límite de pico, este porcentaje del exceso se traslada a horas con "
               "menos demanda. Baja el pico sin perder energía total.")
    flex_actual = float(facade.current_flexible_load_pct())
    nuevo_flex = st.slider("Consumo flexible (%)", 0, 100, int(flex_actual), step=5, key=f"op_flex_{flex_actual}")
    st.write(f"Ahora: **{flex_actual:g} %**")
    if st.button("Aplicar", key="op_flex_btn", disabled=nuevo_flex == flex_actual):
        aplicar(facade, "operar", lambda: facade.set_flexible_load(nuevo_flex),
                f"Listo: ahora se mueve el {nuevo_flex:g} % del consumo que pasa el límite.", pista_sin_efecto=True)

    st.divider()
    st.markdown("#### Historial de cambios")
    historial = facade.get_command_history()
    if historial:
        for i, texto in enumerate(historial, start=1):
            st.write(f"{i}. {texto}")
        if st.button("↩ Deshacer el último cambio", key="op_deshacer"):
            aplicar(facade, "operar", facade.undo_last_command, "Listo: se deshizo el último cambio.")
    else:
        st.write("Todavía no has hecho cambios.")

    st.divider()
    st.markdown("#### Puntos de guardado")
    st.write("Un punto de guardado es una **foto de cómo está la red ahora**: fuentes encendidas o en falla, "
             "límite de pico, modo de respaldo y consumo flexible. Después puedes hacer todos los cambios que "
             "quieras y **volver a esa foto**.")
    mostrar_aviso("puntos")
    etiqueta = st.text_input("Nombre del punto (opcional)", placeholder="Ej.: Todo encendido", key="cp_nombre")
    if st.button("💾 Guardar un punto con la red como está ahora", key="cp_guardar"):
        try:
            punto = facade.save_checkpoint(etiqueta)
            aviso("puntos", "success", f"Guardado: «{punto.label}».")
        except PermissionError:
            aviso("puntos", "error", "Tu rol no puede guardar puntos.")
        volver_a_dibujar()
    puntos = facade.get_checkpoints()
    if not puntos:
        st.info("Aún no hay puntos guardados.")
    for i, pto in enumerate(puntos):
        izq, centro, der = st.columns([6, 2, 1])
        with izq:
            st.markdown(f"**{i + 1}. {pto.label}** · guardado a las {pto.created_at[11:]}")
            apagadas = [n for n, activa in pto.source_states if not activa]
            limite = f"{pto.peak_threshold_kw:g} kW" if pto.peak_threshold_kw is not None else "—"
            costo = f"${pto.total_cost:.2f}" if pto.total_cost is not None else "—"
            st.caption(f"Fuentes apagadas: {', '.join(apagadas) or 'ninguna'} · límite de pico: {limite} · "
                       f"modo: {MODOS[pto.strategy_name].split(' (')[0]} · consumo flexible: {pto.flexible_load_pct:g} % · "
                       f"costo del día: {costo}")
        with centro:
            if st.button("Volver a este punto", key=f"cp_ir_{i}"):
                antes = estado_actual(facade)
                try:
                    facade.restore_checkpoint(i)
                    aviso("puntos", "success",
                          f"Volviste a «{pto.label}». El historial de cambios se reinició.\n\n"
                          + comparar(antes, estado_actual(facade)))
                except PermissionError:
                    aviso("puntos", "error", "Tu rol no puede restaurar puntos.")
                volver_a_dibujar()
        with der:
            if st.button("Borrar", key=f"cp_borrar_{i}"):
                facade.delete_checkpoint(i)
                volver_a_dibujar()

# ---------------------------------------------------------------- Reportes
with t_rep:
    st.subheader("Reportes")
    st.caption("Resúmenes en texto. Puedes descargarlos.")
    titulos = {"operacion": "Operación de la red", "facturacion": "Facturación", "renovables": "Energía renovable"}
    for clave, texto in facade.generate_reports(billing).items():
        with st.expander(titulos.get(clave, clave.capitalize())):
            st.code(texto)
            st.download_button("⬇ Descargar", texto, file_name=f"reporte_{clave}.txt", key=f"dl_{clave}")
    tabla_csv = pd.DataFrame([{
        "hora": r.reading["hour"], "demanda_kw": r.reading["demand_kw"],
        "generacion_kw": r.reading["generation_kw"], "diferencia_kw": r.reading["balance_kw"],
        "situacion": r.state_name, "tarifa": r.invoice_item["tariff"], "costo": r.invoice_item["cost"],
    } for r in horas]).to_csv(index=False)
    st.download_button("⬇ Descargar la tabla hora por hora (CSV)", tabla_csv,
                       file_name="hora_por_hora.csv", mime="text/csv")

# ---------------------------------------------------------------- Permisos y actividad
with t_perm:
    st.subheader("Quién puede hacer qué")
    st.write(f"Tu rol en esta sesión: **{ROL_NOMBRE.get(facade.monitor.user_role, facade.monitor.user_role)}**")
    nombres_rol = {Role.ADMIN: "Administrador", Role.OPERATOR: "Operador", Role.GUEST: "Invitado"}
    tabla(pd.DataFrame([{
        "Acción": p.value.capitalize(),
        **{nombres_rol[r]: "✅" if p in DEFAULT_ROLE_PERMISSIONS[r] else "⛔" for r in Role},
    } for p in Permission]))

    if st.button("Comprobar si mi rol puede reiniciar el sistema", key="act_probar"):
        try:
            facade.monitor.authorize(Permission.RESET, "probar_permiso_reinicio")
            st.success("Sí puedes. Esto fue solo una prueba: no se reinició nada.")
        except PermissionError:
            st.error("No puedes: tu rol no tiene ese permiso.")

    st.subheader("Registro de actividad")
    st.caption("Cada acción queda anotada, sea permitida o rechazada.")
    ocultar = st.checkbox("Ocultar las simples consultas", value=True)
    solo_rechazadas = st.checkbox("Mostrar solo lo rechazado", value=False)
    try:
        filas = [{
            "Hora": e.timestamp[11:], "Rol": ROL_NOMBRE.get(e.role, e.role),
            "Acción": ACCIONES_REGISTRO.get(e.action, e.action),
            "Resultado": "✅ Permitido" if e.allowed else "⛔ Rechazado",
        } for e in reversed(facade.monitor.audit_trail())
            if not (ocultar and e.action in LECTURAS) and not (solo_rechazadas and e.allowed)]
        if filas:
            tabla(pd.DataFrame(filas[:200]))
        else:
            st.write("No hay actividad que mostrar con esos filtros.")
    except PermissionError:
        st.error("Tu rol no puede ver el registro.")

# ---------------------------------------------------------------- Ayuda
with t_ayuda:
    st.subheader("Tipos de consumo disponibles")
    st.caption("Así se comporta la demanda de cada tipo de usuario a lo largo del día (kW).")
    fig = go.Figure()
    for nombre_d, (usa, tipo) in DEMANDAS.items():
        if usa:
            curva = ConsumptionProfileFactory.get_profile(tipo).curve
            fig.add_trace(go.Scatter(x=list(range(24)), y=[curva[h] for h in range(24)],
                                     name=nombre_d.split(" (")[0], mode="lines", line=dict(width=3)))
    fig.update_xaxes(title="Hora del día", dtick=3)
    grafico(fig, "ayuda_perfiles")
    st.caption("Los valores de dinero ($) son unidades de ejemplo, no una moneda real.")
