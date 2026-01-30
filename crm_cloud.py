import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from datetime import datetime
import io

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="CRM Banca - Colombia", layout="wide", page_icon="🏦")

# --- LISTAS DESPLEGABLES (CATÁLOGOS) ---
PRODUCTOS = [
    "Cartera Ordinaria", 
    "Fuente de Pago", 
    "Leasing", 
    "CDT", 
    "Cta Corriente", 
    "Cta Ahorros"
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
    "Planeada", 
    "Abierta en contacto", 
    "Abierta interesado", 
    "Abierta en proceso", 
    "Cerrada ganada", 
    "Cerrada perdida"
]

# --- CONEXIÓN ---
# Reemplaza esto con tu URL si cambió, si es la misma déjala así
SHEET_URL = "https://docs.google.com/spreadsheets/d/1eEpJjUcETl50P4QDJEOuOr-3x3TrLoNxhMijjb11D5Y/edit?usp=sharing"
conn = st.connection("gsheets", type=GSheetsConnection)

def get_data(worksheet_name):
    try:
        return conn.read(spreadsheet=SHEET_URL, worksheet=worksheet_name, ttl=0)
    except Exception as e:
        st.error(f"Error al leer la hoja '{worksheet_name}'. Verifica que exista en Google Sheets.")
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
        u_id = st.text_input("Identificación Comercial (Usuario):")
        if st.form_submit_button("Ingresar"):
            if u_id:
                st.session_state.logged_in = True
                st.session_state.user_id = u_id
                st.rerun()
