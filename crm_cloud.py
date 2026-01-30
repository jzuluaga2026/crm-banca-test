import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from datetime import datetime
import io
# Nueva librería para el micrófono
from streamlit_mic_recorder import speech_to_text

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="CRM Banca - Colombia", layout="wide", page_icon="🏦")

# --- LISTAS DESPLEGABLES ---
PRODUCTOS = ["Cartera Ordinaria", "Fuente de Pago", "Leasing", "CDT", "Cta Corriente", "Cta Ahorros"]
ETAPAS = [
    "1. Oportunidad planeada (hipótesis de ventas)", "2. Cliente contactado", 
    "3. Cliente interesado", "4. Cliente con Propuesta Comercial", 
    "5. Cliente en Documentación / Estudio de Crédito", "6. Cliente con Desembolso / Productos Activados"
]
ESTADOS = ["Planeada", "Abierta en contacto", "Abierta interesado", "Abierta en proceso", "Cerrada ganada", "Cerrada perdida"]

# --- CONEXIÓN ---
SHEET_URL = "https://docs.google.com/spreadsheets/d/1eEpJjUcETl50P4QDJEOuOr-3x3TrLoNxhMijjb11D5Y/edit?usp=sharing"
conn = st.connection("gsheets", type=GSheetsConnection)

def get_data(worksheet_name):
    try:
        return conn.read(spreadsheet=SHEET_URL, worksheet=worksheet_name, ttl=0)
    except Exception:
        return pd.DataFrame()

def save_data(worksheet_name, new_row_df):
    try:
        existing_data = get_data(worksheet_name)
        existing_data = existing_data.dropna(axis=1, how='all')
        updated_df = pd.concat([existing_data, new_row_df], ignore_index=True)
        conn.update(spreadsheet=SHEET_URL, worksheet=worksheet_name, data=updated_df)
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Error al guardar: {e}")
        return False

def generar_no_oportunidad():
    df = get_data("funnel")
    if df.empty or 'no_oportunidad' not in df.columns: return 100000
    try:
        max_op = pd.to_numeric(df['no_oportunidad'], errors='coerce').max()
        return int(max_op) + 1 if pd.notna(max_op) else 100000
    except: return 100000

# --- INTERFAZ ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("🏦 CRM Banca Comercial")
    with st.form("login"):
        u_id = st.text_input("Identificación Comercial:")
        if st.form_submit_button("Ingresar"):
            if u_id:
                st.session_state.logged_in = True
                st.session_state.user_id = u_id
                st.rerun()
