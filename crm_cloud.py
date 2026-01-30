import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from datetime import datetime
import io
# Librería para el micrófono
from streamlit_mic_recorder import speech_to_text

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="CRM Banca - Colombia", layout="wide", page_icon="🏦")

# --- CATÁLOGOS ---
PRODUCTOS = [
    "Cartera Ordinaria", "Fuente de Pago", "Leasing", 
    "CDT", "Cta Corriente", "Cta Ahorros"
]

ETAPAS = [
    "1. Oportunidad planeada (hipótesis de ventas)",
    "2. Cliente contactado",
    "3. Cliente interesado",
    "4. Cliente con Propuesta Comercial",
    "5. Cliente en Documentación / Estudio de Crédito",
    "6. Cliente con Desembolso / Productos Activados"
]

ESTADOS = [
    "Planeada", "Abierta en contacto", "Abierta interesado", 
    "Abierta en proceso", "Cerrada ganada", "Cerrada perdida"
]

# --- CONEXIÓN ---
SHEET_URL = "https://docs.google.com/spreadsheets/d/1eEpJjUcETl50P4QDJEOuOr-3x3TrLoNxhMijjb11D5Y/edit?usp=sharing"
conn = st.connection("gsheets", type=GSheetsConnection)

def get_data(worksheet_name):
    try:
        # ttl=0 evita que guarde caché viejo
        return conn.read(spreadsheet=SHEET_URL, worksheet=worksheet_name, ttl=0)
    except Exception:
        return pd.DataFrame()

def save_data(worksheet_name, new_row_df):
    try:
        existing_data = get_data(worksheet_name)
        # Limpieza básica para evitar filas fantasmas
        if not existing_data.empty:
            existing_data = existing_data.dropna(how='all')
        
        updated_df = pd.concat([existing_data, new_row_df], ignore_index=True)
        conn.update(spreadsheet=SHEET_URL, worksheet=worksheet_name, data=updated_df)
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Error técnico al guardar: {e}")
        return False

def generar_no_oportunidad():
    """Genera un consecutivo de 6 dígitos iniciando en 100000"""
    df = get_data("funnel")
    if df.empty or 'no_oportunidad' not in df.columns: 
        return 100001
    try:
        # Convertir a número forzoso, ignorar errores
        series_nums = pd.to_numeric(df['no_oportunidad'], errors='coerce')
        max_op = series_nums.max()
        if pd.isna(max_op) or max_op < 100000:
            return 100001
        return int(max_op) + 1
    except: 
        return 100001

# --- FUNCIÓN INTELIGENTE DE VOZ ---
def render_voice_input(label, key_base, height=100):
    """
    Crea campo de texto + botón de voz. 
    Conserva el texto manual si no hay nueva grabación.
    """
    key_text = f"{key_base}_text"
    key_voice = f"{key_base}_voice"
    key_last_voice = f"{key_base}_last_voice"

    if key_text not in st.session_state: st.session_state[key_text] = ""
    if key_last_voice not in st.session_state: st.session_state[key_last_voice] = ""

    st.markdown(f"**{label}**")
    # Botón de micrófono
    voice_content = speech_to_text(
        language='es', start_prompt="🎙️ Grabar", stop_prompt="⏹️ Fin", 
        just_once=True, key=key_voice
    )

    # Lógica: Si hay voz nueva, reemplaza. Si no, respeta lo escrito.
    if voice_content and voice_content != st.session_state[key_last_voice]:
        st.session_state[key_text] = voice_content
        st.session_state[key_last_voice] = voice_content

    return st.text_area(label="", key=key_text, height=height)

# --- APP PRINCIPAL ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("🏦 CRM Banca Comercial")
    with st.form("login"):
        u_id = st.text_input("Ingresa tu ID Comercial:")
        if st.form_submit_button("Ingresar"):
            if u_id:
                st.session_state.logged_in = True
                st.session_state.user_id = u_id
                st.rerun()