else:
    st.sidebar.title(f"👤 {st.session_state.user_id}")
    menu = st.sidebar.radio("Menú Principal", ["Funnel Comercial", "Bitácora (Visitas)", "Plan de Cuenta", "Reportes"])
    
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state.logged_in = False
        st.rerun()

    # ---------------------------------------------------------
    # MÓDULO 1: FUNNEL COMERCIAL
    # ---------------------------------------------------------
    if menu == "Funnel Comercial":
        st.header("📉 Gestión de Oportunidades")
        t1, t2 = st.tabs(["🆕 Crear Oportunidad", "✏️ Actualizar Avance"])
        
        with t1:
            with st.form("f_nuevo"):
                st.subheader("Nueva Oportunidad")
                c1, c2 = st.columns(2)
                cli_id = c1.number_input("NIT / ID Cliente", min_value=1, format="%d")
                cli_nom = c1.text_input("Razón Social / Nombre")
                prod = c1.selectbox("Producto", PRODUCTOS)
                val = c2.number_input("Valor Estimado ($)", min_value=0.0, format="%.2f")
                f_cie = c2.date_input("Fecha Cierre Estimada")
                
                # Valores por defecto para nueva op
                st.info("La oportunidad iniciará en etapa: '1. Oportunidad planeada' y estado 'Planeada'.")
                
                if st.form_submit_button("🚀 Crear Oportunidad"):
                    if cli_nom:
                        n_op = generar_no_oportunidad()
                        fila = pd.DataFrame([{
                            "id": None, "cliente_id": cli_id, "cliente_nombre": cli_nom,
                            "no_oportunidad": n_op, "producto": prod, "valor": val,
                            "fecha_cierre": str(f_cie), 
                            "etapa": "1. Oportunidad planeada (hipótesis de ventas)", 
                            "estado": "Planeada",
                            "comercial_id": st.session_state.user_id, "fecha_gestion": str(datetime.now())
                        }])
                        if save_data("funnel", fila):
                            st.success(f"¡Oportunidad #{n_op} creada exitosamente!")
                    else: st.error("El nombre del cliente es obligatorio")

        with t2:
            st.subheader("Actualizar Estado de Negocio")
            busq = st.number_input("Buscar por NIT / ID Cliente:", min_value=1, format="%d")
            df_f = get_data("funnel")
            
            if not df_f.empty and busq in df_f['cliente_id'].values:
                # Filtrar solo lo de este cliente
                df_cli = df_f[df_f['cliente_id'] == busq].copy()
                # Ordenar para ver lo más reciente primero
                df_cli = df_cli.sort_values('fecha_gestion', ascending=False)
                
                # Selector de oportunidad (Muestra ID - Producto - Valor)
                opciones = df_cli['no_oportunidad'].unique()
                op_sel = st.selectbox("Seleccione el negocio a actualizar:", opciones)
                
                # Obtener datos actuales de esa oportunidad
                row = df_cli[df_cli['no_oportunidad'] == op_sel].iloc[0]
                st.write(f"**Producto:** {row['producto']} | **Cliente:** {row['cliente_nombre']}")
                
                with st.form("f_avance"):
                    col_a, col_b = st.columns(2)
                    n_etapa = col_a.selectbox("Nueva Etapa", ETAPAS, index=ETAPAS.index(row['etapa']) if row['etapa'] in ETAPAS else 0)
                    n_estado = col_b.selectbox("Nuevo Estado", ESTADOS, index=ESTADOS.index(row['estado']) if row['estado'] in ESTADOS else 0)
                    
                    if st.form_submit_button("💾 Registrar Avance"):
                        fila = pd.DataFrame([{
                            "id": None, "cliente_id": busq, "cliente_nombre": row['cliente_nombre'],
                            "no_oportunidad": op_sel, "producto": row['producto'], "valor": row['valor'],
                            "fecha_cierre": row['fecha_cierre'], "etapa": n_etapa, "estado": n_estado,
                            "comercial_id": st.session_state.user_id, "fecha_gestion": str(datetime.now())
                        }])
                        if save_data("funnel", fila): st.success("Bitácora de oportunidad actualizada.")
            else:
                st.info("Ingrese un NIT para buscar negocios activos.")

    # ---------------------------------------------------------
    # MÓDULO 2: BITÁCORA (NUEVO)
    # ---------------------------------------------------------
    elif menu == "Bitácora (Visitas)":
        st.header("📒 Bitácora Comercial")
        st.markdown("Use el **dictado por voz** de su teclado (móvil o PC) para llenar los campos de texto más rápido. 🎙️")
        
        nit_bitacora = st.number_input("NIT Cliente para Bitácora:", min_value=1, format="%d")
        
        # Pestañas: Ver Historial vs Nuevo Registro
        tab_b1, tab_b2 = st.tabs(["📝 Nuevo Registro", "📜 Ver Historial"])
        
        with tab_b1:
            with st.form("form_bitacora"):
                c1, c2 = st.columns(2)
                f_contacto = c1.date_input("Fecha de Contacto", datetime.now())
                nom_contacto = c2.text_input("Nombre del Contacto (Persona):")
                
                st.markdown("---")
                # Campos de texto amplios para permitir dictado
                temas = st.text_area("🗣️ Temas Claves Abordados:", height=100, help="Puede dictar aquí")
                resultados = st.text_area("🗣️ Resultados Obtenidos:", height=100)
                obj_prox = st.text_input("🗣️ Objetivo Siguiente Contacto:")
                f_prox = st.date_input("Fecha Siguiente Contacto")
                
                if st.form_submit_button("💾 Guardar en Bitácora"):
                    if nit_bitacora and nom_contacto:
                        fila_bit = pd.DataFrame([{
                            "id": None, 
                            "cliente_id": nit_bitacora,
                            "fecha_contacto": str(f_contacto),
                            "nombre_contacto": nom_contacto,
                            "temas": temas,
                            "resultados": resultados,
                            "objetivo_prox": obj_prox,
                            "fecha_prox": str(f_prox),
                            "comercial_id": st.session_state.user_id,
                            "fecha_registro": str(datetime.now())
                        }])
                        if save_data("bitacora", fila_bit):
                            st.success("Registro de visita guardado correctamente.")
                    else:
                        st.error("El NIT y Nombre del contacto son obligatorios.")
        
        with tab_b2:
            if nit_bitacora:
                df_b = get_data("bitacora")
                if not df_b.empty:
                    # Filtrar por cliente
                    filt_b = df_b[df_b['cliente_id'] == nit_bitacora].sort_values('fecha_contacto', ascending=False)
                    if not filt_b.empty:
                        for index, row in filt_b.iterrows():
                            with st.expander(f"📅 {row['fecha_contacto']} - {row['nombre_contacto']}"):
                                st.markdown(f"**Temas:** {row['temas']}")
                                st.markdown(f"**Resultados:** {row['resultados']}")
                                st.info(f"👉 **Próximo paso:** {row['objetivo_prox']} ({row['fecha_prox']})")
                    else:
                        st.warning("No hay registros previos para este cliente.")
                else:
                    st.warning("La bitácora está vacía.")

    # ---------------------------------------------------------
    # MÓDULO 3: PLAN DE CUENTA
    # ---------------------------------------------------------
    elif menu == "Plan de Cuenta":
        st.header("📋 Plan de Cuenta (Estratégico)")
        id_p = st.number_input("NIT Cliente:", min_value=1, format="%d", key="nit_plan")
        if id_p:
            df_p = get_data("plan_cuenta")
            # Buscar último registro
            prev = pd.DataFrame()
            if not df_p.empty:
                prev = df_p[df_p['cliente_id'] == id_p].sort_values('fecha_gestion', ascending=False)
            
            last = prev.iloc[0] if not prev.empty else {}
            
            with st.form("f_plan"):
                st.markdown("Use el dictado por voz 🎙️ para análisis extensos.")
                a_pos = st.text_area("Análisis Financiero", value=last.get('analisis_fin_pos', ''), height=150)
                c_val = st.text_area("Cadena de Valor", value=last.get('cadena_valor_pos', ''), height=150)
                riesgos = st.text_area("Riesgos detectados", value=last.get('riesgos', ''), height=100)
                
                if st.form_submit_button("💾 Guardar Plan"):
                    fila = pd.DataFrame([{
                        "id": None, "cliente_id": id_p, "analisis_fin_pos": a_pos,
                        "analisis_fin_rev": "", "cadena_valor_pos": c_val, "cadena_valor_rev": "",
                        "flujo_efec_pos": "", "flujo_efec_rev": "", "riesgos": riesgos,
                        "comercial_id": st.session_state.user_id, "fecha_gestion": str(datetime.now())
                    }])
                    if save_data("plan_cuenta", fila): st.success("Plan guardado en la nube")

    # ---------------------------------------------------------
    # MÓDULO 4: REPORTES
    # ---------------------------------------------------------
    elif menu == "Reportes":
        st.header("📊 Descarga de Información")
        tipo = st.selectbox("Seleccione Base de Datos:", ["Funnel Comercial", "Bitácora de Visitas", "Planes de Cuenta"])
        
        # Mapeo de nombre en menú a nombre en hoja
        sheet_map = {
            "Funnel Comercial": "funnel",
            "Bitácora de Visitas": "bitacora",
            "Planes de Cuenta": "plan_cuenta"
        }
        
        if st.button("Generar Vista Previa"):
            df_rep = get_data(sheet_map[tipo])
            if not df_rep.empty:
                st.dataframe(df_rep)
                
                # Botón descarga
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df_rep.to_excel(writer, index=False, sheet_name='Datos')
                
                st.download_button(
                    label="📥 Descargar Excel",
                    data=output.getvalue(),
                    file_name=f"{sheet_map[tipo]}_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.warning("No hay datos para mostrar.")
