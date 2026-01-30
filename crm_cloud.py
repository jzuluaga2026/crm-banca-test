import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from datetime import datetime
import io
# Librería para el micrófono
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

# --- FUNCIÓN AUXILIAR PARA VOZ Y TEXTO ---
def render_voice_input(label, key_base, height=100):
    """
    Crea un bloque con botón de micrófono y área de texto.
    Maneja el estado para que no se borre lo escrito manualmente.
    """
    # 1. Crear llaves únicas para session_state
    key_text = f"{key_base}_text"
    key_voice = f"{key_base}_voice"
    key_last_voice = f"{key_base}_last_voice"

    # 2. Inicializar estado del texto si no existe
    if key_text not in st.session_state:
        st.session_state[key_text] = ""
    if key_last_voice not in st.session_state:
        st.session_state[key_last_voice] = ""

    # 3. Componente de micrófono
    st.markdown(f"**{label}**")
    voice_content = speech_to_text(
        language='es', 
        start_prompt="🎙️ Grabar", 
        stop_prompt="⏹️ Detener", 
        just_once=True,
        key=key_voice
    )

    # 4. Lógica de actualización: Solo sobrescribir si hay NUEVA voz
    if voice_content and voice_content != st.session_state[key_last_voice]:
        st.session_state[key_text] = voice_content
        st.session_state[key_last_voice] = voice_content

    # 5. Área de texto vinculada al estado (permite edición manual)
    return st.text_area(
        label="", 
        key=key_text, 
        height=height, 
        placeholder="Escriba aquí o use el micrófono..."
    )

# --- INTERFAZ PRINCIPAL ---
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

    # ==========================================
    # 1. FUNNEL COMERCIAL
    # ==========================================
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

    # ==========================================
    # 2. BITÁCORA (VISITAS) - Con Voz Mejorada
    # ==========================================
    elif menu == "Bitácora (Visitas)":
        st.header("📒 Bitácora con Dictado de Voz")
        
        nit_bit = st.number_input("NIT Cliente:", min_value=1, format="%d")
        tab_b1, tab_b2 = st.tabs(["📝 Nuevo Registro", "📜 Historial"])
        
        with tab_b1:
            c1, c2 = st.columns(2)
            f_cont = c1.date_input("Fecha Contacto")
            nom_cont = c2.text_input("Nombre Contacto")
            
            # Usamos la función auxiliar para manejar voz + texto manual
            temas = render_voice_input("1. Temas Abordados", "bit_temas")
            resultados = render_voice_input("2. Resultados Obtenidos", "bit_res")
            obj_prox = render_voice_input("3. Objetivo Siguiente Paso", "bit_obj", height=68)
            
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
                        # Limpiar campos manualmente en session_state
                        st.session_state["bit_temas_text"] = ""
                        st.session_state["bit_res_text"] = ""
                        st.session_state["bit_obj_text"] = ""
                        st.rerun()
                else: st.error("Falta NIT o Nombre")

        with tab_b2:
            if nit_bit:
                df_b = get_data("bitacora")
                if not df_b.empty:
                    f = df_b[df_b['cliente_id'] == nit_bit].sort_values('fecha_contacto', ascending=False)
                    for i, r in f.iterrows():
                        with st.expander(f"{r['fecha_contacto']} - {r['nombre_contacto']}"):
                            st.write(f"**Temas:** {r['temas']}")
                            st.write(f"**Resultados:** {r['resultados']}")
                            st.caption(f"Prox: {r['objetivo_prox']} ({r['fecha_prox']})")

    # ==========================================
    # 3. PLAN DE CUENTA (RESTAURADO)
    # ==========================================
    elif menu == "Plan de Cuenta":
        st.header("📋 Plan de Cuenta Estratégico")
        st.info("Utiliza los micrófonos para dictar el análisis extenso.")
        
        id_p = st.number_input("NIT Cliente:", min_value=1, format="%d", key="nit_plan")
        
        # Cargar último plan si existe
        if id_p:
            df_p = get_data("plan_cuenta")
            prev_analisis = ""
            prev_cadena = ""
            prev_riesgos = ""
            
            if not df_p.empty:
                filtro = df_p[df_p['cliente_id'] == id_p].sort_values('fecha_gestion', ascending=False)
                if not filtro.empty:
                    last = filtro.iloc[0]
                    prev_analisis = last.get('analisis_fin_pos', '')
                    prev_cadena = last.get('cadena_valor_pos', '')
                    prev_riesgos = last.get('riesgos', '')
            
            # Inicializar los campos con el valor de la base de datos SI es la primera vez que carga
            if f"plan_fin_text" not in st.session_state:
                st.session_state["plan_fin_text"] = prev_analisis
                st.session_state["plan_cad_text"] = prev_cadena
                st.session_state["plan_rsk_text"] = prev_riesgos

            # Campos con voz
            a_pos = render_voice_input("Análisis Financiero", "plan_fin", height=150)
            c_val = render_voice_input("Cadena de Valor", "plan_cad", height=150)
            riesgos = render_voice_input("Riesgos Detectados", "plan_rsk", height=100)
            
            if st.button("💾 Guardar Plan de Cuenta"):
                fila = pd.DataFrame([{
                    "id": None, "cliente_id": id_p, 
                    "analisis_fin_pos": a_pos, "analisis_fin_rev": "", 
                    "cadena_valor_pos": c_val, "cadena_valor_rev": "",
                    "flujo_efec_pos": "", "flujo_efec_rev": "", 
                    "riesgos": riesgos,
                    "comercial_id": st.session_state.user_id, "fecha_gestion": str(datetime.now())
                }])
                if save_data("plan_cuenta", fila): 
                    st.success("Plan estratégico actualizado en la nube.")

    # ==========================================
    # 4. REPORTES
    # ==========================================
    elif menu == "Reportes":
        st.header("📊 Descarga de Información")
        tipo = st.selectbox("Base de Datos:", ["Funnel Comercial", "Bitácora", "Plan de Cuenta"])
        sheet_map = {"Funnel Comercial": "funnel", "Bitácora": "bitacora", "Plan de Cuenta": "plan_cuenta"}
        
        if st.button("Generar Excel"):
            df_rep = get_data(sheet_map[tipo])
            if not df_rep.empty:
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df_rep.to_excel(writer, index=False)
                st.download_button("📥 Descargar", output.getvalue(), f"{sheet_map[tipo]}.xlsx")
            else: st.warning("Sin datos.")