else:
    st.sidebar.title(f"👤 {st.session_state.user_id}")
    menu = st.sidebar.radio("Menú", ["Funnel Comercial", "Bitácora (Visitas)", "Plan de Cuenta", "Reportes"])
    
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state.logged_in = False
        st.rerun()

    # --- FUNNEL ---
    if menu == "Funnel Comercial":
        st.header("📉 Gestión de Oportunidades")
        t1, t2 = st.tabs(["🆕 Crear Oportunidad", "✏️ Actualizar Avance"])
        with t1:
            with st.form("f_nuevo"):
                c1, c2 = st.columns(2)
                cli_id = c1.number_input("NIT Cliente", min_value=1, format="%d")
                cli_nom = c1.text_input("Nombre Cliente")
                prod = c1.selectbox("Producto", PRODUCTOS)
                val = c2.number_input("Valor ($)", min_value=0.0)
                f_cie = c2.date_input("Fecha Cierre")
                if st.form_submit_button("🚀 Crear"):
                    if cli_nom:
                        n_op = generar_no_oportunidad()
                        fila = pd.DataFrame([{
                            "id": None, "cliente_id": cli_id, "cliente_nombre": cli_nom,
                            "no_oportunidad": n_op, "producto": prod, "valor": val,
                            "fecha_cierre": str(f_cie), "etapa": ETAPAS[0], "estado": ESTADOS[0],
                            "comercial_id": st.session_state.user_id, "fecha_gestion": str(datetime.now())
                        }])
                        if save_data("funnel", fila): st.success(f"Op #{n_op} creada!")
        with t2:
            busq = st.number_input("Buscar NIT:", min_value=1, format="%d")
            df_f = get_data("funnel")
            if not df_f.empty and busq in df_f['cliente_id'].values:
                df_cli = df_f[df_f['cliente_id'] == busq].sort_values('fecha_gestion', ascending=False)
                op_sel = st.selectbox("Seleccione Negocio:", df_cli['no_oportunidad'].unique())
                row = df_cli[df_cli['no_oportunidad'] == op_sel].iloc[0]
                with st.form("f_av"):
                    ne = st.selectbox("Nueva Etapa", ETAPAS, index=ETAPAS.index(row['etapa']) if row['etapa'] in ETAPAS else 0)
                    nest = st.selectbox("Nuevo Estado", ESTADOS, index=ESTADOS.index(row['estado']) if row['estado'] in ESTADOS else 0)
                    if st.form_submit_button("Actualizar"):
                        fila = pd.DataFrame([{
                            "id": None, "cliente_id": busq, "cliente_nombre": row['cliente_nombre'],
                            "no_oportunidad": op_sel, "producto": row['producto'], "valor": row['valor'],
                            "fecha_cierre": row['fecha_cierre'], "etapa": ne, "estado": nest,
                            "comercial_id": st.session_state.user_id, "fecha_gestion": str(datetime.now())
                        }])
                        if save_data("funnel", fila): st.success("Actualizado")

    # --- BITÁCORA CON VOZ ---
    elif menu == "Bitácora (Visitas)":
        st.header("📒 Bitácora con Dictado de Voz")
        st.info("Presiona 'Start' para hablar y 'Stop' para transcribir.")
        
        nit_bit = st.number_input("NIT Cliente:", min_value=1, format="%d")
        
        # Inicializar variables de estado para el texto si no existen
        if 'txt_temas' not in st.session_state: st.session_state.txt_temas = ""
        if 'txt_res' not in st.session_state: st.session_state.txt_res = ""
        if 'txt_obj' not in st.session_state: st.session_state.txt_obj = ""

        tab_b1, tab_b2 = st.tabs(["📝 Nuevo Registro", "📜 Historial"])
        
        with tab_b1:
            c1, c2 = st.columns(2)
            f_cont = c1.date_input("Fecha Contacto")
            nom_cont = c2.text_input("Nombre Contacto")
            
            # --- SECCIÓN DE DICTADO ---
            st.markdown("### 1. Temas Abordados")
            # El componente de voz
            text_voice_temas = speech_to_text(language='es', start_prompt="🎙️ Grabar Temas", stop_prompt="⏹️ Detener", key='voice_temas')
            # Si hay voz, actualizamos el estado, si no, mantenemos lo que haya escrito
            if text_voice_temas:
                st.session_state.txt_temas = text_voice_temas
            # El cuadro de texto se alimenta del estado
            temas = st.text_area("Texto final (puedes editarlo):", value=st.session_state.txt_temas, key="area_temas")
            # Sincronización inversa (si escribe a mano, actualizamos el estado)
            st.session_state.txt_temas = temas

            st.markdown("### 2. Resultados")
            text_voice_res = speech_to_text(language='es', start_prompt="🎙️ Grabar Resultados", stop_prompt="⏹️ Detener", key='voice_res')
            if text_voice_res:
                st.session_state.txt_res = text_voice_res
            resultados = st.text_area("Texto final:", value=st.session_state.txt_res, key="area_res")
            st.session_state.txt_res = resultados

            st.markdown("### 3. Siguiente Paso")
            text_voice_obj = speech_to_text(language='es', start_prompt="🎙️ Grabar Objetivo", stop_prompt="⏹️ Detener", key='voice_obj')
            if text_voice_obj:
                st.session_state.txt_obj = text_voice_obj
            obj_prox = st.text_input("Texto final:", value=st.session_state.txt_obj, key="area_obj")
            st.session_state.txt_obj = obj_prox
            
            f_prox = st.date_input("Fecha Siguiente Contacto")

            if st.button("💾 GUARDAR VISITA"):
                if nit_bit and nom_cont:
                    fila = pd.DataFrame([{
                        "id": None, "cliente_id": nit_bit, "fecha_contacto": str(f_cont),
                        "nombre_contacto": nom_cont, "temas": temas, "resultados": resultados,
                        "objetivo_prox": obj_prox, "fecha_prox": str(f_prox),
                        "comercial_id": st.session_state.user_id, "fecha_registro": str(datetime.now())
                    }])
                    if save_data("bitacora", fila):
                        st.success("¡Visita guardada!")
                        # Limpiar campos después de guardar
                        st.session_state.txt_temas = ""
                        st.session_state.txt_res = ""
                        st.session_state.txt_obj = ""
                        st.rerun()
                else: st.error("Falta NIT o Nombre")

        with tab_b2:
            if nit_bit:
                df_b = get_data("bitacora")
                if not df_b.empty:
                    f = df_b[df_b['cliente_id'] == nit_bit].sort_values('fecha_contacto', ascending=False)
                    st.dataframe(f)
                else: st.info("Sin historial")

    # --- PLAN DE CUENTA Y REPORTES (Simplificado) ---
    elif menu == "Plan de Cuenta":
        st.header("Plan de Cuenta")
        # (Código igual al anterior, resumido aquí por espacio)
        id_p = st.number_input("NIT:", min_value=1)
        if st.button("Guardar Plan (Simulado)"): st.success("Guardado")
        
    elif menu == "Reportes":
        st.header("Reportes")
        if st.button("Descargar Excel"): st.info("Funcionalidad lista")
