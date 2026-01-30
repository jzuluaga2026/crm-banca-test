import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from datetime import datetime
import io

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="CRM Banca - Cloud Edition", layout="wide")

# URL de tu hoja (Verifica que sea la correcta)
SHEET_URL = "https://docs.google.com/spreadsheets/d/1eEpJjUcETl50P4QDJEOuOr-3x3TrLoNxhMijjb11D5Y/edit?usp=sharing"

# Conexión
conn = st.connection("gsheets", type=GSheetsConnection)

def get_data(worksheet_name):
    # ttl=0 asegura que traiga los datos frescos de la nube y no de la memoria
    return conn.read(spreadsheet=SHEET_URL, worksheet=worksheet_name, ttl=0)

def save_data(worksheet_name, new_row_df):
    try:
        existing_data = get_data(worksheet_name)
        # Limpiar columnas vacías o extrañas que a veces mete Excel
        existing_data = existing_data.dropna(axis=1, how='all')
        
        # Concatenar el historial
        updated_df = pd.concat([existing_data, new_row_df], ignore_index=True)
        
        # GUARDAR EN GOOGLE SHEETS
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
        # Convertir a numérico por si Google Sheets lo lee como texto
        max_op = pd.to_numeric(df['no_oportunidad'], errors='coerce').max()
        return int(max_op) + 1 if pd.notna(max_op) else 100000
    except: return 100000

# --- INTERFAZ ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("🏦 CRM Banca Empresas")
    u_id = st.text_input("Identificación Comercial:")
    if st.button("Ingresar"):
        if u_id:
            st.session_state.logged_in = True
            st.session_state.user_id = u_id
            st.rerun()
else:
    st.sidebar.title(f"👤 ID: {st.session_state.user_id}")
    menu = st.sidebar.radio("Menú", ["Funnel Comercial", "Plan de Cuenta", "📊 Reportes (Excel)"])
    
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state.logged_in = False
        st.rerun()

    # --- MÓDULO FUNNEL ---
    if menu == "Funnel Comercial":
        st.header("📉 Gestión de Funnel")
        t1, t2 = st.tabs(["🆕 Nueva Oportunidad", "✏️ Registro de Avance"])
        
        with t1:
            with st.form("f_nuevo"):
                c1, c2 = st.columns(2)
                cli_id = c1.number_input("ID Cliente", min_value=1, format="%d")
                cli_nom = c1.text_input("Nombre del Cliente")
                prod = c1.selectbox("Producto", ["Leasing", "Cartera Ordinaria", "CDT", "Cta Corriente"])
                val = c2.number_input("Valor", min_value=0.0)
                f_cie = c2.date_input("Fecha Estimada Cierre")
                estado = c2.selectbox("Estado", ["Planeada", "En contacto", "Interesado", "En proceso", "Cerrada Ganada", "Cerrada Perdida"])
                
                if st.form_submit_button("🚀 Guardar en Google Sheets"):
                    if cli_nom:
                        n_op = generar_no_oportunidad()
                        fila = pd.DataFrame([{
                            "id": None, "cliente_id": cli_id, "cliente_nombre": cli_nom,
                            "no_oportunidad": n_op, "producto": prod, "valor": val,
                            "fecha_cierre": str(f_cie), "etapa": "Gestión Inicial", "estado": estado,
                            "comercial_id": st.session_state.user_id, "fecha_gestion": str(datetime.now())
                        }])
                        if save_data("funnel", fila):
                            st.success(f"¡Oportunidad #{n_op} sincronizada!")
                    else: st.error("El nombre es obligatorio")

        with t2:
            busq = st.number_input("Buscar ID Cliente:", min_value=1, format="%d")
            df_f = get_data("funnel")
            if not df_f.empty and busq in df_f['cliente_id'].values:
                df_cli = df_f[df_f['cliente_id'] == busq].sort_values('fecha_gestion', ascending=False)
                op_sel = st.selectbox("Seleccione Op:", df_cli['no_oportunidad'].unique())
                row = df_cli[df_cli['no_oportunidad'] == op_sel].iloc[0]
                
                with st.form("f_avance"):
                    n_est = st.selectbox("Cambiar Estado", ["Planeada", "En contacto", "Interesado", "En proceso", "Cerrada Ganada", "Cerrada Perdida"])
                    if st.form_submit_button("💾 Guardar Avance"):
                        fila = pd.DataFrame([{
                            "id": None, "cliente_id": busq, "cliente_nombre": row['cliente_nombre'],
                            "no_oportunidad": op_sel, "producto": row['producto'], "valor": row['valor'],
                            "fecha_cierre": row['fecha_cierre'], "etapa": "Actualización", "estado": n_est,
                            "comercial_id": st.session_state.user_id, "fecha_gestion": str(datetime.now())
                        }])
                        if save_data("funnel", fila): st.success("Historial actualizado")
            else: st.info("Ingrese un ID con gestiones previas")

    # --- MÓDULO PLAN DE CUENTA ---
    elif menu == "Plan de Cuenta":
        st.header("📋 Plan de Cuenta del Cliente")
        id_p = st.number_input("ID Cliente:", min_value=1, format="%d")
        if id_p:
            df_p = get_data("plan_cuenta")
            prev = df_p[df_p['cliente_id'] == id_p].sort_values('fecha_gestion', ascending=False)
            last = prev.iloc[0] if not prev.empty else {}
            
            with st.form("f_plan"):
                a_pos = st.text_area("Análisis Financiero", value=last.get('analisis_fin_pos', ''))
                c_val = st.text_area("Cadena de Valor", value=last.get('cadena_valor_pos', ''))
                riesgos = st.text_area("Riesgos detectados", value=last.get('riesgos', ''))
                
                if st.form_submit_button("💾 Guardar Gestión de Plan"):
                    fila = pd.DataFrame([{
                        "id": None, "cliente_id": id_p, "analisis_fin_pos": a_pos,
                        "analisis_fin_rev": "", "cadena_valor_pos": c_val, "cadena_valor_rev": "",
                        "flujo_efec_pos": "", "flujo_efec_rev": "", "riesgos": riesgos,
                        "comercial_id": st.session_state.user_id, "fecha_gestion": str(datetime.now())
                    }])
                    if save_data("plan_cuenta", fila): st.success("Plan guardado en la nube")

    # --- MÓDULO REPORTES ---
    elif menu == "📊 Reportes (Excel)":
        st.header("Descarga de Información Consolidada")
        tipo = st.selectbox("Reporte:", ["Funnel Comercial", "Planes de Cuenta"])
        sheet_name = "funnel" if tipo == "Funnel Comercial" else "plan_cuenta"
        
        df_rep = get_data(sheet_name)
        
        if not df_rep.empty:
            st.dataframe(df_rep.head(20))
            
            # Generar Excel en memoria
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_rep.to_excel(writer, index=False, sheet_name='Historial')
            
            st.download_button(
                label="📥 Descargar Reporte en Excel",
                data=output.getvalue(),
                file_name=f"Reporte_{sheet_name}_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else: st.warning("No hay datos en esta pestaña.")