else:
    st.sidebar.title(f"👤 {st.session_state.user_id}")
    menu = st.sidebar.radio("Navegación", ["Funnel Comercial", "Plan de Cuenta", "Bitácora (Visitas)", "Reportes"])
    
    if st.sidebar.button("Salir"):
        st.session_state.logged_in = False
        st.rerun()

    # ==========================================
    # 1. FUNNEL COMERCIAL (Ajustado)
    # ==========================================
    if menu == "Funnel Comercial":
        st.header("📉 Funnel Comercial")
        t1, t2 = st.tabs(["🆕 Nueva Oportunidad", "✏️ Gestionar Existente"])
        
        with t1:
            st.info("El No. de Oportunidad se genera automáticamente (6 dígitos).")
            with st.form("f_nuevo"):
                c1, c2 = st.columns(2)
                # Campos solicitados
                cli_id = c1.number_input("1. ID Cliente", min_value=1, format="%d")
                cli_nom = c1.text_input("2. Nombre Cliente")
                prod = c1.selectbox("4. Producto", PRODUCTOS)
                val = c2.number_input("5. Valor Oportunidad ($)", min_value=0.0)
                f_cie = c2.date_input("6. Fecha Estimada Cierre")
                
                st.markdown("**Estado Inicial:**")
                st.write("7. Etapa: " + ETAPAS[0])
                st.write("8. Estado: " + ESTADOS[0])
                
                if st.form_submit_button("🚀 Crear Oportunidad"):
                    if cli_nom and cli_id:
                        n_op = generar_no_oportunidad()
                        fila = pd.DataFrame([{
                            "id": None, "cliente_id": cli_id, "cliente_nombre": cli_nom,
                            "no_oportunidad": n_op, 
                            "producto": prod, "valor": val, "fecha_cierre": str(f_cie), 
                            "etapa": ETAPAS[0], "estado": ESTADOS[0],
                            "comercial_id": st.session_state.user_id, 
                            "fecha_gestion": str(datetime.now())
                        }])
                        if save_data("funnel", fila): 
                            st.success(f"¡Oportunidad #{n_op} creada exitosamente!")
                    else: st.error("ID y Nombre son obligatorios.")

        with t2:
            busq = st.number_input("Buscar ID Cliente:", min_value=1, format="%d")
            df_f = get_data("funnel")
            
            if not df_f.empty and busq in df_f['cliente_id'].values:
                df_cli = df_f[df_f['cliente_id'] == busq].sort_values('fecha_gestion', ascending=False)
                
                # Selector de negocio
                lista_ops = df_cli['no_oportunidad'].unique()
                op_sel = st.selectbox("Seleccione Oportunidad:", lista_ops)
                
                row = df_cli[df_cli['no_oportunidad'] == op_sel].iloc[0]
                st.markdown(f"**Cliente:** {row['cliente_nombre']} | **Producto:** {row['producto']}")
                
                with st.form("f_av"):
                    ne = st.selectbox("7. Nueva Etapa", ETAPAS, index=ETAPAS.index(row['etapa']) if row['etapa'] in ETAPAS else 0)
                    nest = st.selectbox("8. Nuevo Estado", ESTADOS, index=ESTADOS.index(row['estado']) if row['estado'] in ESTADOS else 0)
                    
                    if st.form_submit_button("💾 Actualizar"):
                        fila = pd.DataFrame([{
                            "id": None, "cliente_id": busq, "cliente_nombre": row['cliente_nombre'],
                            "no_oportunidad": op_sel, "producto": row['producto'], "valor": row['valor'],
                            "fecha_cierre": row['fecha_cierre'], "etapa": ne, "estado": nest,
                            "comercial_id": st.session_state.user_id, "fecha_gestion": str(datetime.now())
                        }])
                        if save_data("funnel", fila): st.success("Avance registrado.")
            elif busq:
                st.warning("No se encontraron negocios para este cliente.")

    # ==========================================
    # 2. PLAN DE CUENTA (Nuevos campos)
    # ==========================================
    elif menu == "Plan de Cuenta":
        st.header("📋 Plan de Cuenta Estratégico")
        id_p = st.number_input("1. ID Cliente (Plan):", min_value=1, format="%d")
        
        # Lógica para cargar datos previos
        defaults = {k: "" for k in ["an_fin_pos", "an_fin_rev", "cad_val_pos", "cad_val_rev", "flujo_pos", "flujo_rev", "riesgos"]}
        if id_p:
            df_p = get_data("plan_cuenta")
            if not df_p.empty:
                f_p = df_p[df_p['cliente_id'] == id_p].sort_values('fecha_gestion', ascending=False)
                if not f_p.empty:
                    last = f_p.iloc[0]
                    for k in defaults.keys():
                        if k in last: defaults[k] = last[k]

        # Inicializar sesión si cambió de cliente
        if "last_plan_id" not in st.session_state or st.session_state.last_plan_id != id_p:
            st.session_state.last_plan_id = id_p
            for k, v in defaults.items():
                st.session_state[f"{k}_text"] = v

        with st.form("form_plan"):
            st.subheader("2. Análisis Financiero")
            af_p = render_voice_input("Aspectos Positivos", "an_fin_pos", 80)
            af_r = render_voice_input("Aspectos por Revisar", "an_fin_rev", 80)
            
            st.subheader("3. Cadena de Valor")
            cv_p = render_voice_input("Aspectos Positivos", "cad_val_pos", 80)
            cv_r = render_voice_input("Aspectos por Revisar", "cad_val_rev", 80)
            
            st.subheader("4. Flujo de Efectivo")
            fl_p = render_voice_input("Aspectos Positivos", "flujo_pos", 80)
            fl_r = render_voice_input("Aspectos por Revisar", "flujo_rev", 80)
            
            st.subheader("5. Riesgos")
            rsk = render_voice_input("Riesgos / Limitaciones", "riesgos", 80)
            
            if st.form_submit_button("💾 Guardar Plan"):
                fila = pd.DataFrame([{
                    "id": None, "cliente_id": id_p, 
                    "an_fin_pos": af_p, "an_fin_rev": af_r,
                    "cad_val_pos": cv_p, "cad_val_rev": cv_r,
                    "flujo_pos": fl_p, "flujo_rev": fl_r,
                    "riesgos": rsk,
                    "comercial_id": st.session_state.user_id, 
                    "fecha_gestion": str(datetime.now())
                }])
                if save_data("plan_cuenta", fila): st.success("Plan guardado.")

    # ==========================================
    # 3. BITÁCORA
    # ==========================================
    elif menu == "Bitácora (Visitas)":
        st.header("📒 Bitácora Comercial")
        nit_bit = st.number_input("NIT Cliente:", min_value=1, format="%d")
        
        t_new, t_hist = st.tabs(["Nueva Visita", "Historial"])
        with t_new:
            c1, c2 = st.columns(2)
            f_cont = c1.date_input("Fecha Contacto")
            nom_cont = c2.text_input("Nombre Contacto")
            
            temas = render_voice_input("Temas Claves Abordados", "bit_temas")
            res = render_voice_input("Resultados Obtenidos", "bit_res")
            obj = render_voice_input("Objetivo Sig. Contacto", "bit_obj", 68)
            f_prox = st.date_input("Fecha Sig. Contacto")
            
            if st.button("💾 Guardar Visita"):
                if nit_bit and nom_cont:
                    fila = pd.DataFrame([{
                        "id": None, "cliente_id": nit_bit, "fecha_contacto": str(f_cont),
                        "nombre_contacto": nom_cont, "temas": temas, "resultados": res,
                        "objetivo_prox": obj, "fecha_prox": str(f_prox),
                        "comercial_id": st.session_state.user_id, "fecha_registro": str(datetime.now())
                    }])
                    if save_data("bitacora", fila):
                        st.success("Guardado.")
                        # Limpiar visualmente
                        for k in ["bit_temas_text", "bit_res_text", "bit_obj_text"]:
                            st.session_state[k] = ""
                        st.rerun()
                else: st.error("Faltan datos obligatorios.")
        
        with t_hist:
            if nit_bit:
                df_b = get_data("bitacora")
                if not df_b.empty and 'cliente_id' in df_b.columns:
                    f = df_b[df_b['cliente_id'] == nit_bit].sort_values('fecha_contacto', ascending=False)
                    st.dataframe(f[['fecha_contacto', 'nombre_contacto', 'temas', 'resultados', 'objetivo_prox']])

    elif menu == "Reportes":
        st.header("📊 Reportes")
        tipo = st.selectbox("Base de datos:", ["Funnel", "Plan de Cuenta", "Bitácora"])
        mapa = {"Funnel": "funnel", "Plan de Cuenta": "plan_cuenta", "Bitácora": "bitacora"}
        if st.button("Descargar"):
            df = get_data(mapa[tipo])
            out = io.BytesIO()
            with pd.ExcelWriter(out, engine='openpyxl') as writer:
                df.to_excel(writer, index=False)
            st.download_button("📥 Bajar Excel", out.getvalue(), f"{mapa[tipo]}.xlsx")
